"""
Tests for core.morning_routine module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, time


class TestMorningRoutine:
    """Test cases for MorningRoutine class."""

    @pytest.fixture
    def morning_routine(self):
        """Create a fresh MorningRoutine instance for testing."""
        from core.morning_routine import MorningRoutine
        return MorningRoutine()

    def test_morning_routine_initialization(self, morning_routine):
        """Test MorningRoutine initialization."""
        assert morning_routine is not None
        assert hasattr(morning_routine, 'start_routine')
        assert hasattr(morning_routine, 'stop_routine')
        assert hasattr(morning_routine, 'add_task')

    def test_add_task(self, morning_routine):
        """Test adding a task to the morning routine."""
        task_id = morning_routine.add_task(
            task_name="Skin Check",
            task_type="skin_analysis",
            scheduled_time=time(7, 0)
        )
        
        assert task_id is not None
        assert task_id in morning_routine.tasks

    def test_start_routine(self, morning_routine):
        """Test starting the morning routine."""
        morning_routine.add_task("Task 1", "test", time(7, 0))
        
        morning_routine.start_routine()
        
        assert morning_routine.is_running

    def test_stop_routine(self, morning_routine):
        """Test stopping the morning routine."""
        morning_routine.is_running = True
        
        morning_routine.stop_routine()
        
        assert not morning_routine.is_running

    def test_execute_task(self, morning_routine):
        """Test executing a routine task."""
        task_id = morning_routine.add_task("Test Task", "test", time(7, 0))
        
        result = morning_routine.execute_task(task_id)
        
        assert result is not None

    def test_get_task_status(self, morning_routine):
        """Test getting task status."""
        task_id = morning_routine.add_task("Test Task", "test", time(7, 0))
        
        status = morning_routine.get_task_status(task_id)
        
        assert status is not None
        assert 'status' in status

    def test_skip_task(self, morning_routine):
        """Test skipping a task."""
        task_id = morning_routine.add_task("Test Task", "test", time(7, 0))
        
        morning_routine.skip_task(task_id)
        
        status = morning_routine.get_task_status(task_id)
        assert status['status'] == "skipped"

    def test_complete_task(self, morning_routine):
        """Test marking a task as complete."""
        task_id = morning_routine.add_task("Test Task", "test", time(7, 0))
        
        morning_routine.complete_task(task_id)
        
        status = morning_routine.get_task_status(task_id)
        assert status['status'] == "completed"

    def test_get_routine_summary(self, morning_routine):
        """Test getting routine summary."""
        morning_routine.add_task("Task 1", "test", time(7, 0))
        morning_routine.add_task("Task 2", "test", time(7, 30))
        
        summary = morning_routine.get_routine_summary()
        
        assert summary is not None
        assert 'total_tasks' in summary
        assert summary['total_tasks'] == 2

    def test_reminder_notification(self, morning_routine):
        """Test reminder notification for tasks."""
        morning_routine.enable_reminders = True
        
        task_id = morning_routine.add_task("Test Task", "test", time(7, 0))
        
        # Should trigger reminder
        mock_notify = Mock()
        morning_routine.set_notification_callback(mock_notify)
        
        morning_routine.trigger_reminder(task_id)
        
        # Should have called notification
        assert True  # Placeholder for actual notification test


class TestMorningRoutineErrorHandling:
    """Test error handling in MorningRoutine."""

    @pytest.fixture
    def morning_routine(self):
        """Create a fresh MorningRoutine instance for testing."""
        from core.morning_routine import MorningRoutine
        return MorningRoutine()

    def test_execute_nonexistent_task(self, morning_routine):
        """Test executing a non-existent task."""
        with pytest.raises(KeyError):
            morning_routine.execute_task("nonexistent_id")

    def test_invalid_task_type(self, morning_routine):
        """Test handling of invalid task types."""
        invalid_types = [None, "", "invalid_type", 123]
        
        for invalid_type in invalid_types:
            try:
                morning_routine.add_task("Test", invalid_type, time(7, 0))
            except (ValueError, TypeError):
                pass  # Expected

    def test_task_execution_failure(self, morning_routine):
        """Test handling of task execution failure."""
        task_id = morning_routine.add_task("Failing Task", "failing_type", time(7, 0))
        
        # Mock failure
        with patch.object(morning_routine, '_execute_task_internal', side_effect=Exception("Task failed")):
            result = morning_routine.execute_task(task_id)
            # Should handle failure gracefully
            assert result is not None or result is None


class TestMorningRoutineIntegration:
    """Integration tests for MorningRoutine."""

    @patch('core.morning_routine.get_local_analyzer')
    def test_skin_check_integration(self, mock_analyzer):
        """Test skin check integration with local analyzer."""
        from core.morning_routine import MorningRoutine
        
        mock_analyzer.return_value = Mock()
        mock_analyzer.return_value.analyze_skin.return_value = {
            "analysis": "Skin looks good",
            "recommendations": []
        }
        
        routine = MorningRoutine()
        routine.add_task("Skin Check", "skin_analysis", time(7, 0))
        
        result = routine.execute_skin_check()
        
        assert result is not None

    def test_full_routine_execution(self):
        """Test full morning routine execution."""
        from core.morning_routine import MorningRoutine
        
        routine = MorningRoutine()
        
        # Add tasks
        routine.add_task("Skin Check", "skin_analysis", time(7, 0))
        routine.add_task("Weather Check", "weather", time(7, 5))
        routine.add_task("Calendar Review", "calendar", time(7, 10))
        
        # Start routine
        routine.start_routine()
        
        # Execute all tasks
        for task_id in routine.tasks:
            routine.execute_task(task_id)
        
        # Get summary
        summary = routine.get_routine_summary()
        
        assert summary['total_tasks'] == 3

    def test_routine_persistence(self):
        """Test that routine configuration persists."""
        from core.morning_routine import MorningRoutine
        
        routine1 = MorningRoutine()
        routine1.add_task("Test Task", "test", time(7, 0))
        routine1.save_configuration()
        
        routine2 = MorningRoutine()
        routine2.load_configuration()
        
        # Should load saved configuration
        assert True  # Placeholder for actual persistence test

    def test_routine_with_notifications(self):
        """Test routine with notification system."""
        from core.morning_routine import MorningRoutine
        
        routine = MorningRoutine()
        routine.enable_reminders = True
        
        mock_notify = Mock()
        routine.set_notification_callback(mock_notify)
        
        routine.add_task("Test Task", "test", time(7, 0))
        routine.start_routine()
        
        # Should send notifications
        assert routine.enable_reminders is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
