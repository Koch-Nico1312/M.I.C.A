"""
Tests for the action history system.
"""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from core.action_history import (
    ActionHistory,
    ActionRecord,
    ActionStatus,
    ActionType,
    get_action_history,
)


def test_action_history_initialization():
    """Test action history initialization."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_file = Path(tmpdir) / "test_history.json"
        history = ActionHistory(history_file=history_file)

        assert len(history.get_history()) == 0
        assert history_file.parent.exists()


def test_record_action():
    """Test recording an action."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_file = Path(tmpdir) / "test_history.json"
        history = ActionHistory(history_file=history_file)

        record = history.record_action(
            tool_name="file_controller",
            action="delete",
            parameters={"path": "/tmp/test"},
            result="File deleted",
            status=ActionStatus.SUCCESS,
        )

        assert record.tool_name == "file_controller"
        assert record.action == "delete"
        assert record.status == ActionStatus.SUCCESS
        assert len(history.get_history()) == 1


def test_get_history():
    """Test retrieving history."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_file = Path(tmpdir) / "test_history.json"
        history = ActionHistory(history_file=history_file)

        # Record multiple actions
        for i in range(5):
            history.record_action(
                tool_name="file_controller",
                action=f"action_{i}",
                parameters={"index": i},
                result=f"Result {i}",
                status=ActionStatus.SUCCESS,
            )

        # Get all history
        all_history = history.get_history(limit=10)
        assert len(all_history) == 5

        # Get limited history
        limited_history = history.get_history(limit=3)
        assert len(limited_history) == 3


def test_get_history_by_type():
    """Test filtering history by action type."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_file = Path(tmpdir) / "test_history.json"
        history = ActionHistory(history_file=history_file)

        # Record file operations
        history.record_action(
            tool_name="file_controller",
            action="delete",
            parameters={"path": "/tmp/test"},
            status=ActionStatus.SUCCESS,
        )

        # Record config change
        history.record_action(
            tool_name="computer_settings",
            action="volume",
            parameters={"level": 50},
            status=ActionStatus.SUCCESS,
        )

        # Filter by file operation type
        file_ops = history.get_history(action_type=ActionType.FILE_OPERATION)
        assert len(file_ops) == 1
        assert file_ops[0].tool_name == "file_controller"


def test_undo_action():
    """Test undoing an action."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_file = Path(tmpdir) / "test_history.json"
        history = ActionHistory(history_file=history_file)

        # Record an action with undo data
        record = history.record_action(
            tool_name="file_controller",
            action="delete",
            parameters={"path": "/tmp/test"},
            result="File deleted",
            status=ActionStatus.SUCCESS,
            undo_data={"original_path": "/tmp/test", "backup_path": "/tmp/backup"},
        )

        assert record.can_undo is True

        # Undo the action
        success, message = history.undo_action(record.id)
        assert success is True
        assert "undone" in message.lower()

        # Check status
        updated_record = history.get_record(record.id)
        assert updated_record.status == ActionStatus.UNDONE


def test_undo_non_undoable_action():
    """Test that non-undoable actions cannot be undone."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_file = Path(tmpdir) / "test_history.json"
        history = ActionHistory(history_file=history_file)

        # Record an action without undo data
        record = history.record_action(
            tool_name="file_controller",
            action="list",
            parameters={"path": "/tmp"},
            result="Files listed",
            status=ActionStatus.SUCCESS,
        )

        assert record.can_undo is False

        # Try to undo
        success, message = history.undo_action(record.id)
        assert success is False
        assert "cannot be undone" in message.lower()


def test_undo_failed_action():
    """Test that failed actions cannot be undone."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_file = Path(tmpdir) / "test_history.json"
        history = ActionHistory(history_file=history_file)

        # Record a failed action
        record = history.record_action(
            tool_name="file_controller",
            action="delete",
            parameters={"path": "/tmp/test"},
            result="Permission denied",
            status=ActionStatus.FAILED,
            undo_data={"backup_path": "/tmp/backup"},
        )

        # Try to undo
        success, message = history.undo_action(record.id)
        assert success is False
        assert "status" in message.lower()


def test_get_undoable_actions():
    """Test getting list of undoable actions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_file = Path(tmpdir) / "test_history.json"
        history = ActionHistory(history_file=history_file)

        # Record undoable action
        history.record_action(
            tool_name="file_controller",
            action="delete",
            parameters={"path": "/tmp/test"},
            status=ActionStatus.SUCCESS,
            undo_data={"backup": "/tmp/backup"},
        )

        # Record non-undoable action
        history.record_action(
            tool_name="file_controller",
            action="list",
            parameters={"path": "/tmp"},
            status=ActionStatus.SUCCESS,
        )

        # Get undoable actions
        undoable = history.get_undoable_actions()
        assert len(undoable) == 1
        assert undoable[0].action == "delete"


def test_clear_history():
    """Test clearing history."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_file = Path(tmpdir) / "test_history.json"
        history = ActionHistory(history_file=history_file)

        # Record some actions
        for i in range(5):
            history.record_action(
                tool_name="file_controller",
                action=f"action_{i}",
                parameters={"index": i},
                status=ActionStatus.SUCCESS,
            )

        assert len(history.get_history()) == 5

        # Clear all history
        history.clear_history()
        assert len(history.get_history()) == 0


def test_clear_history_before_date():
    """Test clearing history before a specific date."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_file = Path(tmpdir) / "test_history.json"
        history = ActionHistory(history_file=history_file)

        # Record actions
        history.record_action(
            tool_name="file_controller",
            action="old_action",
            parameters={},
            status=ActionStatus.SUCCESS,
        )

        # Wait a bit
        import time

        time.sleep(0.1)

        cutoff = datetime.now()

        # Record more actions
        history.record_action(
            tool_name="file_controller",
            action="new_action",
            parameters={},
            status=ActionStatus.SUCCESS,
        )

        # Clear before cutoff
        history.clear_history(before_date=cutoff)

        # Should only have the new action
        remaining = history.get_history()
        assert len(remaining) == 1
        assert remaining[0].action == "new_action"


def test_get_stats():
    """Test getting history statistics."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_file = Path(tmpdir) / "test_history.json"
        history = ActionHistory(history_file=history_file)

        # Record various actions
        history.record_action(
            tool_name="file_controller",
            action="delete",
            parameters={},
            status=ActionStatus.SUCCESS,
            undo_data={"backup": "/tmp/backup"},
        )
        history.record_action(
            tool_name="file_controller", action="list", parameters={}, status=ActionStatus.SUCCESS
        )
        history.record_action(
            tool_name="computer_settings",
            action="volume",
            parameters={},
            status=ActionStatus.FAILED,
        )

        stats = history.get_stats()
        assert stats["total_actions"] == 3
        assert stats["undoable_count"] == 1
        assert "by_type" in stats
        assert "by_status" in stats


def test_action_record_serialization():
    """Test ActionRecord serialization to/from dict."""
    record = ActionRecord(
        action_type=ActionType.FILE_OPERATION,
        tool_name="file_controller",
        action="delete",
        parameters={"path": "/tmp/test"},
        result="Deleted",
        status=ActionStatus.SUCCESS,
    )

    # Add undo data
    record.undo_data = {"backup": "/tmp/backup"}
    record.can_undo = True

    # Serialize
    data = record.to_dict()
    assert data["tool_name"] == "file_controller"
    assert data["action"] == "delete"
    assert data["can_undo"] is True

    # Deserialize
    restored = ActionRecord.from_dict(data)
    assert restored.tool_name == record.tool_name
    assert restored.action == record.action
    assert restored.can_undo == record.can_undo


def test_global_action_history_instance():
    """Test global action history instance."""
    history1 = get_action_history()
    history2 = get_action_history()
    assert history1 is history2


def test_max_history_size():
    """Test that history respects max size limit."""
    with tempfile.TemporaryDirectory() as tmpdir:
        history_file = Path(tmpdir) / "test_history.json"
        history = ActionHistory(history_file=history_file)
        history._max_history_size = 10

        # Record more than max size
        for i in range(15):
            history.record_action(
                tool_name="file_controller",
                action=f"action_{i}",
                parameters={"index": i},
                status=ActionStatus.SUCCESS,
            )

        # Should only keep max size
        assert len(history.get_history()) == 10
