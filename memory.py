from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from langchain.memory import ConversationSummaryBufferMemory
from langchain.schema import BaseMessage, HumanMessage, AIMessage
from langchain.base_language import BaseLanguageModel


@dataclass
class SessionState:
    """Represents the current state of a Locopilot session."""
    
    mode: str = "do"
    model: str = ""
    backend: str = ""
    project_path: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def update(self, **kwargs):
        """Update session state fields."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.now()


class LocopilotMemory:
    """Memory management for Locopilot sessions."""
    
    def __init__(
        self,
        llm: BaseLanguageModel,
        max_token_limit: int = 4000,
        summarization_threshold: int = 3000,
    ):
        self.llm = llm
        self.max_token_limit = max_token_limit
        self.summarization_threshold = summarization_threshold
        
        # Initialize conversation memory with summarization
        self.memory = ConversationSummaryBufferMemory(
            llm=llm,
            max_token_limit=max_token_limit,
            return_messages=True,
        )
        
        # Track file edits and context
        self.file_edits: List[Dict[str, Any]] = []
        self.project_context: Dict[str, Any] = {}
        
        # Session state
        self.session_state = SessionState()
    
    def add_user_message(self, content: str):
        """Add a user message to memory."""
        self.memory.chat_memory.add_user_message(content)
    
    def add_ai_message(self, content: str):
        """Add an AI message to memory."""
        self.memory.chat_memory.add_ai_message(content)
    
    def add_file_edit(self, file_path: str, action: str, content: Optional[str] = None):
        """Track a file edit."""
        edit = {
            "file_path": file_path,
            "action": action,  # create, edit, delete
            "timestamp": datetime.now(),
            "content_preview": content[:200] if content else None
        }
        self.file_edits.append(edit)
    
    def set_project_context(self, context: Dict[str, Any]):
        """Set project context information."""
        self.project_context = context
    
    def get_context_summary(self) -> str:
        """Get a summary of the current context."""
        messages = self.memory.chat_memory.messages
        
        if not messages:
            return "No conversation history."
        
        # Get recent messages
        recent_messages = messages[-10:]  # Last 10 messages
        
        summary = "Recent conversation:\n"
        for msg in recent_messages:
            if isinstance(msg, HumanMessage):
                summary += f"User: {msg.content[:100]}...\n"
            elif isinstance(msg, AIMessage):
                summary += f"Assistant: {msg.content[:100]}...\n"
        
        # Add file edit summary
        if self.file_edits:
            summary += f"\nRecent file edits: {len(self.file_edits)} files modified\n"
            for edit in self.file_edits[-5:]:  # Last 5 edits
                summary += f"- {edit['action']} {edit['file_path']}\n"
        
        return summary
    
    def force_summarize(self):
        """Force memory summarization."""
        # This triggers the summarization in ConversationSummaryBufferMemory
        # by simulating that we're over the token limit
        current_buffer = self.memory.buffer
        self.memory.buffer = []
        
        if current_buffer:
            # Add a summary message
            summary = self.llm.invoke(
                f"Summarize this conversation concisely:\n{current_buffer}"
            )
            self.memory.chat_memory.add_ai_message(f"[Summary] {summary}")
    
    def clear(self):
        """Clear all memory."""
        self.memory.clear()
        self.file_edits.clear()
        self.project_context.clear()
    
    def get_formatted_history(self) -> str:
        """Get formatted conversation history."""
        messages = self.memory.chat_memory.messages
        
        formatted = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                formatted.append(f"User: {msg.content}")
            elif isinstance(msg, AIMessage):
                formatted.append(f"Assistant: {msg.content}")
        
        return "\n\n".join(formatted)
    
    def should_summarize(self) -> bool:
        """Check if memory should be summarized based on token count."""
        # Estimate token count (rough approximation)
        total_chars = sum(len(msg.content) for msg in self.memory.chat_memory.messages)
        estimated_tokens = total_chars // 4  # Rough estimate: 4 chars per token
        
        return estimated_tokens > self.summarization_threshold