"""Persistent local automation scheduler with run recovery and circuit breaking."""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

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
TERMINAL_RUN_STATUSES = {"completed", "failed", "interrupted", "cancelled"}


class CircuitOpenError(RuntimeError):
    pass


@dataclass
class Automation:
    id: str
    name: str
    action: str
    schedule: str
    parameters: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    last_run: str | None = None
    last_success: str | None = None
    last_error: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    next_run: str | None = None
    consecutive_failures: int = 0
    circuit_state: str = "closed"
    circuit_opened_at: str | None = None
    max_failures: int = 3
    recovery_after_minutes: int = 15
    active_run_id: str | None = None


@dataclass
class AutomationRun:
    id: str
    automation_id: str
    action: str
    status: str
    started_at: str
    finished_at: str | None = None
    error: str | None = None
    result: dict[str, Any] = field(default_factory=dict)
    recovery: bool = False


class AutomationScheduler:
    def __init__(self, path: Path = AUTOMATION_PATH):
        self.path = path
        self._lock = threading.RLock()
        self._items: dict[str, Automation] = {}
        self._runs: dict[str, AutomationRun] = {}
        self._load()
        self._recover_interrupted_runs()

    def create(
        self,
        name: str,
        action: str,
        schedule: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
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
            return {
                "items": [asdict(item) for item in self._items.values()],
                "runs": [asdict(run) for run in list(self._runs.values())[-250:]][::-1],
                "allowed_actions": sorted(SAFE_AUTOMATION_ACTIONS),
            }

    def set_enabled(self, automation_id: str, enabled: bool) -> dict[str, Any]:
        with self._lock:
            item = self._require(automation_id)
            item.enabled = bool(enabled)
            if item.enabled and not item.next_run:
                item.next_run = self._next_after(item.schedule, datetime.now())
            self._save()
            return asdict(item)

    def begin_run(self, automation_id: str, *, now: datetime | None = None) -> dict[str, Any]:
        current = now or datetime.now()
        with self._lock:
            item = self._require(automation_id)
            if not item.enabled:
                raise ValueError("automation is disabled")
            if item.active_run_id:
                active = self._runs.get(item.active_run_id)
                if active and active.status == "running":
                    raise ValueError("automation already has an active run")
                item.active_run_id = None
            recovery = self._prepare_circuit(item, current)
            run = AutomationRun(
                id=f"run-{uuid.uuid4().hex[:10]}",
                automation_id=item.id,
                action=item.action,
                status="running",
                started_at=current.isoformat(),
                recovery=recovery,
            )
            self._runs[run.id] = run
            item.active_run_id = run.id
            item.last_run = current.isoformat()
            self._trim_runs()
            self._save()
            return asdict(run)

    def complete_run(
        self,
        run_id: str,
        *,
        error: str | None = None,
        result: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        current = now or datetime.now()
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                raise ValueError("unknown automation run")
            if run.status != "running":
                raise ValueError("automation run is already finished")
            item = self._require(run.automation_id)
            run.finished_at = current.isoformat()
            run.error = str(error) if error else None
            run.result = dict(result or {})
            item.active_run_id = None
            item.last_error = run.error
            item.next_run = self._next_after(item.schedule, current)
            if error:
                run.status = "failed"
                item.consecutive_failures += 1
                if item.consecutive_failures >= item.max_failures:
                    item.circuit_state = "open"
                    item.circuit_opened_at = current.isoformat()
            else:
                run.status = "completed"
                item.last_success = current.isoformat()
                item.consecutive_failures = 0
                item.circuit_state = "closed"
                item.circuit_opened_at = None
                if item.schedule.startswith("once:"):
                    item.enabled = False
            self._save()
            return {"run": asdict(run), "automation": asdict(item)}

    def execute(
        self,
        automation_id: str,
        runner: Callable[[dict[str, Any]], dict[str, Any] | None],
    ) -> dict[str, Any]:
        run = self.begin_run(automation_id)
        item = asdict(self._require(automation_id))
        try:
            result = runner(item) or {}
        except Exception as exc:
            self.complete_run(run["id"], error=str(exc))
            raise
        return self.complete_run(run["id"], result=result)

    def record_run(self, automation_id: str, *, error: str | None = None) -> dict[str, Any]:
        """Compatibility helper for older callers that report only after execution."""
        run = self.begin_run(automation_id)
        return self.complete_run(run["id"], error=error)["automation"]

    def recover(self, automation_id: str, *, now: datetime | None = None) -> dict[str, Any]:
        current = now or datetime.now()
        with self._lock:
            item = self._require(automation_id)
            if item.circuit_state != "open":
                return asdict(item)
            if not self._recovery_due(item, current):
                raise CircuitOpenError("automation recovery cooldown has not elapsed")
            item.circuit_state = "half_open"
            self._save()
            return asdict(item)

    def delete(self, automation_id: str) -> dict[str, Any]:
        with self._lock:
            item = self._require(automation_id)
            if item.active_run_id:
                raise ValueError("cannot delete automation with an active run")
            removed = asdict(item)
            del self._items[automation_id]
            self._save()
            return removed

    def due(self, now: datetime | None = None) -> list[dict[str, Any]]:
        current = now or datetime.now()
        with self._lock:
            due_items = []
            for item in self._items.values():
                if not item.enabled or not item.next_run or datetime.fromisoformat(item.next_run) > current:
                    continue
                if item.circuit_state == "open" and not self._recovery_due(item, current):
                    continue
                due_items.append(asdict(item))
            return due_items

    def _prepare_circuit(self, item: Automation, now: datetime) -> bool:
        if item.circuit_state == "open":
            if not self._recovery_due(item, now):
                raise CircuitOpenError("automation circuit is open")
            item.circuit_state = "half_open"
        return item.circuit_state == "half_open"

    @staticmethod
    def _recovery_due(item: Automation, now: datetime) -> bool:
        if not item.circuit_opened_at:
            return True
        try:
            opened = datetime.fromisoformat(item.circuit_opened_at)
        except ValueError:
            return True
        return now >= opened + timedelta(minutes=max(1, item.recovery_after_minutes))

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

    def _recover_interrupted_runs(self) -> None:
        changed = False
        now = datetime.now().isoformat()
        with self._lock:
            for run in self._runs.values():
                if run.status != "running":
                    continue
                run.status = "interrupted"
                run.finished_at = now
                run.error = "M.I.C.A stopped before this automation run finished."
                item = self._items.get(run.automation_id)
                if item and item.active_run_id == run.id:
                    item.active_run_id = None
                    item.last_error = run.error
                    item.consecutive_failures += 1
                    if item.consecutive_failures >= item.max_failures:
                        item.circuit_state = "open"
                        item.circuit_opened_at = now
                changed = True
            if changed:
                self._save()

    def _trim_runs(self) -> None:
        while len(self._runs) > 250:
            oldest_id = next(iter(self._runs))
            if self._runs[oldest_id].status == "running":
                break
            del self._runs[oldest_id]

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            allowed_item = Automation.__dataclass_fields__
            for item in raw.get("items", []):
                automation = Automation(**{key: value for key, value in item.items() if key in allowed_item})
                if automation.enabled and automation.next_run is None:
                    automation.next_run = self._next_after(automation.schedule, datetime.now())
                self._items[automation.id] = automation
            allowed_run = AutomationRun.__dataclass_fields__
            for item in raw.get("runs", []):
                run = AutomationRun(**{key: value for key, value in item.items() if key in allowed_run})
                self._runs[run.id] = run
        except Exception:
            self._items = {}
            self._runs = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {
                    "version": 2,
                    "items": [asdict(item) for item in self._items.values()],
                    "runs": [asdict(run) for run in self._runs.values()],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary.replace(self.path)


_scheduler: AutomationScheduler | None = None


def get_automation_scheduler() -> AutomationScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AutomationScheduler()
    return _scheduler
