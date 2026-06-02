"""
Action History System for Mark-XXXIX
=====================================
Tracks important actions with metadata and provides undo/rollback capabilities.
"""

import json
import threading
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.logger import get_logger

logger = get_logger(__name__)


class ActionType(Enum):
    """Types of actions that can be tracked."""

    FILE_OPERATION = "file_operation"
    CONFIG_CHANGE = "config_change"
    SYSTEM_SETTING = "system_setting"
    UI_ACTION = "ui_action"
    API_CALL = "api_call"
    MEMORY_UPDATE = "memory_update"
    INTEGRATION_ACTION = "integration_action"


class ActionStatus(Enum):
    """Status of an action."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    UNDONE = "undone"


class ActionRecord:
    """Represents a single action in history."""

    def __init__(
        self,
        action_type: ActionType,
        tool_name: str,
        action: str,
        parameters: Dict[str, Any],
        result: str = "",
        status: ActionStatus = ActionStatus.PENDING,
    ):
        self.id = f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        self.action_type = action_type
        self.tool_name = tool_name
        self.action = action
        self.parameters = parameters
        self.result = result
        self.status = status
        self.timestamp = datetime.now()
        self.undo_data: Optional[Dict[str, Any]] = None
        self.can_undo = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "action_type": self.action_type.value,
            "tool_name": self.tool_name,
            "action": self.action,
            "parameters": self.parameters,
            "result": self.result,
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
            "undo_data": self.undo_data,
            "can_undo": self.can_undo,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActionRecord":
        """Create from dictionary."""
        record = cls(
            action_type=ActionType(data["action_type"]),
            tool_name=data["tool_name"],
            action=data["action"],
            parameters=data["parameters"],
            result=data.get("result", ""),
            status=ActionStatus(data.get("status", "pending")),
        )
        record.id = data["id"]
        record.timestamp = datetime.fromisoformat(data["timestamp"])
        record.undo_data = data.get("undo_data")
        record.can_undo = data.get("can_undo", False)
        return record


class ActionHistory:
    """
    Manages action history with undo/rollback capabilities.
    """

    def __init__(self, history_file: Optional[Path] = None):
        """
        Initialize action history.

        Args:
            history_file: Path to history file for persistence
        """
        if history_file is None:
            base_dir = Path(__file__).resolve().parent.parent
            history_file = base_dir / "data" / "action_history.json"

        self.history_file = Path(history_file)
        self.history_file.parent.mkdir(parents=True, exist_ok=True)

        self._history: List[ActionRecord] = []
        self._lock = threading.Lock()
        self._max_history_size = 1000

        self._load_history()
        logger.info(f"Action history initialized with {len(self._history)} records")

    def _load_history(self):
        """Load history from file."""
        if not self.history_file.exists():
            return

        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._history = [ActionRecord.from_dict(item) for item in data]
            # Trim to max size
            self._history = self._history[-self._max_history_size :]

        except Exception as e:
            logger.error(f"Failed to load action history: {e}")
            self._history = []

    def _save_history(self):
        """Save history to file."""
        try:
            data = [record.to_dict() for record in self._history]
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save action history: {e}")

    def record_action(
        self,
        tool_name: str,
        action: str,
        parameters: Dict[str, Any],
        result: str = "",
        status: ActionStatus = ActionStatus.SUCCESS,
        undo_data: Optional[Dict[str, Any]] = None,
    ) -> ActionRecord:
        """
        Record an action in history.

        Args:
            tool_name: Name of the tool
            action: Specific action performed
            parameters: Action parameters
            result: Action result
            status: Action status
            undo_data: Data needed to undo the action

        Returns:
            The created ActionRecord
        """
        # Determine action type based on tool name
        action_type = self._classify_action_type(tool_name, action)

        record = ActionRecord(
            action_type=action_type,
            tool_name=tool_name,
            action=action,
            parameters=parameters,
            result=result,
            status=status,
        )

        if undo_data:
            record.undo_data = undo_data
            record.can_undo = True

        with self._lock:
            self._history.append(record)
            # Trim to max size
            if len(self._history) > self._max_history_size:
                self._history = self._history[-self._max_history_size :]

            self._save_history()

        logger.info(f"Action recorded: {tool_name}/{action} (ID: {record.id})")
        return record

    def _classify_action_type(self, tool_name: str, action: str) -> ActionType:
        """Classify action type based on tool and action."""
        tool_lower = tool_name.lower()
        action_lower = action.lower()

        if "file" in tool_lower or "file_controller" in tool_lower:
            return ActionType.FILE_OPERATION
        elif "config" in tool_lower or "settings" in tool_lower:
            return ActionType.CONFIG_CHANGE
        elif "computer" in tool_lower or "desktop" in tool_lower:
            return ActionType.SYSTEM_SETTING
        elif "memory" in tool_lower:
            return ActionType.MEMORY_UPDATE
        elif "gmail" in tool_lower or "calendar" in tool_lower or "obsidian" in tool_lower:
            return ActionType.INTEGRATION_ACTION
        else:
            return ActionType.API_CALL

    def get_history(
        self, limit: int = 50, action_type: Optional[ActionType] = None
    ) -> List[ActionRecord]:
        """
        Get action history.

        Args:
            limit: Maximum number of records to return
            action_type: Filter by action type

        Returns:
            List of ActionRecords (most recent first)
        """
        with self._lock:
            history = self._history.copy()

        if action_type:
            history = [r for r in history if r.action_type == action_type]

        return history[-limit:][::-1]

    def get_record(self, record_id: str) -> Optional[ActionRecord]:
        """Get a specific record by ID."""
        with self._lock:
            for record in self._history:
                if record.id == record_id:
                    return record
        return None

    def undo_action(self, record_id: str) -> tuple[bool, str]:
        """
        Undo an action if possible.

        Args:
            record_id: ID of the action to undo

        Returns:
            Tuple of (success, message)
        """
        with self._lock:
            record = None
            for r in self._history:
                if r.id == record_id:
                    record = r
                    break

            if not record:
                return False, "Action not found in history"

            if not record.can_undo:
                return False, f"Action '{record.action}' cannot be undone"

            if record.status != ActionStatus.SUCCESS:
                return False, f"Cannot undo action with status: {record.status.value}"

            # Mark as undone
            record.status = ActionStatus.UNDONE
            self._save_history()

            logger.info(f"Action undone: {record.tool_name}/{record.action} (ID: {record.id})")
            return True, f"Action '{record.action}' marked as undone"

    def retry_action(
        self, record_id: str, modified_parameters: Optional[Dict[str, Any]] = None
    ) -> tuple[bool, str, Optional[ActionRecord]]:
        """
        Retry a failed action with the same or modified parameters.

        Args:
            record_id: ID of the action to retry
            modified_parameters: Optional modified parameters for retry

        Returns:
            Tuple of (success, message, new_record)
        """
        with self._lock:
            record = None
            for r in self._history:
                if r.id == record_id:
                    record = r
                    break

            if not record:
                return False, "Action not found in history", None

            if record.status != ActionStatus.FAILED:
                return (
                    False,
                    f"Can only retry failed actions (current status: {record.status.value})",
                    None,
                )

            # Create new record for retry
            retry_params = record.parameters.copy()
            if modified_parameters:
                retry_params.update(modified_parameters)

            # Create new record with RETRY status
            new_record = ActionRecord(
                action_type=record.action_type,
                tool_name=record.tool_name,
                action=record.action,
                parameters=retry_params,
                result="",
                status=ActionStatus.PENDING,
            )
            new_record.result = f"Retry of original action {record.id}"

            self._history.append(new_record)
            self._save_history()

        logger.info(
            f"Action retry created: {record.tool_name}/{record.action} (original ID: {record.id}, new ID: {new_record.id})"
        )
        return True, f"Retry created for action '{record.action}'", new_record

    def get_undoable_actions(self) -> List[ActionRecord]:
        """Get list of actions that can be undone."""
        with self._lock:
            return [r for r in self._history if r.can_undo and r.status == ActionStatus.SUCCESS]

    def clear_history(self, before_date: Optional[datetime] = None):
        """
        Clear action history.

        Args:
            before_date: Clear only records before this date. If None, clear all.
        """
        with self._lock:
            if before_date:
                self._history = [r for r in self._history if r.timestamp >= before_date]
            else:
                self._history = []

            self._save_history()

        logger.info(f"Action history cleared (before_date: {before_date})")

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about action history."""
        with self._lock:
            total = len(self._history)
            by_type = {}
            by_status = {}
            undoable = 0

            for record in self._history:
                # Count by type
                atype = record.action_type.value
                by_type[atype] = by_type.get(atype, 0) + 1

                # Count by status
                status = record.status.value
                by_status[status] = by_status.get(status, 0) + 1

                # Count undoable
                if record.can_undo and record.status == ActionStatus.SUCCESS:
                    undoable += 1

            return {
                "total_actions": total,
                "by_type": by_type,
                "by_status": by_status,
                "undoable_count": undoable,
                "history_file": str(self.history_file),
            }


# Global instance
_action_history: Optional[ActionHistory] = None


def get_action_history() -> ActionHistory:
    """Get the global action history instance."""
    global _action_history
    if _action_history is None:
        _action_history = ActionHistory()
    return _action_history
