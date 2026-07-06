"""
Clipboard History for M.I.C.A AI Assistant.

This module provides clipboard history tracking and management.
"""

import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.logger import get_logger

logger = get_logger(__name__)


class ClipboardEntry:
    """Represents a clipboard entry."""
    
    def __init__(self, content: str, timestamp: Optional[datetime] = None):
        self.content = content
        self.timestamp = timestamp or datetime.now()
        self.content_type = self._detect_content_type(content)
    
    def _detect_content_type(self, content: str) -> str:
        """Detect the type of clipboard content."""
        if content.startswith("http://") or content.startswith("https://"):
            return "url"
        elif content.startswith(("mailto:", "tel:", "ftp://")):
            return "contact"
        elif "\n" in content:
            return "multiline"
        else:
            return "text"


class ClipboardHistory:
    """
    Clipboard history manager.
    
    Tracks clipboard changes and maintains a history of copied items.
    """
    
    def __init__(self, max_entries: int = 100):
        self._history: List[ClipboardEntry] = []
        self._max_entries = max_entries
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_content = ""
        self._lock = threading.Lock()
    
    def _monitor_clipboard(self):
        """Monitor clipboard for changes."""
        try:
            import pyperclip
        except ImportError:
            logger.error("pyperclip not installed, clipboard monitoring disabled")
            return
        
        while self._running and not self._stop_event.is_set():
            try:
                current_content = pyperclip.paste()
                
                if current_content and current_content != self._last_content:
                    with self._lock:
                        entry = ClipboardEntry(current_content)
                        self._history.append(entry)
                        
                        # Trim to max entries
                        if len(self._history) > self._max_entries:
                            self._history = self._history[-self._max_entries:]
                        
                        self._last_content = current_content
                        logger.debug(f"Clipboard entry added: {entry.content_type}")
                
                time.sleep(1)  # Check every second
            except Exception as e:
                logger.error(f"Error monitoring clipboard: {e}")
                time.sleep(5)  # Wait before retrying
    
    def start_monitoring(self):
        """Start monitoring clipboard changes."""
        if self._running:
            logger.warning("Clipboard monitoring already running")
            return
        
        self._running = True
        self._stop_event.clear()
        
        self._monitor_thread = threading.Thread(target=self._monitor_clipboard, daemon=True)
        self._monitor_thread.start()
        
        logger.info("Clipboard monitoring started")
    
    def stop_monitoring(self):
        """Stop monitoring clipboard changes."""
        if not self._running:
            return
        
        self._running = False
        self._stop_event.set()
        
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        
        logger.info("Clipboard monitoring stopped")
    
    def get_history(self, limit: Optional[int] = None) -> List[ClipboardEntry]:
        """
        Get clipboard history.
        
        Args:
            limit: Maximum number of entries to return
            
        Returns:
            List of clipboard entries
        """
        with self._lock:
            if limit:
                return self._history[-limit:]
            return self._history.copy()
    
    def get_recent(self, count: int = 10) -> List[ClipboardEntry]:
        """Get the most recent clipboard entries."""
        return self.get_history(limit=count)
    
    def search(self, query: str) -> List[ClipboardEntry]:
        """
        Search clipboard history.
        
        Args:
            query: Search query
            
        Returns:
            List of matching clipboard entries
        """
        with self._lock:
            query_lower = query.lower()
            return [
                entry for entry in self._history
                if query_lower in entry.content.lower()
            ]
    
    def get_by_type(self, content_type: str) -> List[ClipboardEntry]:
        """
        Get entries by content type.
        
        Args:
            content_type: Type of content (url, text, multiline, contact)
            
        Returns:
            List of matching clipboard entries
        """
        with self._lock:
            return [
                entry for entry in self._history
                if entry.content_type == content_type
            ]
    
    def clear_history(self):
        """Clear all clipboard history."""
        with self._lock:
            self._history.clear()
            logger.info("Clipboard history cleared")
    
    def set_content(self, content: str) -> bool:
        """
        Set clipboard content.
        
        Args:
            content: Content to set
            
        Returns:
            bool: True if successful
        """
        try:
            import pyperclip
            pyperclip.copy(content)
            self._last_content = content
            logger.debug("Clipboard content set")
            return True
        except ImportError:
            logger.error("pyperclip not installed")
            return False
        except Exception as e:
            logger.error(f"Failed to set clipboard content: {e}")
            return False
    
    def is_monitoring(self) -> bool:
        """Check if clipboard monitoring is active."""
        return self._running


# Global clipboard history instance
_clipboard_history: Optional[ClipboardHistory] = None


def get_clipboard_history(max_entries: int = 100) -> ClipboardHistory:
    """
    Get the global clipboard history instance.
    
    Args:
        max_entries: Maximum number of entries to keep
        
    Returns:
        ClipboardHistory: The global clipboard history
    """
    global _clipboard_history
    if _clipboard_history is None:
        _clipboard_history = ClipboardHistory(max_entries=max_entries)
    return _clipboard_history
