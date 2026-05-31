"""
Session manager module for JARVIS AI Assistant.

This module provides:
- Session lifecycle management
- Session context management
- Session refresh handling
- Session state tracking
"""

import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
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
    
    def __init__(self):
        """Initialize session manager."""
        self.session: Optional[Any] = None
        self.context: SessionContext = SessionContext()
        self.state: SessionState = SessionState()
        self._refresh_requested = False
        self._refresh_reason = ""
        self._turn_done_event: Optional[asyncio.Event] = None
        
        logger.info("Session manager initialized")
    
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
        logger.info("Session manager reset")


# Global instance
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get the global session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
