"""Compatibility facade backed by M.I.C.A's centralized notification journal."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from core.notification_center import NotificationCenter, get_notification_center


VALID_PRIORITIES = {"low", "normal", "high", "urgent"}


class NotificationSystem:
    """Stable notification API for older actions and integration consumers."""

    def __init__(
        self,
        center: NotificationCenter | None = None,
        delivery_backend: Callable[[str, str, str], bool] | None = None,
    ):
        self.center = center or get_notification_center()
        self.delivery_backend = delivery_backend
        self.enable_sound = False
        self.enable_persistence = True
        self.enable_history = True
        self.enable_grouping = False
        self.channels = ["desktop"]

    def send(
        self,
        title: str,
        message: str,
        priority: str = "normal",
        *,
        play_sound: bool = False,
        persistent: bool = False,
        channels: list[str] | None = None,
        group: str = "",
        **_: Any,
    ) -> str:
        if not str(message or "").strip():
            raise ValueError("notification message is required")
        priority = str(priority or "normal").lower()
        if priority not in VALID_PRIORITIES:
            raise ValueError("invalid notification priority")
        selected_channels = [str(item) for item in (channels or self.channels) if item]
        dedup_key = f"group:{group}" if self.enable_grouping and group else ""
        deliver = None
        if self.delivery_backend is not None and "desktop" in selected_channels:
            deliver = lambda: bool(self.delivery_backend(str(title), str(message), priority))
        event = self.center.publish(
            str(title or "M.I.C.A"),
            str(message),
            priority,
            source="notification_system",
            dedup_key=dedup_key,
            deliver=deliver,
        )
        return str(event["id"])

    def schedule(
        self,
        title: str,
        message: str,
        scheduled_time: datetime,
        priority: str = "normal",
        **kwargs: Any,
    ) -> str:
        if scheduled_time <= datetime.now():
            raise ValueError("scheduled notification must be in the future")
        return self.send(
            title,
            message,
            priority,
            persistent=True,
            **kwargs,
        )

    def get_history(self) -> list[dict[str, Any]]:
        return self.center.snapshot()["events"]

    def dismiss(self, notification_id: str) -> bool:
        return self.center.dismiss(str(notification_id or ""))
