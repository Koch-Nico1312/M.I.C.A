"""Persistent local automation scheduler metadata."""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
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
    "task_pipeline",
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
    next_run: str | None = None


class AutomationScheduler:
    def __init__(self, path: Path = AUTOMATION_PATH):
        self.path = path
        self._lock = threading.RLock()
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
        item.next_run = self._next_after(item.schedule, datetime.now())
        with self._lock:
            self._items[item.id] = item
            self._save()
        return asdict(item)

    def list(self) -> dict[str, Any]:
        with self._lock:
            return {"items": [asdict(item) for item in self._items.values()], "allowed_actions": sorted(SAFE_AUTOMATION_ACTIONS)}

    def set_enabled(self, automation_id: str, enabled: bool) -> dict[str, Any]:
        with self._lock:
            item = self._require(automation_id)
            item.enabled = bool(enabled)
            if item.enabled and not item.next_run:
                item.next_run = self._next_after(item.schedule, datetime.now())
            self._save()
            return asdict(item)

    def record_run(self, automation_id: str, *, error: str | None = None) -> dict[str, Any]:
        with self._lock:
            item = self._require(automation_id)
            now = datetime.now()
            item.last_run = now.isoformat()
            item.last_error = error
            item.next_run = self._next_after(item.schedule, now)
            if item.schedule.startswith("once:"):
                item.enabled = False
            self._save()
            return asdict(item)

    def delete(self, automation_id: str) -> dict[str, Any]:
        with self._lock:
            item = self._require(automation_id)
            removed = asdict(item)
            del self._items[automation_id]
            self._save()
            return removed

    def due(self, now: datetime | None = None) -> list[dict[str, Any]]:
        current = now or datetime.now()
        with self._lock:
            return [asdict(item) for item in self._items.values() if item.enabled and item.next_run and datetime.fromisoformat(item.next_run) <= current]

    @staticmethod
    def _next_after(schedule: str, after: datetime) -> str | None:
        raw = str(schedule or "manual").strip().lower()
        if raw == "manual":
            return None
        if len(raw) == 5 and raw[2] == ":":
            raw = f"daily:{raw}"
        if raw.startswith("once:"):
            target = datetime.fromisoformat(schedule.split(":", 1)[1])
            return target.isoformat() if target > after else after.isoformat()
        if raw.startswith("daily:"):
            hour, minute = (int(part) for part in raw.split(":")[1:3])
            target = after.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target <= after:
                target += timedelta(days=1)
            return target.isoformat()
        if raw.startswith("weekly:"):
            _, weekday, hour, minute = raw.split(":")
            target = after.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
            target += timedelta(days=(int(weekday) - after.weekday()) % 7)
            if target <= after:
                target += timedelta(days=7)
            return target.isoformat()
        raise ValueError("unsupported schedule")

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
                if automation.enabled and automation.next_run is None:
                    automation.next_run = self._next_after(automation.schedule, datetime.now())
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
