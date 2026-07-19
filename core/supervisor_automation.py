"""Local, deduplicated automation rules for the solo supervisor inbox."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from core.paths import project_path


SUPERVISOR_AUTOMATION_PATH = project_path("data", "supervisor_automation.json")
PRIORITY_SCORE = {"low": 1, "normal": 2, "high": 3, "urgent": 4}


@dataclass
class SupervisorAutomationSettings:
    enabled: bool = True
    desktop_notifications: bool = False
    min_priority: str = "high"
    quiet_start: int = 22
    quiet_end: int = 7
    focus_mode: bool = False
    read_ids: list[str] = field(default_factory=list)
    dismissed_ids: list[str] = field(default_factory=list)
    notified_signatures: list[str] = field(default_factory=list)
    last_evaluated_at: str = ""


class SupervisorAutomationManager:
    def __init__(self, path: Path = SUPERVISOR_AUTOMATION_PATH):
        self.path = path
        self._lock = threading.RLock()
        self.settings = SupervisorAutomationSettings()
        self._load()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return asdict(self.settings)

    def configure(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            if "enabled" in payload:
                self.settings.enabled = bool(payload["enabled"])
            if "desktop_notifications" in payload:
                self.settings.desktop_notifications = bool(payload["desktop_notifications"])
            if "focus_mode" in payload:
                self.settings.focus_mode = bool(payload["focus_mode"])
            if "min_priority" in payload:
                priority = str(payload["min_priority"])
                if priority not in PRIORITY_SCORE:
                    raise ValueError("unknown notification priority")
                self.settings.min_priority = priority
            for key in ("quiet_start", "quiet_end"):
                if key in payload:
                    value = int(payload[key])
                    if not 0 <= value <= 23:
                        raise ValueError("quiet hours must be between 0 and 23")
                    setattr(self.settings, key, value)
            self._save()
            return self.snapshot()

    def dismiss(self, item_id: str) -> dict[str, Any]:
        with self._lock:
            if item_id and item_id not in self.settings.dismissed_ids:
                self.settings.dismissed_ids.append(item_id)
                self.settings.dismissed_ids = self.settings.dismissed_ids[-100:]
                self._save()
            return self.snapshot()

    def mark_read(self, item_id: str) -> dict[str, Any]:
        with self._lock:
            if item_id and item_id not in self.settings.read_ids:
                self.settings.read_ids.append(item_id)
                self.settings.read_ids = self.settings.read_ids[-200:]
                self._save()
            return self.snapshot()

    def mark_all_read(self, item_ids: list[str]) -> dict[str, Any]:
        with self._lock:
            self.settings.read_ids = list(dict.fromkeys([*self.settings.read_ids, *(str(item) for item in item_ids if item)]))[-200:]
            self._save()
            return self.snapshot()

    def restore(self, payload: dict[str, Any]) -> dict[str, Any]:
        allowed = SupervisorAutomationSettings.__dataclass_fields__
        with self._lock:
            self.settings = SupervisorAutomationSettings(**{key: value for key, value in payload.items() if key in allowed})
            self._save()
            return self.snapshot()

    def evaluate(
        self,
        inbox: list[dict[str, Any]],
        *,
        now: datetime | None = None,
        notifier: Callable[[str, str, str], bool] | None = None,
    ) -> dict[str, Any]:
        now = now or datetime.now()
        with self._lock:
            threshold = 4 if self.settings.focus_mode else PRIORITY_SCORE.get(self.settings.min_priority, 3)
            quiet = self._is_quiet_hour(now.hour)
            candidates = []
            notifications = []
            for item in inbox:
                item_id = str(item.get("id") or "")
                priority = str(item.get("priority") or "normal")
                signature = f"{item_id}:{item.get('title', '')}:{item.get('detail', '')}"
                if item_id in self.settings.dismissed_ids or PRIORITY_SCORE.get(priority, 0) < threshold:
                    continue
                candidates.append(item)
                if (
                    self.settings.enabled
                    and self.settings.desktop_notifications
                    and not quiet
                    and signature not in self.settings.notified_signatures
                    and notifier is not None
                ):
                    delivered = bool(notifier(str(item.get("title") or "Mika Supervisor"), str(item.get("detail") or ""), priority))
                    notifications.append({"id": item_id, "delivered": delivered})
                    if delivered:
                        self.settings.notified_signatures.append(signature)
            self.settings.notified_signatures = self.settings.notified_signatures[-200:]
            self.settings.last_evaluated_at = now.isoformat()
            self._save()
            return {
                "settings": self.snapshot(),
                "quiet": quiet,
                "candidate_count": len(candidates),
                "candidates": candidates,
                "notifications": notifications,
            }

    def _is_quiet_hour(self, hour: int) -> bool:
        start, end = self.settings.quiet_start, self.settings.quiet_end
        if start == end:
            return False
        return start <= hour < end if start < end else hour >= start or hour < end

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            allowed = SupervisorAutomationSettings.__dataclass_fields__
            self.settings = SupervisorAutomationSettings(**{key: value for key, value in raw.items() if key in allowed})
        except Exception:
            self.settings = SupervisorAutomationSettings()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(self.settings), ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)


_manager: SupervisorAutomationManager | None = None
_manager_lock = threading.Lock()


def get_supervisor_automation_manager() -> SupervisorAutomationManager:
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = SupervisorAutomationManager()
    return _manager
