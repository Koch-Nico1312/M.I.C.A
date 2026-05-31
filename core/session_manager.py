"""
Session manager module for JARVIS AI Assistant.

This module provides:
- Session lifecycle management
- Session context management
- Session refresh handling
- Session state tracking
"""

import asyncio
import threading
from collections import deque
from datetime import datetime
from typing import Optional, Dict, Any, Deque, List
from dataclasses import dataclass, field

from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SessionContext:
    """Context information for a session."""
    prompt_mtime: Optional[float] = None
    memory_mtime: Optional[float] = None
    created_at: datetime = field(default_factory=datetime.now)
    last_refresh: Optional[datetime] = None
    refresh_count: int = 0


@dataclass
class SessionState:
    """Current state of a session."""
    is_connected: bool = False
    is_speaking: bool = False
    is_muted: bool = False
    last_activity: Optional[datetime] = None
    turn_count: int = 0


class SessionManager:
    """
    Manages JARVIS session lifecycle and state.
    """
    
    def __init__(self, max_messages: int = 30, max_tool_results: int = 10):
        """Initialize session manager."""
        self.session: Optional[Any] = None
        self.context: SessionContext = SessionContext()
        self.state: SessionState = SessionState()
        self._refresh_requested = False
        self._refresh_reason = ""
        self._turn_done_event: Optional[asyncio.Event] = None
        self.max_messages = max_messages
        self.max_tool_results = max_tool_results
        self._messages: Deque[Dict[str, Any]] = deque(maxlen=max_messages)
        self._tool_results: Deque[Dict[str, Any]] = deque(maxlen=max_tool_results)
        self._session_token: Optional[str] = None
        self._session_start: Optional[datetime] = None
        self._reconnect_count = 0
        self._context_lock = threading.Lock()
        
        logger.info("Session manager initialized")

    def start_session(self) -> None:
        """Mark the start of a new session."""
        self._session_start = datetime.now()
        logger.info("[Session] New session started")

    def record_user_message(self, text: str) -> None:
        """Record a user message."""
        if not text or not text.strip():
            return
        with self._context_lock:
            self._messages.append({
                "role": "user",
                "content": text.strip(),
                "timestamp": datetime.now().isoformat(),
            })

    def record_jarvis_response(self, text: str) -> None:
        """Record a JARVIS response."""
        if not text or not text.strip():
            return
        with self._context_lock:
            self._messages.append({
                "role": "jarvis",
                "content": text.strip(),
                "timestamp": datetime.now().isoformat(),
            })

    def record_tool_execution(self, tool_name: str, args: dict, result: str) -> None:
        """Record a tool execution result."""
        with self._context_lock:
            self._tool_results.append({
                "tool": tool_name,
                "args_summary": str(args)[:200],
                "result_summary": str(result)[:300],
                "timestamp": datetime.now().isoformat(),
            })

    def save_session_token(self, token: str) -> None:
        """Save Gemini session resumption token."""
        self._session_token = token

    def get_session_token(self) -> Optional[str]:
        """Get saved session resumption token."""
        return self._session_token

    def mark_reconnect(self) -> None:
        """Mark that a reconnection occurred."""
        self._reconnect_count += 1
        logger.info(f"[Session] Reconnection #{self._reconnect_count}")

    def build_context_summary(self) -> str:
        """Build a context summary string for reconnect prompt injection."""
        with self._context_lock:
            if not self._messages and not self._tool_results:
                return ""

            lines: List[str] = []
            lines.append("[CONVERSATION CONTEXT — Resumed session, continue naturally]")
            lines.append(f"Session reconnection #{self._reconnect_count}. Continue as if uninterrupted.")
            lines.append("")

            if self._messages:
                lines.append("Recent conversation:")
                for msg in list(self._messages)[-15:]:
                    role = "User" if msg["role"] == "user" else "JARVIS"
                    content = str(msg["content"])[:250]
                    lines.append(f"  {role}: {content}")
                lines.append("")

            if self._tool_results:
                lines.append("Recent actions taken:")
                for tool in list(self._tool_results)[-5:]:
                    lines.append(f"  - {tool['tool']}: {str(tool['result_summary'])[:150]}")
                lines.append("")

            lines.append("Continue the conversation naturally. Do NOT say 'welcome back' or mention reconnection.")

            result = "\n".join(lines)
            if len(result) > 2500:
                result = result[:2497] + "..."
            return result + "\n"

    def clear(self) -> None:
        """Clear all reconnect context."""
        with self._context_lock:
            self._messages.clear()
            self._tool_results.clear()
            self._session_token = None
            self._reconnect_count = 0
    
    def set_session(self, session: Any) -> None:
        """
        Set the active session.
        
        Args:
            session: Gemini Live session
        """
        self.session = session
        self.state.is_connected = True
        self.state.last_activity = datetime.now()
        logger.info("Session set")
    
    def close_session(self) -> None:
        """Close the current session."""
        if self.session:
            try:
                asyncio.create_task(self.session.close())
            except Exception as e:
                logger.error(f"Error closing session: {e}")
        
        self.session = None
        self.state.is_connected = False
        logger.info("Session closed")
    
    def update_context_signature(self, prompt_mtime: Optional[float], memory_mtime: Optional[float]) -> None:
        """
        Update context signature from file modification times.
        
        Args:
            prompt_mtime: Prompt file modification time
            memory_mtime: Memory file modification time
        """
        self.context.prompt_mtime = prompt_mtime
        self.context.memory_mtime = memory_mtime
        logger.debug("Context signature updated")
    
    def get_context_signature(self) -> tuple[Optional[float], Optional[float]]:
        """
        Get current context signature.
        
        Returns:
            Tuple of (prompt_mtime, memory_mtime)
        """
        return self.context.prompt_mtime, self.context.memory_mtime
    
    def request_refresh(self, reason: str) -> None:
        """
        Request a session context refresh.
        
        Args:
            reason: Reason for refresh
        """
        self._refresh_requested = True
        self._refresh_reason = reason
        logger.info(f"Session refresh requested: {reason}")
    
    async def apply_pending_refresh(self) -> None:
        """Apply pending session refresh if requested."""
        if not self._refresh_requested or not self.session:
            return
        
        reason = self._refresh_reason or "Context updated."
        self._refresh_requested = False
        self._refresh_reason = ""
        
        self.context.last_refresh = datetime.now()
        self.context.refresh_count += 1
        
        logger.info(f"Applying session refresh: {reason}")
        await self.session.close()
    
    def set_turn_done_event(self, event: asyncio.Event) -> None:
        """
        Set the turn completion event.
        
        Args:
            event: Async event for turn completion
        """
        self._turn_done_event = event
    
    def signal_turn_complete(self) -> None:
        """Signal that the current turn is complete."""
        if self._turn_done_event:
            self._turn_done_event.set()
            self.state.turn_count += 1
            logger.debug(f"Turn complete (total: {self.state.turn_count})")
    
    def clear_turn_done_event(self) -> None:
        """Clear the turn completion event."""
        if self._turn_done_event:
            self._turn_done_event.clear()
    
    def set_speaking(self, is_speaking: bool) -> None:
        """
        Set speaking state.
        
        Args:
            is_speaking: Speaking state
        """
        self.state.is_speaking = is_speaking
        if is_speaking:
            self.state.last_activity = datetime.now()
    
    def set_muted(self, is_muted: bool) -> None:
        """
        Set muted state.
        
        Args:
            is_muted: Muted state
        """
        self.state.is_muted = is_muted
    
    def is_speaking(self) -> bool:
        """Check if currently speaking."""
        return self.state.is_speaking
    
    def is_muted(self) -> bool:
        """Check if currently muted."""
        return self.state.is_muted
    
    def is_connected(self) -> bool:
        """Check if session is connected."""
        return self.state.is_connected
    
    def get_session_info(self) -> Dict[str, Any]:
        """
        Get session information.
        
        Returns:
            Dictionary with session information
        """
        return {
            "connected": self.state.is_connected,
            "speaking": self.state.is_speaking,
            "muted": self.state.is_muted,
            "turn_count": self.state.turn_count,
            "last_activity": self.state.last_activity.isoformat() if self.state.last_activity else None,
            "context_refreshes": self.context.refresh_count,
            "last_refresh": self.context.last_refresh.isoformat() if self.context.last_refresh else None,
            "refresh_pending": self._refresh_requested
        }
    
    def reset(self) -> None:
        """Reset session manager state."""
        self.session = None
        self.context = SessionContext()
        self.state = SessionState()
        self._refresh_requested = False
        self._refresh_reason = ""
        self._turn_done_event = None
        self.clear()
        logger.info("Session manager reset")


class SessionContextManager(SessionManager):
    """
    Maintains conversation context across Gemini Live reconnections.
    """


# Global instance
_session_manager: Optional[SessionContextManager] = None


def get_session_manager() -> SessionContextManager:
    """Get the global session manager instance."""
    global _session_manager
    if _session_manager is None:
        try:
            from config.config_loader import get_config

            config = get_config()
            max_messages = int(config.get("session.max_messages", 30))
            max_tool_results = int(config.get("session.max_tool_results", 10))
        except Exception:
            max_messages = 30
            max_tool_results = 10
        _session_manager = SessionContextManager(
            max_messages=max_messages,
            max_tool_results=max_tool_results,
        )
    return _session_manager
