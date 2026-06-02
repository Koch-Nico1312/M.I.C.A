"""
Tests for actions.agent_task module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestAgentTask:
    """Test cases for agent_task action."""

    @pytest.fixture
    def agent_task(self):
        """Create a fresh agent_task instance for testing."""
        from actions.agent_task import agent_task
        return agent_task

    def test_create_task(self, agent_task):
        """Test creating a new task."""
        result = agent_task.create(
            description="Complete the project documentation",
            priority="high"
        )
        
        assert result is not None

    def test_list_tasks(self, agent_task):
        """Test listing all tasks."""
        agent_task.create("Task 1", "low")
        agent_task.create("Task 2", "medium")
        
        result = agent_task.list()
        
        assert result is not None
        assert len(result) >= 2

    def test_get_task(self, agent_task):
        """Test getting a specific task."""
        task_id = agent_task.create("Test task", "medium")
        
        result = agent_task.get(task_id)
        
        assert result is not None
        assert result['description'] == "Test task"

    def test_update_task(self, agent_task):
        """Test updating a task."""
        task_id = agent_task.create("Original description", "medium")
        
        result = agent_task.update(task_id, description="Updated description")
        
        assert result is not None

    def test_complete_task(self, agent_task):
        """Test marking a task as complete."""
        task_id = agent_task.create("Test task", "medium")
        
        result = agent_task.complete(task_id)
        
        assert result is not None

    def test_delete_task(self, agent_task):
        """Test deleting a task."""
        task_id = agent_task.create("Test task", "medium")
        
        result = agent_task.delete(task_id)
        
        assert result is not None

    def test_set_priority(self, agent_task):
        """Test setting task priority."""
        task_id = agent_task.create("Test task", "medium")
        
        result = agent_task.set_priority(task_id, "high")
        
        assert result is not None

    def test_add_subtask(self, agent_task):
        """Test adding a subtask to a task."""
        task_id = agent_task.create("Main task", "medium")
        
        result = agent_task.add_subtask(task_id, "Subtask 1")
        
        assert result is not None


class TestAgentTaskErrorHandling:
    """Test error handling in agent_task."""

    @pytest.fixture
    def agent_task(self):
        """Create a fresh agent_task instance for testing."""
        from actions.agent_task import agent_task
        return agent_task

    def test_empty_description(self, agent_task):
        """Test handling of empty description."""
        with pytest.raises(ValueError):
            agent_task.create("", "medium")

    def test_invalid_priority(self, agent_task):
        """Test handling of invalid priority."""
        with pytest.raises(ValueError):
            agent_task.create("Test", "invalid_priority")

    def test_get_nonexistent_task(self, agent_task):
        """Test getting a non-existent task."""
        with pytest.raises(KeyError):
            agent_task.get("nonexistent_id")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
