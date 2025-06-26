import os
from pathlib import Path
from typing import Dict, Any, List, Optional, TypedDict
from enum import Enum

from langchain.agents import AgentExecutor
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import Tool
from langchain.schema import BaseMessage, HumanMessage, AIMessage
from langchain.schema.runnable import RunnablePassthrough
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolExecutor
from rich.console import Console

from .connection import get_llm_client
from .memory import LocopilotMemory, SessionState
from .utils import (
    get_project_files,
    read_file_content,
    create_file_edit_prompt,
    format_file_tree
)


console = Console()


class AgentMode(Enum):
    DO = "do"
    REFACTOR = "refactor"
    EXPLAIN = "explain"
    CHAT = "chat"


class AgentState(TypedDict):
    """State for the LangGraph agent."""
    messages: List[BaseMessage]
    mode: str
    task: str
    plan: Optional[str]
    edits: List[Dict[str, Any]]
    should_summarize: bool
    output: Optional[str]


class LocopilotAgent:
    """Main agent class using LangGraph for workflow management."""
    
    def __init__(self, config: Dict[str, Any], project_path: Path):
        self.config = config
        self.project_path = project_path
        
        # Initialize LLM
        self.llm = get_llm_client(
            backend=config["backend"],
            model=config["model"],
            temperature=0.1
        )
        
        # Initialize memory
        self.memory = LocopilotMemory(
            llm=self.llm,
            max_token_limit=config["memory"]["max_tokens"],
            summarization_threshold=config["memory"]["summarization_threshold"]
        )
        
        # Set initial session state
        self.memory.session_state.update(
            mode=config.get("mode", "do"),
            model=config["model"],
            backend=config["backend"],
            project_path=str(project_path)
        )
        
        # Initialize project context
        self._init_project_context()
        
        # Build the agent graph
        self.graph = self._build_graph()
    
    def _init_project_context(self):
        """Initialize project context by scanning files."""
        project_files = get_project_files(self.project_path)
        
        context = {
            "project_path": str(self.project_path),
            "file_count": len(project_files),
            "file_tree": format_file_tree(self.project_path),
            "main_files": [str(f.relative_to(self.project_path)) for f in project_files[:20]]
        }
        
        self.memory.set_project_context(context)
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        
        # Create the graph
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("parse_input", self._parse_input_node)
        workflow.add_node("plan", self._plan_node)
        workflow.add_node("edit", self._edit_node)
        workflow.add_node("summarize", self._summarize_node)
        workflow.add_node("output", self._output_node)
        
        # Add edges
        workflow.set_entry_point("parse_input")
        
        # Conditional routing based on mode
        workflow.add_conditional_edges(
            "parse_input",
            self._route_by_mode,
            {
                "plan": "plan",
                "chat": "output",
                "explain": "output"
            }
        )
        
        workflow.add_edge("plan", "edit")
        workflow.add_edge("edit", "summarize")
        
        workflow.add_conditional_edges(
            "summarize",
            self._should_continue,
            {
                "continue": "output",
                "end": END
            }
        )
        
        workflow.add_edge("output", END)
        
        return workflow.compile()
    
    def _parse_input_node(self, state: AgentState) -> AgentState:
        """Parse user input and determine action."""
        state["mode"] = self.memory.session_state.mode
        return state
    
    def _plan_node(self, state: AgentState) -> AgentState:
        """Create a plan for the task."""
        mode = state["mode"]
        task = state["task"]
        
        # Get context
        context = self.memory.get_context_summary()
        project_context = self.memory.project_context
        
        # Create planning prompt
        prompt = f"""You are Locopilot, an agentic coding assistant.
        
Mode: {mode}
Task: {task}

Project Context:
{project_context.get('file_tree', 'No file tree available')}

Recent Context:
{context}

Create a step-by-step plan to accomplish this task. Be specific about which files to create/edit.
Format your response as a numbered list."""
        
        # Get plan from LLM
        plan = self.llm.invoke(prompt)
        state["plan"] = plan
        
        return state
    
    def _edit_node(self, state: AgentState) -> AgentState:
        """Execute file edits based on the plan."""
        plan = state.get("plan", "")
        task = state["task"]
        
        # For now, we'll simulate file edits
        # In a real implementation, this would parse the plan and execute edits
        
        edits = []
        
        # Example edit (this would be dynamic based on plan parsing)
        edit_prompt = f"""Based on this plan:
{plan}

And this task: {task}

What specific file changes need to be made? List each file and the changes."""
        
        edit_response = self.llm.invoke(edit_prompt)
        
        # Track the edit
        self.memory.add_file_edit(
            file_path="simulated_file.py",
            action="edit",
            content=edit_response
        )
        
        edits.append({
            "file": "simulated_file.py",
            "action": "edit",
            "content": edit_response
        })
        
        state["edits"] = edits
        return state
    
    def _summarize_node(self, state: AgentState) -> AgentState:
        """Check if memory should be summarized."""
        if self.memory.should_summarize():
            self.memory.force_summarize()
            state["should_summarize"] = True
        else:
            state["should_summarize"] = False
        
        return state
    
    def _output_node(self, state: AgentState) -> AgentState:
        """Generate final output."""
        mode = state["mode"]
        task = state["task"]
        
        if mode == "chat":
            # Simple chat response
            response = self.llm.invoke(task)
        elif mode == "explain":
            # Explanation mode
            context = self.memory.get_context_summary()
            prompt = f"Explain the following in detail:\n{task}\n\nContext:\n{context}"
            response = self.llm.invoke(prompt)
        else:
            # Do/Refactor mode - summarize what was done
            plan = state.get("plan", "No plan")
            edits = state.get("edits", [])
            
            response = f"Task completed!\n\nPlan:\n{plan}\n\n"
            response += f"Files edited: {len(edits)}"
        
        state["output"] = response
        
        # Add to memory
        self.memory.add_user_message(task)
        self.memory.add_ai_message(response)
        
        return state
    
    def _route_by_mode(self, state: AgentState) -> str:
        """Route based on agent mode."""
        mode = state["mode"]
        
        if mode in ["do", "refactor"]:
            return "plan"
        elif mode in ["chat", "explain"]:
            return "output"
        else:
            return "plan"
    
    def _should_continue(self, state: AgentState) -> str:
        """Determine if we should continue or end."""
        # For now, always continue to output
        return "continue"
    
    def process_task(self, task: str) -> str:
        """Process a user task through the agent workflow."""
        
        # Create initial state
        initial_state = {
            "messages": [],
            "mode": self.memory.session_state.mode,
            "task": task,
            "plan": None,
            "edits": [],
            "should_summarize": False,
            "output": None
        }
        
        # Run the graph
        result = self.graph.invoke(initial_state)
        
        return result.get("output", "Task processing failed.")
    
    def handle_slash_command(self, command: str) -> Optional[str]:
        """Handle slash commands."""
        
        parts = command.split()
        cmd = parts[0].lower()
        
        if cmd == "/help":
            return self._show_help()
        elif cmd == "/model":
            return self._change_model(parts[1] if len(parts) > 1 else None)
        elif cmd == "/change-mode":
            return self._change_mode(parts[1] if len(parts) > 1 else None)
        elif cmd == "/clear":
            self.memory.clear()
            return "[green][/green] Memory cleared"
        elif cmd == "/new":
            self.memory.clear()
            self._init_project_context()
            return "[green][/green] New session started"
        elif cmd == "/concise":
            self.memory.force_summarize()
            return "[green][/green] Context summarized"
        elif cmd == "/end":
            return "exit"
        else:
            return f"[red]Unknown command: {cmd}[/red]"
    
    def _show_help(self) -> str:
        """Show help for slash commands."""
        help_text = """
[bold]Available Commands:[/bold]

/help          - Show this help message
/model [name]  - Change the model (shows current if no name given)
/change-mode   - Change agent mode (do, refactor, explain, chat)
/clear         - Clear conversation memory
/new           - Start a new session
/concise       - Force memory summarization
/end           - Exit Locopilot

[bold]Modes:[/bold]
" do       - Execute coding tasks (default)
" refactor - Refactor existing code
" explain  - Explain code or concepts
" chat     - General conversation
"""
        return help_text
    
    def _change_model(self, new_model: Optional[str]) -> str:
        """Change the current model."""
        if not new_model:
            return f"Current model: [cyan]{self.memory.session_state.model}[/cyan]"
        
        # Update model
        self.config["model"] = new_model
        self.memory.session_state.model = new_model
        
        # Reinitialize LLM
        self.llm = get_llm_client(
            backend=self.config["backend"],
            model=new_model,
            temperature=0.1
        )
        self.memory.llm = self.llm
        
        return f"[green][/green] Model changed to [cyan]{new_model}[/cyan]"
    
    def _change_mode(self, new_mode: Optional[str]) -> str:
        """Change the agent mode."""
        if not new_mode:
            modes = [mode.value for mode in AgentMode]
            current = self.memory.session_state.mode
            return f"Current mode: [cyan]{current}[/cyan]\nAvailable: {', '.join(modes)}"
        
        # Validate mode
        try:
            mode_enum = AgentMode(new_mode)
            self.memory.session_state.mode = new_mode
            return f"[green][/green] Mode changed to [cyan]{new_mode}[/cyan]"
        except ValueError:
            return f"[red]Invalid mode: {new_mode}[/red]"