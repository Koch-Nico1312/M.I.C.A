"""Persistent solo-project state for the M.I.C.A supervisor."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paths import project_path


PROJECT_STATE_PATH = project_path("data", "project_state.json")
VALID_TABS = {"hub", "tasks", "agents", "flows", "approvals", "activity"}
DEFAULT_DASHBOARD_WIDGETS = ["supervisor", "approvals", "runs", "models", "activity"]
VALID_DASHBOARD_WIDGETS = set(DEFAULT_DASHBOARD_WIDGETS)
DEFAULT_RUN_BUDGET = {"max_steps": 8, "max_minutes": 60, "max_agent_calls": 20, "stop_on_limit": True}


def _now() -> str:
    return datetime.now().isoformat()


@dataclass
class ProjectState:
    version: int = 1
    active_project_id: str = ""
    objective: str = ""
    focus: str = ""
    status: str = "ready"
    last_tab: str = "hub"
    pipeline_ids: list[str] = field(default_factory=list)
    agent_ids: list[str] = field(default_factory=list)
    artifact_ids: list[str] = field(default_factory=list)
    favorite_commands: list[str] = field(default_factory=list)
    recent_commands: list[str] = field(default_factory=list)
    saved_views: dict[str, dict[str, Any]] = field(default_factory=dict)
    dashboard_widgets: list[str] = field(default_factory=lambda: list(DEFAULT_DASHBOARD_WIDGETS))
    run_budget: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_RUN_BUDGET))
    checkpoint: str = ""
    updated_at: str = field(default_factory=_now)


class ProjectStateManager:
    """Owns the small durable state needed to resume a personal project."""

    def __init__(self, path: Path = PROJECT_STATE_PATH):
        self.path = path
        self._lock = threading.RLock()
        self._state = ProjectState()
        self._load()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return asdict(self._state)

    def update(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            for key in ("active_project_id", "objective", "focus", "status", "checkpoint"):
                if key in payload:
                    setattr(self._state, key, str(payload.get(key) or "").strip())
            if "last_tab" in payload:
                tab = str(payload.get("last_tab") or "hub")
                self._state.last_tab = tab if tab in VALID_TABS else "hub"
            for key in ("pipeline_ids", "agent_ids", "artifact_ids", "favorite_commands", "recent_commands"):
                if key in payload and isinstance(payload[key], list):
                    values = list(dict.fromkeys(str(item) for item in payload[key] if item))
                    setattr(self._state, key, values[-20:] if key == "recent_commands" else values)
            if "dashboard_widgets" in payload and isinstance(payload["dashboard_widgets"], list):
                self._state.dashboard_widgets = list(dict.fromkeys(
                    str(item) for item in payload["dashboard_widgets"] if str(item) in VALID_DASHBOARD_WIDGETS
                ))
            if "saved_views" in payload and isinstance(payload["saved_views"], dict):
                self._state.saved_views = {
                    str(key): value for key, value in payload["saved_views"].items()
                    if isinstance(value, dict)
                }
            if "run_budget" in payload and isinstance(payload["run_budget"], dict):
                raw_budget = payload["run_budget"]
                self._state.run_budget = {
                    "max_steps": max(1, min(50, int(raw_budget.get("max_steps", self._state.run_budget.get("max_steps", 8))))),
                    "max_minutes": max(1, min(1440, int(raw_budget.get("max_minutes", self._state.run_budget.get("max_minutes", 60))))),
                    "max_agent_calls": max(1, min(500, int(raw_budget.get("max_agent_calls", self._state.run_budget.get("max_agent_calls", 20))))),
                    "stop_on_limit": bool(raw_budget.get("stop_on_limit", self._state.run_budget.get("stop_on_limit", True))),
                }
            self._state.updated_at = _now()
            self._save()
            return self.snapshot()

    def checkpoint(self, note: str, *, focus: str = "") -> dict[str, Any]:
        return self.update({"checkpoint": note, **({"focus": focus} if focus else {})})

    def reconcile(
        self,
        *,
        active_project_id: str = "",
        pipeline_ids: list[str] | None = None,
        agent_ids: list[str] | None = None,
        artifact_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        current = self.snapshot()
        return self.update(
            {
                "active_project_id": active_project_id or current["active_project_id"],
                "pipeline_ids": pipeline_ids if pipeline_ids is not None else current["pipeline_ids"],
                "agent_ids": agent_ids if agent_ids is not None else current["agent_ids"],
                "artifact_ids": artifact_ids if artifact_ids is not None else current["artifact_ids"],
            }
        )

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            allowed = ProjectState.__dataclass_fields__
            self._state = ProjectState(**{key: value for key, value in raw.items() if key in allowed})
        except Exception:
            self._state = ProjectState()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(self._state), ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)


_manager: ProjectStateManager | None = None
_manager_lock = threading.Lock()


def get_project_state_manager() -> ProjectStateManager:
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = ProjectStateManager()
    return _manager
