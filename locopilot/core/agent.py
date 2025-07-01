import os
from pathlib import Path
from typing import Dict, Any, List, Optional, TypedDict
from enum import Enum

from langchain.agents import AgentExecutor
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import Tool
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain.schema.runnable import RunnablePassthrough
from langgraph.graph import StateGraph, END
from rich.console import Console

from locopilot.llm.connection import get_llm_client
from locopilot.core.memory import LocopilotMemory, SessionState
from locopilot.utils.file_ops import (
    get_project_files,
    read_file_content,
    create_file_edit_prompt,
    format_file_tree
)
from locopilot.core.executor import PlanExecutor, PlanAction, ActionType


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
    errors: Optional[List[str]]


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
        
        # Initialize plan executor
        self.plan_executor = PlanExecutor(project_path, dry_run=False)
        
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
        workflow.add_node("planning", self._plan_node)
        workflow.add_node("edit", self._edit_node)
        workflow.add_node("summarize", self._summarize_node)
        workflow.add_node("generate_output", self._output_node)
        
        # Add edges
        workflow.set_entry_point("parse_input")
        
        # Conditional routing based on mode
        workflow.add_conditional_edges(
            "parse_input",
            self._route_by_mode,
            {
                "planning": "planning",
                "generate_output": "generate_output"
            }
        )
        
        workflow.add_edge("planning", "edit")
        workflow.add_edge("edit", "summarize")
        
        workflow.add_conditional_edges(
            "summarize",
            self._should_continue,
            {
                "continue": "generate_output",
                "end": END
            }
        )
        
        workflow.add_edge("generate_output", END)
        
        return workflow.compile()
    
    def _parse_input_node(self, state: AgentState) -> AgentState:
        """Parse user input and determine action mode."""
        task = state["task"].strip()
        task_lower = task.lower()
        
        # Patterns for different modes
        conversational_patterns = [
            "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
            "how are you", "what's up", "thanks", "thank you", "bye", "goodbye",
            "help", "what can you do", "who are you", "what are you"
        ]
        
        explain_patterns = [
            "explain", "what is", "how does", "why does", "describe", "tell me about",
            "what are", "how do", "what's the difference", "compare"
        ]
        
        action_patterns = [
            "create", "make", "add", "delete", "remove", "edit", "modify", "update",
            "run", "execute", "build", "install", "setup", "configure", "fix",
            "refactor", "optimize", "implement", "write", "generate"
        ]
        
        # Determine mode based on content
        if any(pattern in task_lower for pattern in conversational_patterns):
            state["mode"] = "chat"
        elif any(pattern in task_lower for pattern in explain_patterns):
            state["mode"] = "explain"
        elif any(pattern in task_lower for pattern in action_patterns):
            state["mode"] = "do"
        elif len(task.split()) <= 3:
            # Short messages default to chat
            state["mode"] = "chat"
        else:
            # Use session default mode
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
        prompt = f"""You are Locopilot, an expert coding assistant that executes tasks precisely.

Current Mode: {mode}
Task to Complete: {task}

Available Project Files:
{project_context.get('file_tree', 'No file tree available')}

Previous Context:
{context if context else 'No previous context'}

Instructions:
Create a concrete action plan to complete this task. Each step must be a specific, executable action.

Action Types:
1. DELETE FILE: "Delete file: path/to/file.ext"
2. CREATE FILE: "Create file: path/to/file.ext"
3. EDIT FILE: "Edit file: path/to/file.ext - Replace X with Y" or "Edit file: path/to/file.ext - Add X after Y"
4. RUN COMMAND: "Run command: exact_command_here"
5. CREATE DIRECTORY: "Create directory: path/to/directory"

Rules:
- Use exact file paths as they appear in the project
- For deletions, just specify the file path
- For creations, the content will be generated based on the task
- For edits, be specific about what to change
- For commands, provide the exact command to run
- Keep the plan concise - only include necessary steps

Example Plan:
1. Delete file: old_module.py
2. Create file: src/new_module.py
3. Edit file: src/main.py - Add import for new_module
4. Run command: python -m pytest tests/

Your Plan:"""
        
        # Get plan from LLM
        llm_response = self.llm.invoke(prompt)
        plan = str(llm_response.content) if hasattr(llm_response, 'content') else str(llm_response)
        state["plan"] = plan
        
        return state
    
    def _edit_node(self, state: AgentState) -> AgentState:
        """Execute file edits based on the plan."""
        plan = state.get("plan", "")
        task = state["task"]
        mode = state["mode"]
        
        # Import at function level to avoid circular imports
        from locopilot.core.executor import PlanAction, ActionType
        
        # Generate specific actions from the plan
        action_prompt = f"""Convert this plan into executable JSON actions:

PLAN:
{plan}

ORIGINAL TASK: {task}

CONVERSION RULES:
Transform each plan step into a JSON action object. Use these exact action_type values:

1. "delete_file" - For deleting files
   Required: action_type, target, description
   
2. "create_file" - For creating new files  
   Required: action_type, target, description
   Optional: content (will be generated if not provided)
   
3. "edit_file" - For modifying existing files
   Required: action_type, target, description
   Optional: old_content, new_content, content
   
4. "run_bash" - For shell commands
   Required: action_type, command, description
   Set target to "bash"
   
5. "create_dir" - For creating directories
   Required: action_type, target, description

EXAMPLES:
Plan: "Delete file: .coverage"
JSON: {{"action_type": "delete_file", "target": ".coverage", "description": "Delete coverage file"}}

Plan: "Create file: src/utils.py"  
JSON: {{"action_type": "create_file", "target": "src/utils.py", "description": "Create utility functions module"}}

Plan: "Run command: pytest tests/"
JSON: {{"action_type": "run_bash", "command": "pytest tests/", "target": "bash", "description": "Run tests"}}

OUTPUT FORMAT (JSON only, no markdown or extra text):
{{
    "actions": [
        {{"action_type": "...", "target": "...", "description": "..."}}
    ]
}}"""
        
        llm_response = self.llm.invoke(action_prompt)
        action_response = str(llm_response.content) if hasattr(llm_response, 'content') else str(llm_response)
        
        try:
            # Extract JSON from response
            import json
            import re
            
            # Log the raw response for debugging
            console.print(f"[dim]Debug - LLM response:[/dim] {action_response[:200]}...")
            
            # Find JSON in the response
            json_match = re.search(r'\{[\s\S]*\}', action_response)
            if json_match:
                json_str = json_match.group()
                console.print(f"[dim]Debug - Found JSON:[/dim] {json_str[:200]}...")
                
                action_data = json.loads(json_str)
                actions = self.plan_executor.parse_plan_from_json(action_data)
                
                # Generate content for file creation actions that don't have content
                for action in actions:
                    if action.action_type == ActionType.CREATE_FILE and not action.content:
                        action.content = self._generate_file_content(action.target, task, plan)
                
                # Execute the plan
                console.print(f"\n[bold cyan]Executing {len(actions)} actions...[/bold cyan]")
                results = self.plan_executor.execute_plan(actions)
                
                # Track successful edits in memory
                for action_dict in results["executed"]:
                    if action_dict["action_type"] in ["create_file", "edit_file", "delete_file"]:
                        self.memory.add_file_edit(
                            file_path=action_dict["target"],
                            action=action_dict["action_type"],
                            content=action_dict.get("content", "")
                        )
                
                state["edits"] = results["executed"]
                
                # If execution failed, add error info
                if not results["success"]:
                    state["errors"] = results["errors"]
            else:
                # Fallback - try to extract actions from plan directly
                console.print("[yellow]Warning: No JSON found in response, attempting intelligent parsing[/yellow]")
                
                actions = self._parse_plan_fallback(plan, task)
                if actions:
                    results = self.plan_executor.execute_plan(actions)
                    state["edits"] = results["executed"]
                else:
                    state["edits"] = [{
                        "file": "simulated_action",
                        "action": "plan_generated", 
                        "content": f"Plan created but not executed: {plan}"
                    }]
                
        except json.JSONDecodeError as e:
            console.print(f"[red]JSON parsing error: {str(e)}[/red]")
            console.print(f"[red]Response was: {action_response[:500]}[/red]")
            state["edits"] = []
            state["errors"] = [f"JSON parsing error: {str(e)}"]
        except Exception as e:
            console.print(f"[red]Error executing plan: {str(e)}[/red]")
            state["edits"] = []
            state["errors"] = [str(e)]
        
        return state
    
    def _generate_file_content(self, file_path: str, task: str, plan: str) -> str:
        """Generate content for a file based on the task and plan."""
        file_extension = Path(file_path).suffix.lower()
        
        # Determine file type and generate appropriate content
        content_prompt = f"""Generate content for this file based on the task and plan.

File Path: {file_path}
File Type: {file_extension}
Original Task: {task}
Plan Context: {plan}

Requirements:
- Generate appropriate content for the file type ({file_extension})
- Content should fulfill the purpose described in the task/plan
- Follow best practices for the language/file type
- Include necessary imports, docstrings, and structure
- Keep it functional and well-commented

For Python files (.py): Include proper imports, functions/classes with docstrings
For JavaScript files (.js/.ts): Include proper modules, functions with JSDoc
For HTML files (.html): Include proper structure with head/body
For CSS files (.css): Include organized styles with comments
For Markdown files (.md): Include proper headers and formatting
For configuration files: Include appropriate settings and comments
For text files: Include relevant content based on the context

Generate only the file content, no explanations or markdown formatting:"""

        llm_response = self.llm.invoke(content_prompt)
        content = str(llm_response.content) if hasattr(llm_response, 'content') else str(llm_response)
        
        # Clean up the content (remove markdown code blocks if present)
        import re
        content = re.sub(r'^```\w*\n', '', content)
        content = re.sub(r'\n```$', '', content)
        
        return content.strip()
    
    def _parse_plan_fallback(self, plan: str, task: str) -> List:
        """Fallback parser for extracting actions from plan text."""
        from locopilot.core.executor import PlanAction, ActionType
        import re
        
        actions = []
        plan_lines = plan.split('\n')
        
        for line in plan_lines:
            line = line.strip()
            if not line or not any(char.isalpha() for char in line):
                continue
                
            line_lower = line.lower()
            
            # Delete file patterns
            delete_patterns = [
                r'delete\s+file[:\s]+([^\s]+)',
                r'remove\s+([^\s]+)',
                r'rm\s+([^\s]+)',
                r'delete\s+([^\s]+)'
            ]
            
            for pattern in delete_patterns:
                match = re.search(pattern, line_lower)
                if match:
                    filename = match.group(1).strip('\"\'')
                    actions.append(PlanAction(
                        action_type=ActionType.DELETE_FILE,
                        target=filename,
                        description=f"Delete {filename}"
                    ))
                    break
            
            # Create file patterns
            create_patterns = [
                r'create\s+file[:\s]+([^\s]+)',
                r'make\s+([^\s\.]+\.[a-z]+)',
                r'add\s+([^\s\.]+\.[a-z]+)',
                r'new\s+file[:\s]+([^\s]+)'
            ]
            
            for pattern in create_patterns:
                match = re.search(pattern, line_lower)
                if match:
                    filename = match.group(1).strip('\"\'')
                    actions.append(PlanAction(
                        action_type=ActionType.CREATE_FILE,
                        target=filename,
                        description=f"Create {filename}"
                    ))
                    break
            
            # Run command patterns
            command_patterns = [
                r'run\s+command[:\s]+(.+)',
                r'execute[:\s]+(.+)',
                r'run[:\s]+(.+)'
            ]
            
            for pattern in command_patterns:
                match = re.search(pattern, line_lower)
                if match:
                    command = match.group(1).strip('\"\'')
                    actions.append(PlanAction(
                        action_type=ActionType.RUN_BASH,
                        command=command,
                        target="bash",
                        description=f"Run: {command}"
                    ))
                    break
        
        # If no actions found, try simple keyword matching on the original task
        if not actions:
            task_lower = task.lower()
            if "delete" in task_lower or "remove" in task_lower:
                # Look for file extensions or common filenames
                import re
                file_matches = re.findall(r'([^\s]+\.[a-z]+)', task)
                for filename in file_matches:
                    actions.append(PlanAction(
                        action_type=ActionType.DELETE_FILE,
                        target=filename,
                        description=f"Delete {filename}"
                    ))
        
        return actions
    
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
            # Enhanced chat response with context
            prompt = f"""You are Locopilot, an expert coding assistant with a friendly personality.

User: {task}

Context: You can help with coding tasks including:
- Creating, editing, and deleting files
- Running bash commands and scripts
- Code refactoring and optimization
- Explaining code concepts
- Setting up project structures
- Writing tests and documentation

Respond naturally and helpfully. If the user is asking about a coding task, offer to help execute it. Keep your response conversational and engaging."""
            llm_response = self.llm.invoke(prompt)
            response = str(llm_response.content) if hasattr(llm_response, 'content') else str(llm_response)
        elif mode == "explain":
            # Explanation mode
            context = self.memory.get_context_summary()
            prompt = f"""You are Locopilot, an expert coding assistant in explanation mode.

Topic to Explain: {task}

Project Context:
{context if context else 'No previous context available'}

Instructions:
Provide a clear, comprehensive explanation that includes:
1. Core concepts and definitions
2. How it works or why it's important
3. Practical examples relevant to coding
4. Common use cases or best practices
5. Potential pitfalls or considerations

Structure your explanation logically and use examples where helpful. Tailor the depth to the complexity of the topic."""
            llm_response = self.llm.invoke(prompt)
            response = str(llm_response.content) if hasattr(llm_response, 'content') else str(llm_response)
        else:
            # Do/Refactor mode - summarize what was done
            plan = state.get("plan", "No plan")
            edits = state.get("edits", [])
            errors = state.get("errors", [])
            
            response = f"Task completed!\n\nPlan:\n{plan}\n\n"
            
            if edits:
                response += "Actions executed:\n"
                for edit in edits:
                    action_type = edit.get("action_type", edit.get("action", "unknown"))
                    target = edit.get("target", edit.get("file", "unknown"))
                    
                    if action_type == "create_file":
                        response += f"  ✓ Created file: {target}\n"
                    elif action_type == "edit_file":
                        response += f"  ✓ Edited file: {target}\n"
                    elif action_type == "delete_file":
                        response += f"  ✓ Deleted file: {target}\n"
                    elif action_type == "run_bash":
                        response += f"  ✓ Ran command: {edit.get('command', 'unknown')}\n"
                    elif action_type == "create_dir":
                        response += f"  ✓ Created directory: {target}\n"
                    else:
                        response += f"  ✓ {action_type}: {target}\n"
            else:
                response += "No actions were executed.\n"
            
            if errors:
                response += "\nErrors encountered:\n"
                for error in errors:
                    response += f"  ✗ {error}\n"
        
        state["output"] = response
        
        # Add to memory
        self.memory.add_user_message(task)
        self.memory.add_ai_message(response)
        
        return state
    
    def _route_by_mode(self, state: AgentState) -> str:
        """Route based on agent mode."""
        mode = state["mode"]
        
        if mode in ["do", "refactor"]:
            return "planning"
        elif mode in ["chat", "explain"]:
            return "generate_output"
        else:
            return "planning"
    
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
            "output": None,
            "errors": None
        }
        
        # Run the graph
        result = self.graph.invoke(initial_state)
        
        return result.get("output", "Task processing failed.")
    
    def process_task_streaming(self, task: str):
        """Process a user task with streaming output."""
        
        # Check if this looks like a conversational message
        task_lower = task.lower().strip()
        conversational_patterns = [
            "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
            "how are you", "what's up", "thanks", "thank you", "bye", "goodbye",
            "help", "what can you do", "who are you", "what are you"
        ]
        
        # Determine if this should be streamed
        is_conversational = any(pattern in task_lower for pattern in conversational_patterns) or len(task_lower.split()) <= 3
        
        if is_conversational:
            # Stream chat response directly
            prompt = f"""You are Locopilot, an expert coding assistant with a warm, helpful personality.

User: {task}

You excel at:
- Creating and modifying files
- Running commands and scripts  
- Code analysis and refactoring
- Project setup and organization
- Debugging and testing

Respond naturally and offer specific help if appropriate. Be concise but engaging."""
            
            complete_response = ""
            for chunk in self.llm.stream(prompt):
                # OllamaLLM returns strings directly, not objects
                chunk_text = str(chunk)
                complete_response += chunk_text
                yield chunk_text
                # No delay for immediate streaming
            
            # Update memory
            self.memory.add_user_message(task)
            self.memory.add_ai_message(complete_response)
        else:
            # For non-conversational tasks, use the normal workflow
            response = self.process_task(task)
            yield response
    
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
            return "[green]✓[/green] Memory cleared"
        elif cmd == "/new":
            self.memory.clear()
            self._init_project_context()
            return "[green]✓[/green] New session started"
        elif cmd == "/concise":
            self.memory.force_summarize()
            return "[green]✓[/green] Context summarized"
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
• do       - Execute coding tasks (default)
• refactor - Refactor existing code
• explain  - Explain code or concepts
• chat     - General conversation
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
        
        return f"[green]✓[/green] Model changed to [cyan]{new_model}[/cyan]"
    
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
            return f"[green]✓[/green] Mode changed to [cyan]{new_mode}[/cyan]"
        except ValueError:
            return f"[red]Invalid mode: {new_mode}[/red]"