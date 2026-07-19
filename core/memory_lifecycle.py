"""Session lifecycle hooks for personal-state freshness and handovers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from core.memory_freshness import MemoryFreshnessManager, get_memory_freshness_manager
from core.project_state import ProjectStateManager, get_project_state_manager


class MemoryLifecycleHooks:
    def __init__(
        self,
        freshness: MemoryFreshnessManager | None = None,
        project_state: ProjectStateManager | None = None,
    ):
        self.freshness = freshness or get_memory_freshness_manager()
        self.project_state = project_state or get_project_state_manager()

    def on_session_start(self, session: dict[str, Any]) -> dict[str, Any]:
        report = self.freshness.report()
        return {
            "event": "session_start",
            "session_id": str(session.get("id") or ""),
            "occurred_at": datetime.now().isoformat(),
            "freshness_status": report["status"],
            "stale_sections": [item["section"] for item in report["stale"]],
        }

    def on_session_end(self, session: dict[str, Any]) -> dict[str, Any]:
        occurred_at = datetime.now()
        handover = {
            "session_id": str(session.get("id") or ""),
            "summary": str(session.get("summary") or "").strip(),
            "open_ends": [str(item) for item in session.get("open_ends", []) if item][:20],
            "recent_files": [str(item) for item in session.get("recent_files", []) if item][:20],
            "created_at": occurred_at.isoformat(),
        }
        self.project_state.update({"last_handover": handover})
        self.freshness.touch(
            "session_context",
            reviewed_at=occurred_at,
            source="session_manager",
            reason="session handover persisted",
        )
        return {"event": "session_end", "occurred_at": occurred_at.isoformat(), "handover": handover}


_hooks: MemoryLifecycleHooks | None = None


def get_memory_lifecycle_hooks() -> MemoryLifecycleHooks:
    global _hooks
    if _hooks is None:
        _hooks = MemoryLifecycleHooks()
    return _hooks
