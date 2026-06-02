"""
Tests for actions.reminder module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta


class TestReminder:
    """Test cases for reminder action."""

    @pytest.fixture
    def reminder(self):
        """Create a fresh reminder instance for testing."""
        from actions.reminder import reminder
        return reminder

    def test_create_reminder(self, reminder):
        """Test creating a reminder."""
        reminder_time = datetime.now() + timedelta(hours=1)
        
        result = reminder.create(
            message="Test reminder",
            reminder_time=reminder_time
        )
        
        assert result is not None

    def test_create_reminder_with_repeat(self, reminder):
        """Test creating a recurring reminder."""
        reminder_time = datetime.now() + timedelta(hours=1)
        
        result = reminder.create(
            message="Daily reminder",
            reminder_time=reminder_time,
            repeat="daily"
        )
        
        assert result is not None

    def test_list_reminders(self, reminder):
        """Test listing all reminders."""
        reminder.create("Test 1", datetime.now() + timedelta(hours=1))
        reminder.create("Test 2", datetime.now() + timedelta(hours=2))
        
        result = reminder.list()
        
        assert result is not None
        assert len(result) >= 2

    def test_delete_reminder(self, reminder):
        """Test deleting a reminder."""
        reminder_id = reminder.create("Test", datetime.now() + timedelta(hours=1))
        
        result = reminder.delete(reminder_id)
        
        assert result is not None

    def test_get_reminder(self, reminder):
        """Test getting a specific reminder."""
        reminder_id = reminder.create("Test", datetime.now() + timedelta(hours=1))
        
        result = reminder.get(reminder_id)
        
        assert result is not None
        assert result['message'] == "Test"

    def test_update_reminder(self, reminder):
        """Test updating a reminder."""
        reminder_id = reminder.create("Test", datetime.now() + timedelta(hours=1))
        
        result = reminder.update(
            reminder_id,
            message="Updated message"
        )
        
        assert result is not None

    def test_complete_reminder(self, reminder):
        """Test marking a reminder as complete."""
        reminder_id = reminder.create("Test", datetime.now() + timedelta(hours=1))
        
        result = reminder.complete(reminder_id)
        
        assert result is not None

    def test_snooze_reminder(self, reminder):
        """Test snoozing a reminder."""
        reminder_id = reminder.create("Test", datetime.now() + timedelta(hours=1))
        
        result = reminder.snooze(reminder_id, minutes=10)
        
        assert result is not None


class TestReminderErrorHandling:
    """Test error handling in reminder."""

    @pytest.fixture
    def reminder(self):
        """Create a fresh reminder instance for testing."""
        from actions.reminder import reminder
        return reminder

    def test_empty_message(self, reminder):
        """Test handling of empty message."""
        with pytest.raises(ValueError):
            reminder.create("", datetime.now() + timedelta(hours=1))

    def test_past_reminder_time(self, reminder):
        """Test handling of past reminder time."""
        past_time = datetime.now() - timedelta(hours=1)
        
        with pytest.raises(ValueError):
            reminder.create("Test", past_time)

    def test_delete_nonexistent_reminder(self, reminder):
        """Test deleting a non-existent reminder."""
        with pytest.raises(KeyError):
            reminder.delete("nonexistent_id")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
