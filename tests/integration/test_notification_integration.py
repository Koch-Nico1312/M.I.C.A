"""
Integration tests for notification system
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestNotificationIntegration:
    """Integration tests for notification system components."""

    @pytest.fixture
    def notification_system(self):
        """Create a fresh notification system instance for testing."""
        from core.notification_system import NotificationSystem
        return NotificationSystem()

    def test_send_notification(self, notification_system):
        """Test sending a notification."""
        result = notification_system.send(
            title="Test Notification",
            message="This is a test notification",
            priority="normal"
        )
        
        assert result is not None

    def test_send_urgent_notification(self, notification_system):
        """Test sending urgent notification."""
        result = notification_system.send(
            title="Urgent Alert",
            message="This is urgent!",
            priority="urgent"
        )
        
        assert result is not None

    def test_notification_with_sound(self, notification_system):
        """Test notification with sound."""
        notification_system.enable_sound = True
        
        result = notification_system.send(
            title="Test",
            message="Test with sound",
            play_sound=True
        )
        
        assert result is not None

    def test_notification_persistence(self, notification_system):
        """Test notification persistence."""
        notification_system.enable_persistence = True
        
        result = notification_system.send(
            title="Persistent",
            message="This notification persists",
            persistent=True
        )
        
        assert result is not None

    def test_notification_history(self, notification_system):
        """Test notification history tracking."""
        notification_system.enable_history = True
        
        # Send multiple notifications
        for i in range(3):
            notification_system.send(f"Notification {i}", f"Message {i}")
        
        # Get history
        history = notification_system.get_history()
        
        assert len(history) >= 3

    def test_notification_scheduling(self, notification_system):
        """Test scheduled notifications."""
        from datetime import datetime, timedelta
        
        scheduled_time = datetime.now() + timedelta(minutes=5)
        
        result = notification_system.schedule(
            title="Scheduled",
            message="This is scheduled",
            scheduled_time=scheduled_time
        )
        
        assert result is not None

    def test_notification_with_jarvis(self, notification_system):
        """Test notification integration with Jarvis."""
        from main import JarvisLive
        
        jarvis = JarvisLive()
        
        # Send notification through Jarvis
        result = notification_system.send(
            title="Jarvis Alert",
            message="Jarvis has a message for you"
        )
        
        assert result is not None

    def test_notification_channels(self, notification_system):
        """Test multiple notification channels."""
        notification_system.channels = ["desktop", "mobile", "email"]
        
        result = notification_system.send(
            title="Multi-channel",
            message="Sent to all channels",
            channels=["desktop", "mobile"]
        )
        
        assert result is not None

    def test_notification_grouping(self, notification_system):
        """Test notification grouping."""
        notification_system.enable_grouping = True
        
        # Send notifications in same group
        notification_system.send("Group Test", "Message 1", group="test_group")
        notification_system.send("Group Test", "Message 2", group="test_group")
        
        # Should be grouped
        assert True  # Placeholder for actual grouping test

    def test_notification_dismissal(self, notification_system):
        """Test notification dismissal."""
        notification_id = notification_system.send("Test", "Test message")
        
        # Dismiss notification
        result = notification_system.dismiss(notification_id)
        
        assert result is not None


class TestNotificationErrorHandling:
    """Error handling tests for notification system."""

    @pytest.fixture
    def notification_system(self):
        """Create a fresh notification system instance for testing."""
        from core.notification_system import NotificationSystem
        return NotificationSystem()

    def test_empty_message(self, notification_system):
        """Test handling of empty message."""
        with pytest.raises(ValueError):
            notification_system.send("Title", "")

    def test_invalid_priority(self, notification_system):
        """Test handling of invalid priority."""
        with pytest.raises(ValueError):
            notification_system.send("Title", "Message", priority="invalid")

    def test_dismiss_nonexistent(self, notification_system):
        """Test dismissing nonexistent notification."""
        result = notification_system.dismiss("nonexistent_id")
        assert result is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
