"""Persistent centralized notification journal and delivery gateway."""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from core.paths import project_path


NOTIFICATION_CENTER_PATH = project_path("data", "notifications.json")


@dataclass
class NotificationEvent:
    id: str
    title: str
    message: str
    priority: str
    source: str
    status: str
    created_at: str
    delivered_at: str | None = None
    dedup_key: str = ""
    error: str | None = None


class NotificationCenter:
    def __init__(self, path: Path = NOTIFICATION_CENTER_PATH):
        self.path = path
        self._lock = threading.RLock()
        self._events: list[NotificationEvent] = []
        self._load()

    def publish(
        self,
        title: str,
        message: str,
        priority: str,
        *,
        source: str = "mica",
        dedup_key: str = "",
        deliver: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if dedup_key:
                existing = next(
                    (item for item in reversed(self._events) if item.dedup_key == dedup_key and item.status == "delivered"),
                    None,
                )
                if existing:
                    return {**asdict(existing), "deduplicated": True}
            event = NotificationEvent(
                id=f"notification-{uuid.uuid4().hex[:10]}",
                title=str(title or "M.I.C.A"),
                message=str(message or ""),
                priority=str(priority or "normal"),
                source=str(source or "mica"),
                status="queued",
                created_at=datetime.now().isoformat(),
                dedup_key=str(dedup_key or ""),
            )
            self._events.append(event)
            self._events = self._events[-500:]
            self._save()

        if deliver is not None:
            try:
                delivered = bool(deliver())
                self._finish(event.id, delivered=delivered)
            except Exception as exc:
                self._finish(event.id, delivered=False, error=str(exc))
        return self.get(event.id) or asdict(event)

    def get(self, event_id: str) -> dict[str, Any] | None:
        with self._lock:
            event = next((item for item in self._events if item.id == event_id), None)
            return asdict(event) if event else None

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            counts: dict[str, int] = {}
            for event in self._events:
                counts[event.status] = counts.get(event.status, 0) + 1
            return {"counts": counts, "events": [asdict(item) for item in reversed(self._events)]}

    def dismiss(self, event_id: str) -> bool:
        with self._lock:
            event = next((item for item in self._events if item.id == event_id), None)
            if event is None:
                return False
            event.status = "dismissed"
            self._save()
            return True

    def _finish(self, event_id: str, *, delivered: bool, error: str | None = None) -> None:
        with self._lock:
            event = next((item for item in self._events if item.id == event_id), None)
            if event is None:
                return
            event.status = "delivered" if delivered else "failed"
            event.delivered_at = datetime.now().isoformat() if delivered else None
            event.error = error or (None if delivered else "delivery backend unavailable")
            self._save()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            allowed = NotificationEvent.__dataclass_fields__
            self._events = [
                NotificationEvent(**{key: value for key, value in item.items() if key in allowed})
                for item in raw.get("events", [])
                if isinstance(item, dict)
            ][-500:]
        except Exception:
            self._events = []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"version": 1, "events": [asdict(item) for item in self._events]}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)


_center: NotificationCenter | None = None


def get_notification_center() -> NotificationCenter:
    global _center
    if _center is None:
        _center = NotificationCenter()
    return _center
