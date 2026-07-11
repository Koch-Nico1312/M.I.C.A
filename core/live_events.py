"""Small in-process event stream used by the local M.I.C.A dashboard."""

from __future__ import annotations

import threading
import time
from collections import deque
from copy import deepcopy
from datetime import datetime
from typing import Any


class LiveEventBus:
    """Thread-safe bounded event stream with resumable sequence numbers."""

    def __init__(self, max_events: int = 500):
        self._events: deque[dict[str, Any]] = deque(maxlen=max_events)
        self._condition = threading.Condition()
        self._sequence = 0

    def publish(self, event_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._condition:
            self._sequence += 1
            event = {
                "id": self._sequence,
                "type": str(event_type or "update"),
                "timestamp": datetime.now().isoformat(),
                "payload": deepcopy(payload or {}),
            }
            self._events.append(event)
            self._condition.notify_all()
            return deepcopy(event)

    def events_after(self, sequence: int = 0) -> list[dict[str, Any]]:
        with self._condition:
            return [deepcopy(item) for item in self._events if int(item["id"]) > sequence]

    def wait(self, sequence: int = 0, timeout: float = 20.0) -> list[dict[str, Any]]:
        deadline = time.monotonic() + max(0.0, timeout)
        with self._condition:
            while self._sequence <= sequence:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return []
                self._condition.wait(remaining)
            return [deepcopy(item) for item in self._events if int(item["id"]) > sequence]

    def snapshot(self, limit: int = 100) -> dict[str, Any]:
        with self._condition:
            items = list(self._events)[-max(1, int(limit)) :]
            return {"sequence": self._sequence, "events": deepcopy(items)}


_event_bus: LiveEventBus | None = None
_event_bus_lock = threading.Lock()


def get_live_event_bus() -> LiveEventBus:
    global _event_bus
    if _event_bus is None:
        with _event_bus_lock:
            if _event_bus is None:
                _event_bus = LiveEventBus()
    return _event_bus
