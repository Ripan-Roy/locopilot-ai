from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.language_models import BaseLanguageModel


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
        
        # Manual message management instead of deprecated memory
        self.messages: List[BaseMessage] = []
        self.summary: Optional[str] = None
        
        # Track file edits and context
        self.file_edits: List[Dict[str, Any]] = []
        self.project_context: Dict[str, Any] = {}
        
        # Session state
        self.session_state = SessionState()
    
    def add_user_message(self, content: str):
        """Add a user message to memory."""
        self.messages.append(HumanMessage(content=content))
        if self.should_summarize():
            self._summarize()
    
    def add_ai_message(self, content: str):
        """Add an AI message to memory."""
        self.messages.append(AIMessage(content=content))
        if self.should_summarize():
            self._summarize()
    
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
        if not self.messages and not self.summary:
            return "No conversation history."
        
        context_parts = []
        
        # Include summary if available
        if self.summary:
            context_parts.append(f"Previous conversation summary:\n{self.summary}")
        
        # Get recent messages
        recent_messages = self.messages[-10:]  # Last 10 messages
        if recent_messages:
            context_parts.append("Recent conversation:")
            for msg in recent_messages:
                if isinstance(msg, HumanMessage):
                    context_parts.append(f"User: {msg.content[:100]}...")
                elif isinstance(msg, AIMessage):
                    context_parts.append(f"Assistant: {msg.content[:100]}...")
        
        # Add file edit summary
        if self.file_edits:
            context_parts.append(f"\nRecent file edits: {len(self.file_edits)} files modified")
            for edit in self.file_edits[-5:]:  # Last 5 edits
                context_parts.append(f"- {edit['action']} {edit['file_path']}")
        
        return "\n".join(context_parts)
    
    def _summarize(self):
        """Internal method to summarize and compress memory."""
        if len(self.messages) <= 10:  # Keep at least 10 messages
            return
            
        # Get messages to summarize (all but the last 10)
        messages_to_summarize = self.messages[:-10]
        recent_messages = self.messages[-10:]
        
        if not messages_to_summarize:
            return
        
        # Create summary prompt
        conversation_text = ""
        for msg in messages_to_summarize:
            if isinstance(msg, HumanMessage):
                conversation_text += f"User: {msg.content}\n"
            elif isinstance(msg, AIMessage):
                conversation_text += f"Assistant: {msg.content}\n"
        
        summary_prompt = f"""Summarize this conversation concisely, focusing on key tasks, decisions, and context:

{conversation_text}

Summary:"""
        
        try:
            new_summary = self.llm.invoke(summary_prompt)
            if isinstance(new_summary, str):
                summary_text = new_summary
            else:
                summary_text = str(new_summary.content) if hasattr(new_summary, 'content') else str(new_summary)
            
            # Combine with existing summary if available
            if self.summary:
                combined_prompt = f"""Combine these two conversation summaries into one concise summary:

Previous summary:
{self.summary}

New summary:
{summary_text}

Combined summary:"""
                combined_summary = self.llm.invoke(combined_prompt)
                if isinstance(combined_summary, str):
                    self.summary = combined_summary
                else:
                    self.summary = str(combined_summary.content) if hasattr(combined_summary, 'content') else str(combined_summary)
            else:
                self.summary = summary_text
            
            # Keep only recent messages
            self.messages = recent_messages
            
        except Exception as e:
            print(f"Warning: Failed to summarize conversation: {e}")
    
    def force_summarize(self):
        """Force memory summarization."""
        self._summarize()
    
    def clear(self):
        """Clear all memory."""
        self.messages.clear()
        self.summary = None
        self.file_edits.clear()
        self.project_context.clear()
    
    def get_formatted_history(self) -> str:
        """Get formatted conversation history."""
        formatted = []
        
        if self.summary:
            formatted.append(f"[Previous Summary]: {self.summary}")
            formatted.append("---")
        
        for msg in self.messages:
            if isinstance(msg, HumanMessage):
                formatted.append(f"User: {msg.content}")
            elif isinstance(msg, AIMessage):
                formatted.append(f"Assistant: {msg.content}")
        
        return "\n\n".join(formatted)
    
    def should_summarize(self) -> bool:
        """Check if memory should be summarized based on token count."""
        if len(self.messages) <= 10:
            return False
            
        # Estimate token count (rough approximation)
        total_chars = sum(len(msg.content) for msg in self.messages)
        if self.summary:
            total_chars += len(self.summary)
        estimated_tokens = total_chars // 4  # Rough estimate: 4 chars per token
        
        return estimated_tokens > self.summarization_threshold