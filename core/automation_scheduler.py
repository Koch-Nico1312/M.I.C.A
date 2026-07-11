"""Persistent local automation scheduler metadata."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paths import project_path


AUTOMATION_PATH = project_path("data", "automations.json")
SAFE_AUTOMATION_ACTIONS = {
    "daily_briefing",
    "healthcheck",
    "knowledge_reindex",
    "reminder",
    "folder_monitor",
    "learned_workflow",
}


@dataclass
class Automation:
    id: str
    name: str
    action: str
    schedule: str
    parameters: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    last_run: str | None = None
    last_error: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class AutomationScheduler:
    def __init__(self, path: Path = AUTOMATION_PATH):
        self.path = path
        self._items: dict[str, Automation] = {}
        self._load()

    def create(self, name: str, action: str, schedule: str, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
        action = str(action or "").strip()
        if action not in SAFE_AUTOMATION_ACTIONS:
            raise ValueError("automation action is not allowed")
        item = Automation(
            id=f"auto-{uuid.uuid4().hex[:8]}",
            name=str(name or action).strip(),
            action=action,
            schedule=str(schedule or "manual").strip(),
            parameters=parameters or {},
        )
        self._items[item.id] = item
        self._save()
        return asdict(item)

    def list(self) -> dict[str, Any]:
        return {
            "items": [asdict(item) for item in self._items.values()],
            "allowed_actions": sorted(SAFE_AUTOMATION_ACTIONS),
        }

    def set_enabled(self, automation_id: str, enabled: bool) -> dict[str, Any]:
        item = self._require(automation_id)
        item.enabled = bool(enabled)
        self._save()
        return asdict(item)

    def record_run(self, automation_id: str, *, error: str | None = None) -> dict[str, Any]:
        item = self._require(automation_id)
        item.last_run = datetime.now().isoformat()
        item.last_error = error
        self._save()
        return asdict(item)

    def _require(self, automation_id: str) -> Automation:
        item = self._items.get(automation_id)
        if not item:
            raise ValueError("unknown automation")
        return item

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            for item in raw.get("items", []):
                automation = Automation(**item)
                self._items[automation.id] = automation
        except Exception:
            self._items = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.list(), ensure_ascii=False, indent=2), encoding="utf-8")


_scheduler: AutomationScheduler | None = None


def get_automation_scheduler() -> AutomationScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AutomationScheduler()
    return _scheduler
