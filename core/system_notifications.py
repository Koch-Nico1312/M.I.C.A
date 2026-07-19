"""
System Notifications for M.I.C.A AI Assistant.

This module provides a cross-platform notification system for displaying
desktop notifications to the user.
"""

import platform
from typing import Optional

from core.logger import get_logger

logger = get_logger(__name__)


class NotificationPriority:
    """Notification priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class SystemNotifier:
    """
    Cross-platform system notification manager.
    
    Supports:
    - Windows: Toast notifications
    - macOS: Notification Center
    - Linux: libnotify
    """
    
    def __init__(self):
        self._platform = platform.system()
        self._notifier = None
        self._initialize_notifier()
    
    def _initialize_notifier(self):
        """Initialize the platform-specific notifier."""
        try:
            if self._platform == "Windows":
                self._initialize_windows()
            elif self._platform == "Darwin":
                self._initialize_macos()
            elif self._platform == "Linux":
                self._initialize_linux()
            else:
                logger.warning(f"Unsupported platform: {self._platform}")
        except Exception as e:
            logger.error(f"Failed to initialize notifier: {e}")
    
    def _initialize_windows(self):
        """Initialize Windows toast notifications."""
        try:
            from win10toast import ToastNotifier
            self._notifier = ToastNotifier()
            logger.info("Windows toast notifier initialized")
        except ImportError:
            logger.warning("win10toast not installed, notifications disabled")
    
    def _initialize_macos(self):
        """Initialize macOS Notification Center."""
        try:
            import pync
            self._notifier = pync
            logger.info("macOS notifier initialized")
        except ImportError:
            logger.warning("pync not installed, notifications disabled")
    
    def _initialize_linux(self):
        """Initialize Linux libnotify."""
        try:
            import notify2
            notify2.init("M.I.C.A")
            self._notifier = notify2
            logger.info("Linux notifier initialized")
        except ImportError:
            logger.warning("notify2 not installed, notifications disabled")
    
    def notify(
        self,
        title: str,
        message: str,
        priority: str = NotificationPriority.NORMAL,
        icon: Optional[str] = None,
        timeout: int = 5
    ) -> bool:
        """
        Display a system notification.
        
        Args:
            title: Notification title
            message: Notification message
            priority: Notification priority (low, normal, high, urgent)
            icon: Path to icon file
            timeout: Timeout in seconds
            
        Returns:
            bool: True if notification was displayed, False otherwise
        """
        if not self._notifier:
            logger.warning("Notifier not available, logging notification instead")
            logger.info(f"[NOTIFICATION] {title}: {message}")
            return False
        
        try:
            if self._platform == "Windows":
                return self._notify_windows(title, message, icon, timeout)
            elif self._platform == "Darwin":
                return self._notify_macos(title, message, priority, timeout)
            elif self._platform == "Linux":
                return self._notify_linux(title, message, priority, icon, timeout)
            return False
        except Exception as e:
            logger.error(f"Failed to display notification: {e}")
            return False
    
    def _notify_windows(self, title: str, message: str, icon: Optional[str], timeout: int) -> bool:
        """Display Windows toast notification."""
        try:
            self._notifier.show_toast(
                title=title,
                msg=message,
                icon_path=icon,
                duration=timeout
            )
            return True
        except Exception as e:
            logger.error(f"Windows notification failed: {e}")
            return False
    
    def _notify_macos(self, title: str, message: str, priority: str, timeout: int) -> bool:
        """Display macOS notification."""
        try:
            self._notifier.notify(
                title=title,
                message=message,
                sound=True if priority == NotificationPriority.URGENT else False
            )
            return True
        except Exception as e:
            logger.error(f"macOS notification failed: {e}")
            return False
    
    def _notify_linux(self, title: str, message: str, priority: str, icon: Optional[str], timeout: int) -> bool:
        """Display Linux notification."""
        try:
            n = self._notifier.Notification(title, message, icon)
            n.set_timeout(timeout * 1000)
            n.show()
            return True
        except Exception as e:
            logger.error(f"Linux notification failed: {e}")
            return False
    
    def is_available(self) -> bool:
        """Check if notifications are available."""
        return self._notifier is not None


# Global notifier instance
_notifier: Optional[SystemNotifier] = None


def get_system_notifier() -> SystemNotifier:
    """
    Get the global system notifier instance.
    
    Returns:
        SystemNotifier: The global system notifier
    """
    global _notifier
    if _notifier is None:
        _notifier = SystemNotifier()
    return _notifier


def notify(title: str, message: str, priority: str = NotificationPriority.NORMAL) -> bool:
    """
    Convenience function to display a notification.
    
    Args:
        title: Notification title
        message: Notification message
        priority: Notification priority
        
    Returns:
        bool: True if notification was displayed
    """
    from core.notification_center import get_notification_center

    notifier = get_system_notifier()
    event = get_notification_center().publish(
        title,
        message,
        priority,
        source="system_notifications",
        deliver=lambda: notifier.notify(title, message, priority),
    )
    return event.get("status") == "delivered"
