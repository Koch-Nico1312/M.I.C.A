"""
Action History System for Mark-XXXIX
=====================================
Tracks important actions with metadata and provides undo/rollback capabilities.
"""

import json
import threading
from dataclasses import dataclass, field
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
    UNDO_PLANNED = "undo_planned"


@dataclass
class UndoPlan:
    """Structured description of how an action can be reversed."""

    strategy: str
    steps: list[Dict[str, Any]] = field(default_factory=list)
    automatic: bool = False
    requires_confirmation: bool = True
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy,
            "steps": list(self.steps),
            "automatic": self.automatic,
            "requires_confirmation": self.requires_confirmation,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any] | None) -> Optional["UndoPlan"]:
        if not data:
            return None
        return cls(
            strategy=str(data.get("strategy", "manual")),
            steps=list(data.get("steps", [])),
            automatic=bool(data.get("automatic", False)),
            requires_confirmation=bool(data.get("requires_confirmation", True)),
            notes=str(data.get("notes", "")),
        )


@dataclass
class ActionRevision:
    """Revision metadata for auditability and retries."""

    number: int = 1
    parent_id: Optional[str] = None
    reason: str = "initial"
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "number": self.number,
            "parent_id": self.parent_id,
            "reason": self.reason,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any] | None) -> "ActionRevision":
        if not data:
            return cls()
        created_at = data.get("created_at")
        return cls(
            number=int(data.get("number", 1)),
            parent_id=data.get("parent_id"),
            reason=str(data.get("reason", "initial")),
            created_at=datetime.fromisoformat(created_at) if created_at else datetime.now(),
        )


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
        revision: ActionRevision | None = None,
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
        self.undo_plan: Optional[UndoPlan] = None
        self.revision = revision or ActionRevision()
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
            "undo_plan": self.undo_plan.to_dict() if self.undo_plan else None,
            "revision": self.revision.to_dict(),
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
        record.undo_plan = UndoPlan.from_dict(data.get("undo_plan"))
        record.revision = ActionRevision.from_dict(data.get("revision"))
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
        legacy_journal = self.history_file.with_suffix(self.history_file.suffix + ".jsonl")
        self.journal_file = self.history_file.with_suffix(".jsonl")
        if legacy_journal.exists() and not self.journal_file.exists():
            legacy_journal.replace(self.journal_file)

        self._history: List[ActionRecord] = []
        self._lock = threading.Lock()
        self._max_history_size = 1000
        self._compact_delay_seconds = 2.0
        self._compact_timer: Optional[threading.Timer] = None
        self._closed = False

        self._load_history()
        logger.info(f"Action history initialized with {len(self._history)} records")

    def _load_history(self):
        """Load history from file."""
        loaded: list[ActionRecord] = []

        if self.history_file.exists():
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                loaded = [ActionRecord.from_dict(item) for item in data]
            except Exception as e:
                logger.error(f"Failed to load action history snapshot: {e}")

        if self.journal_file.exists():
            try:
                with open(self.journal_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        loaded.append(ActionRecord.from_dict(json.loads(line)))
            except Exception as e:
                logger.error(f"Failed to load action history journal: {e}")

        by_id: dict[str, ActionRecord] = {}
        order: list[str] = []
        for record in loaded:
            if record.id not in by_id:
                order.append(record.id)
            by_id[record.id] = record

        self._history = [by_id[record_id] for record_id in order][-self._max_history_size :]

    def _save_history(self):
        """Save a compact snapshot of history to file and clear the journal."""
        try:
            data = [record.to_dict() for record in self._history]
            tmp_file = self.history_file.with_suffix(self.history_file.suffix + ".tmp")
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, separators=(",", ":"))
            tmp_file.replace(self.history_file)
            with open(self.journal_file, "w", encoding="utf-8"):
                pass
        except Exception as e:
            logger.error(f"Failed to save action history: {e}")

    def _append_journal(self, record: ActionRecord) -> None:
        """Persist a single newly-created record without rewriting the snapshot."""
        try:
            with open(self.journal_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record.to_dict(), separators=(",", ":")) + "\n")
        except Exception as e:
            logger.error(f"Failed to append action history journal: {e}")

    def _schedule_compaction(self) -> None:
        if self._closed:
            return
        if self._compact_timer and self._compact_timer.is_alive():
            return
        self._compact_timer = threading.Timer(self._compact_delay_seconds, self.flush)
        self._compact_timer.daemon = True
        self._compact_timer.start()

    def flush(self) -> None:
        """Synchronously compact pending journal entries into the JSON snapshot."""
        with self._lock:
            if self._compact_timer:
                self._compact_timer.cancel()
                self._compact_timer = None
            self._save_history()

    def close(self) -> None:
        """Flush pending action history writes."""
        self._closed = True
        self.flush()

    def record_action(
        self,
        tool_name: str,
        action: str,
        parameters: Dict[str, Any],
        result: str = "",
        status: ActionStatus = ActionStatus.SUCCESS,
        undo_data: Optional[Dict[str, Any]] = None,
        undo_plan: Optional[UndoPlan | Dict[str, Any]] = None,
        parent_id: Optional[str] = None,
        revision_reason: str = "initial",
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
            revision=ActionRevision(
                number=self._next_revision_number(parent_id),
                parent_id=parent_id,
                reason=revision_reason,
            ),
        )

        inferred_plan = UndoPlan.from_dict(undo_plan) if isinstance(undo_plan, dict) else undo_plan
        if inferred_plan is None:
            inferred_plan = self.build_undo_plan(tool_name, action, parameters, undo_data)

        if undo_data:
            record.undo_data = undo_data
            record.can_undo = True
        if inferred_plan:
            record.undo_plan = inferred_plan
            record.can_undo = True

        with self._lock:
            self._history.append(record)
            # Trim to max size
            if len(self._history) > self._max_history_size:
                self._history = self._history[-self._max_history_size :]

            self._append_journal(record)
            self._schedule_compaction()

        logger.info(f"Action recorded: {tool_name}/{action} (ID: {record.id})")
        return record

    def _next_revision_number(self, parent_id: Optional[str]) -> int:
        if not parent_id:
            return 1
        existing = [
            record.revision.number
            for record in self._history
            if record.id == parent_id or record.revision.parent_id == parent_id
        ]
        return (max(existing) + 1) if existing else 2

    def build_undo_plan(
        self,
        tool_name: str,
        action: str,
        parameters: Dict[str, Any],
        undo_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[UndoPlan]:
        """Infer a conservative undo plan for common reversible actions."""
        action_lower = action.lower()
        tool_lower = tool_name.lower()
        if "file" in tool_lower and action_lower in {"move", "rename"}:
            source = parameters.get("source") or undo_data and undo_data.get("original_path")
            destination = parameters.get("destination") or parameters.get("target")
            if source and destination:
                return UndoPlan(
                    strategy="move_back",
                    steps=[{"action": "move", "source": destination, "destination": source}],
                    automatic=False,
                    notes="Move the file or folder back to its original location.",
                )
        if "file" in tool_lower and action_lower == "copy":
            destination = parameters.get("destination") or parameters.get("target")
            if destination:
                return UndoPlan(
                    strategy="remove_copy",
                    steps=[{"action": "delete", "path": destination}],
                    automatic=False,
                    notes="Remove the copied resource after confirmation.",
                )
        if "file" in tool_lower and action_lower in {"create_file", "create_folder"}:
            path = parameters.get("path")
            if path:
                return UndoPlan(
                    strategy="remove_created_resource",
                    steps=[{"action": "delete", "path": path}],
                    automatic=False,
                    notes="Delete the created resource after confirmation.",
                )
        if action_lower in {"prepare", "draft"} or parameters.get("draft_only"):
            draft_id = parameters.get("draft_id") or undo_data and undo_data.get("draft_id")
            return UndoPlan(
                strategy="discard_draft",
                steps=[{"action": "discard_draft", "draft_id": draft_id}],
                automatic=bool(draft_id),
                notes="Discard the prepared message before it is sent.",
            )
        if action_lower in {"start", "run"} and ("workflow" in tool_lower or parameters.get("workflow")):
            return UndoPlan(
                strategy="cancel_workflow",
                steps=[{"action": "cancel", "workflow": parameters.get("workflow")}],
                automatic=False,
                notes="Cancel only if the workflow exposes a safe cancel step.",
            )
        if undo_data:
            return UndoPlan(
                strategy=str(undo_data.get("strategy", "manual_restore")),
                steps=list(undo_data.get("steps", [])),
                automatic=bool(undo_data.get("automatic", False)),
                notes=str(undo_data.get("notes", "Manual restore data is available.")),
            )
        return None

    def _classify_action_type(self, tool_name: str, action: str) -> ActionType:
        """Classify action type based on tool and action."""
        tool_lower = tool_name.lower()

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
            undo_record = ActionRecord(
                action_type=record.action_type,
                tool_name=record.tool_name,
                action=f"undo:{record.action}",
                parameters={"record_id": record.id, "undo_plan": record.undo_plan.to_dict() if record.undo_plan else None},
                result=f"Undo recorded for action {record.id}",
                status=ActionStatus.SUCCESS,
                revision=ActionRevision(
                    number=record.revision.number + 1,
                    parent_id=record.id,
                    reason="undo",
                ),
            )
            self._history.append(undo_record)
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
                revision=ActionRevision(
                    number=record.revision.number + 1,
                    parent_id=record.id,
                    reason="retry",
                ),
            )
            new_record.result = f"Retry of original action {record.id}"

            self._history.append(new_record)
            self._append_journal(new_record)
            self._schedule_compaction()

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
