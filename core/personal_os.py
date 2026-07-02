"""Personal OS integration registry and audit log."""

from __future__ import annotations

import json
import platform
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paths import project_path


OS_AUDIT_PATH = project_path("data", "os_action_audit.json")


ALLOWED_OS_ACTIONS = {
    "find_files": {"risk": "low", "requires_confirmation": False},
    "open_folder": {"risk": "low", "requires_confirmation": False},
    "read_clipboard": {"risk": "medium", "requires_confirmation": True},
    "screenshot_context": {"risk": "medium", "requires_confirmation": True},
    "launch_app": {"risk": "low", "requires_confirmation": False},
    "file_write": {"risk": "medium", "requires_confirmation": True},
    "file_delete": {"risk": "high", "requires_confirmation": True},
}


@dataclass
class OSAuditRecord:
    id: str
    action: str
    parameters: dict[str, Any]
    status: str
    message: str
    os_name: str = field(default_factory=platform.system)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class PersonalOSIntegration:
    def __init__(self, path: Path = OS_AUDIT_PATH):
        self.path = path
        self._records: list[OSAuditRecord] = []
        self._load()

    def allowed_actions(self) -> dict[str, Any]:
        return {"actions": ALLOWED_OS_ACTIONS, "os": platform.system()}

    def validate_action(self, action: str) -> dict[str, Any]:
        metadata = ALLOWED_OS_ACTIONS.get(action)
        if not metadata:
            return {"allowed": False, "reason": "unknown os action"}
        return {"allowed": True, "action": action, **metadata}

    def record(self, action: str, parameters: dict[str, Any], status: str, message: str) -> dict[str, Any]:
        record = OSAuditRecord(
            id=f"os-{uuid.uuid4().hex[:8]}",
            action=action,
            parameters=parameters,
            status=status,
            message=message,
        )
        self._records.insert(0, record)
        self._records = self._records[:200]
        self._save()
        return asdict(record)

    def audit(self) -> dict[str, Any]:
        return {"records": [asdict(record) for record in self._records], **self.allowed_actions()}

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self._records = [OSAuditRecord(**item) for item in raw.get("records", [])]
        except Exception:
            self._records = []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.audit(), ensure_ascii=False, indent=2), encoding="utf-8")


_integration: PersonalOSIntegration | None = None


def get_personal_os_integration() -> PersonalOSIntegration:
    global _integration
    if _integration is None:
        _integration = PersonalOSIntegration()
    return _integration
