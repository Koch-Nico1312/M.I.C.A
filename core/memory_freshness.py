"""Persistent freshness tracking for M.I.C.A's personal context."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from core.paths import project_path


MEMORY_FRESHNESS_PATH = project_path("data", "memory_freshness.json")
DEFAULT_FRESHNESS_POLICIES = {
    "current_state": 7,
    "project_status": 14,
    "telos.goals": 30,
    "telos.strategies": 30,
    "telos.mission": 90,
    "telos.beliefs": 90,
    "ideal_state": 90,
    "session_context": 1,
}


def _now() -> datetime:
    return datetime.now()


@dataclass
class FreshnessRecord:
    section: str
    max_age_days: int
    reviewed_at: str = ""
    source: str = "personal_state"
    reason: str = ""


class MemoryFreshnessManager:
    """Tracks when constitutional context was last reviewed, not merely read."""

    def __init__(
        self,
        path: Path = MEMORY_FRESHNESS_PATH,
        policies: dict[str, int] | None = None,
    ):
        self.path = path
        self._lock = threading.RLock()
        self._records: dict[str, FreshnessRecord] = {}
        self._policies = dict(policies or DEFAULT_FRESHNESS_POLICIES)
        self._load()
        self._ensure_policies()

    def touch(
        self,
        section: str,
        *,
        reviewed_at: datetime | None = None,
        source: str = "personal_state",
        reason: str = "updated",
    ) -> dict[str, Any]:
        key = str(section or "").strip().lower()
        if not key:
            raise ValueError("freshness section is required")
        with self._lock:
            current = self._records.get(key)
            record = FreshnessRecord(
                section=key,
                max_age_days=(current.max_age_days if current else self._policies.get(key, 30)),
                reviewed_at=(reviewed_at or _now()).isoformat(),
                source=str(source or "personal_state"),
                reason=str(reason or "updated"),
            )
            self._records[key] = record
            self._save()
            return self._status(record, now=reviewed_at or _now())

    def report(self, *, now: datetime | None = None) -> dict[str, Any]:
        current = now or _now()
        with self._lock:
            items = [self._status(record, now=current) for record in self._records.values()]
        items.sort(key=lambda item: (not item["stale"], -item["age_days"], item["section"]))
        stale = [item for item in items if item["stale"]]
        missing = [item for item in items if not item["reviewed_at"]]
        return {
            "status": "stale" if stale else "fresh",
            "checked_at": current.isoformat(),
            "stale_count": len(stale),
            "missing_count": len(missing),
            "items": items,
            "stale": stale,
        }

    def _ensure_policies(self) -> None:
        changed = False
        with self._lock:
            for section, max_age_days in self._policies.items():
                if section not in self._records:
                    self._records[section] = FreshnessRecord(section, max(1, int(max_age_days)))
                    changed = True
                else:
                    self._records[section].max_age_days = max(1, int(max_age_days))
            if changed and self.path.exists():
                self._save()

    @staticmethod
    def _status(record: FreshnessRecord, *, now: datetime) -> dict[str, Any]:
        reviewed_at = None
        if record.reviewed_at:
            try:
                reviewed_at = datetime.fromisoformat(record.reviewed_at)
            except ValueError:
                reviewed_at = None
        age = now - reviewed_at if reviewed_at else timedelta.max
        age_days = max(0, int(age.total_seconds() // 86400)) if reviewed_at else 999999
        return {
            **asdict(record),
            "age_days": age_days,
            "stale": reviewed_at is None or age > timedelta(days=record.max_age_days),
            "due_at": (reviewed_at + timedelta(days=record.max_age_days)).isoformat()
            if reviewed_at
            else None,
        }

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            for item in raw.get("records", []):
                if isinstance(item, dict) and item.get("section"):
                    record = FreshnessRecord(
                        section=str(item["section"]),
                        max_age_days=max(1, int(item.get("max_age_days", 30))),
                        reviewed_at=str(item.get("reviewed_at") or ""),
                        source=str(item.get("source") or "personal_state"),
                        reason=str(item.get("reason") or ""),
                    )
                    self._records[record.section] = record
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            self._records = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {"version": 1, "records": [asdict(item) for item in self._records.values()]},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary.replace(self.path)


_manager: MemoryFreshnessManager | None = None
_manager_lock = threading.Lock()


def get_memory_freshness_manager() -> MemoryFreshnessManager:
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = MemoryFreshnessManager()
    return _manager
