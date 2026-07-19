"""Unified, persistent communications gateway for M.I.C.A.

Telegram, Discord, companion devices and telephone calls share one identity,
history, approval and notification surface.  External credentials remain in
configuration; the persisted gateway state contains only paired identifiers
and redacted message metadata.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from config.config_loader import get_config
from core.cross_device import get_cross_device
from core.notification_center import get_notification_center
from core.paths import project_path
from core.telephony import get_telephony_gateway


COMMUNICATION_STATE_PATH = project_path("data", "communications.json")
TELEGRAM_MEDIA_DIR = project_path("data", "communications", "telegram")


@dataclass
class CommunicationEvent:
    id: str
    channel: str
    direction: str
    sender_id: str
    kind: str
    text: str
    status: str
    created_at: str
    attachment_path: str = ""
    error: str = ""


class CommunicationGateway:
    """Routes external conversations into existing M.I.C.A runtime seams."""

    def __init__(self, path: Path = COMMUNICATION_STATE_PATH, config: Any | None = None):
        self.path = path
        self.config = config or get_config()
        self._lock = threading.RLock()
        self._events: list[CommunicationEvent] = []
        self._paired_identities: dict[str, dict[str, dict[str, str]]] = {}
        self._telegram_offset = 0
        self._command_handler: Callable[[str], Any] | None = None
        self._attachment_handler: Callable[[str, str], Any] | None = None
        self._load()

    def set_command_handler(self, handler: Callable[[str], Any] | None) -> None:
        self._command_handler = handler

    def set_attachment_handler(self, handler: Callable[[str, str], Any] | None) -> None:
        self._attachment_handler = handler

    def _channel_settings(self, channel: str) -> dict[str, Any]:
        value = self.config.get(f"communications.channels.{channel}", None)
        if not isinstance(value, dict):
            value = self.config.get(f"cross_device.{channel}", {})
        return value if isinstance(value, dict) else {}

    def _allowed_senders(self, channel: str) -> set[str]:
        settings = self._channel_settings(channel)
        configured = settings.get("allowed_sender_ids", [])
        if isinstance(configured, str):
            configured = [item.strip() for item in configured.split(",")]
        allowed = {str(item).strip() for item in configured if str(item).strip()}
        legacy = str(settings.get("chat_id") or "").strip()
        if legacy:
            allowed.add(legacy)
        allowed.update(self._paired_identities.get(channel, {}).keys())
        if channel == "phone":
            allowed.update(get_telephony_gateway().status().get("allowed_numbers", []))
        return allowed

    def is_sender_allowed(self, channel: str, sender_id: str) -> bool:
        sender = str(sender_id or "").strip()
        return bool(sender and sender in self._allowed_senders(channel))

    def pair_identity(
        self,
        channel: str,
        sender_id: str,
        *,
        label: str = "",
        confirmed: bool = False,
    ) -> dict[str, Any]:
        channel = str(channel or "").lower().strip()
        sender = str(sender_id or "").strip()
        if channel not in {"telegram", "discord", "companion", "phone"}:
            return {"ok": False, "error": "unsupported channel"}
        if not sender:
            return {"ok": False, "error": "sender_id is required"}
        if not confirmed:
            return {"ok": False, "approval_required": True, "error": "explicit confirmation required"}
        with self._lock:
            self._paired_identities.setdefault(channel, {})[sender] = {
                "label": str(label or sender),
                "paired_at": datetime.now().isoformat(),
            }
            self._save()
        return {"ok": True, "channel": channel, "sender_id": sender, "snapshot": self.snapshot()}

    def revoke_identity(self, channel: str, sender_id: str, *, confirmed: bool = False) -> dict[str, Any]:
        if not confirmed:
            return {"ok": False, "approval_required": True, "error": "explicit confirmation required"}
        with self._lock:
            removed = self._paired_identities.get(str(channel), {}).pop(str(sender_id), None)
            self._save()
        return {"ok": bool(removed), "snapshot": self.snapshot()}

    def snapshot(self) -> dict[str, Any]:
        cross_device = get_cross_device()
        telephony = get_telephony_gateway().status()
        telegram = self._channel_settings("telegram")
        discord = self._channel_settings("discord")
        try:
            from core.smart_home import get_smart_home

            smart_home = get_smart_home().get_status_summary()
        except Exception as exc:
            smart_home = {"connected": False, "error": str(exc)}
        with self._lock:
            return {
                "channels": {
                    "telegram": {
                        "enabled": bool(telegram.get("enabled", False)),
                        "configured": bool(cross_device.telegram_bot),
                        "mode": str(telegram.get("mode") or "polling"),
                        "paired": len(self._allowed_senders("telegram")),
                    },
                    "discord": {
                        "enabled": bool(discord.get("enabled", False)),
                        "configured": bool(cross_device.discord_bot),
                        "paired": len(self._allowed_senders("discord")),
                    },
                    "companion": {
                        "enabled": True,
                        "configured": True,
                        "paired": len(self._allowed_senders("companion")),
                    },
                    "telephony": telephony,
                },
                "smart_home": smart_home,
                "telegram_offset": self._telegram_offset,
                "paired_identities": {
                    channel: [
                        {"sender_id": sender, **metadata}
                        for sender, metadata in identities.items()
                    ]
                    for channel, identities in self._paired_identities.items()
                },
                "events": [asdict(item) for item in reversed(self._events[-100:])],
            }

    def send(
        self,
        channel: str,
        text: str,
        *,
        confirmed: bool = False,
        recipient: str = "",
        kind: str = "message",
    ) -> dict[str, Any]:
        channel = str(channel or "telegram").lower().strip()
        message = str(text or "").strip()
        if not message:
            return {"ok": False, "error": "message is required"}
        if not confirmed:
            return {"ok": False, "approval_required": True, "error": "explicit confirmation required"}
        if channel not in {"telegram", "discord", "both"}:
            return {"ok": False, "error": "unsupported outbound channel"}
        event = self._record(channel, "outbound", recipient, kind, message, "sending")
        try:
            delivered = get_cross_device().sync_send_summary(message, channel)
            self._update_event(event.id, "delivered" if delivered else "failed", "" if delivered else "delivery backend unavailable")
            return {"ok": bool(delivered), "event": self._event_dict(event.id)}
        except Exception as exc:
            self._update_event(event.id, "failed", str(exc))
            return {"ok": False, "error": str(exc), "event": self._event_dict(event.id)}

    def deliver_notification(
        self,
        title: str,
        message: str,
        priority: str = "normal",
        *,
        channels: list[str] | None = None,
        call_number: str = "",
        confirmed_call: bool = False,
    ) -> dict[str, Any]:
        selected = channels or list(self.config.get("communications.proactive.channels", ["telegram"]) or [])
        results: dict[str, Any] = {}
        for channel in selected:
            if channel in {"telegram", "discord"}:
                results[channel] = self.send(channel, f"{title}\n\n{message}", confirmed=True, kind="notification")
        if priority == "urgent" and call_number:
            results["telephony"] = get_telephony_gateway().place_call(
                call_number,
                f"{title}. {message}",
                confirmed=confirmed_call,
                purpose="urgent_notification",
            )
        journal = get_notification_center().publish(
            title,
            message,
            priority,
            source="communications",
            dedup_key=f"communications:{title}:{message}",
            deliver=lambda: any(bool(item.get("ok")) for item in results.values()),
        )
        return {"ok": any(bool(item.get("ok")) for item in results.values()), "deliveries": results, "notification": journal}

    def poll_telegram(self, *, timeout: int = 0) -> dict[str, Any]:
        cross_device = get_cross_device()
        updates = cross_device.sync_get_telegram_updates(self._telegram_offset, timeout)
        results = []
        for update in updates:
            update_id = int(update.get("update_id", 0) or 0)
            self._telegram_offset = max(self._telegram_offset, update_id + 1)
            results.append(self.process_telegram_update(update))
        if updates:
            self._save()
        return {"ok": True, "received": len(updates), "results": results, "offset": self._telegram_offset}

    def process_telegram_update(self, update: dict[str, Any]) -> dict[str, Any]:
        callback = update.get("callback_query") if isinstance(update.get("callback_query"), dict) else None
        message = update.get("message") if isinstance(update.get("message"), dict) else None
        if callback:
            message = callback.get("message") if isinstance(callback.get("message"), dict) else {}
        message = message or {}
        chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
        sender_id = str(chat.get("id") or ((callback or {}).get("from") or {}).get("id") or "")
        if not self.is_sender_allowed("telegram", sender_id):
            self._record("telegram", "inbound", sender_id, "unauthorized", "", "rejected", error="sender is not paired")
            return {"ok": False, "error": "sender is not paired", "sender_id": sender_id}

        if callback:
            result = self._handle_callback(str(callback.get("data") or ""), sender_id)
            get_cross_device().sync_answer_telegram_callback(str(callback.get("id") or ""), "Erledigt" if result.get("ok") else "Nicht möglich")
            return result

        text = str(message.get("text") or message.get("caption") or "").strip()
        voice = message.get("voice") if isinstance(message.get("voice"), dict) else None
        attachment_path = ""
        kind = "text"
        if voice and voice.get("file_id"):
            kind = "voice"
            suffix = ".ogg"
            destination = TELEGRAM_MEDIA_DIR / f"voice-{uuid4().hex[:12]}{suffix}"
            attachment_path = get_cross_device().sync_download_telegram_file(str(voice["file_id"]), destination)
            text = text or "Sprachnachricht"
        event = self._record("telegram", "inbound", sender_id, kind, text, "received", attachment_path=attachment_path)
        result = self._dispatch_inbound(text, sender_id=sender_id, channel="telegram", attachment_path=attachment_path)
        self._update_event(event.id, "queued" if result.get("ok") else "failed", str(result.get("error") or ""))
        reply = str(result.get("reply") or "An M.I.C.A weitergeleitet.")
        bot = get_cross_device().telegram_bot
        if bot:
            loop_result = self._send_telegram_reply(reply, sender_id)
            result["reply_sent"] = loop_result
        return {**result, "event": self._event_dict(event.id)}

    def process_inbound(
        self,
        channel: str,
        sender_id: str,
        text: str,
        *,
        attachment_path: str = "",
    ) -> dict[str, Any]:
        if not self.is_sender_allowed(channel, sender_id):
            return {"ok": False, "error": "sender is not paired"}
        event = self._record(channel, "inbound", sender_id, "message", text, "received", attachment_path=attachment_path)
        result = self._dispatch_inbound(text, sender_id=sender_id, channel=channel, attachment_path=attachment_path)
        self._update_event(event.id, "queued" if result.get("ok") else "failed", str(result.get("error") or ""))
        return {**result, "event": self._event_dict(event.id)}

    def _dispatch_inbound(self, text: str, *, sender_id: str, channel: str, attachment_path: str = "") -> dict[str, Any]:
        command = str(text or "").strip()
        lowered = command.lower()
        if lowered in {"/start", "/help", "hilfe"}:
            return {"ok": True, "handled": True, "reply": "M.I.C.A ist verbunden. Befehle: /status, /approvals, /approve TOOL ACTION, /deny TOOL ACTION. Freier Text wird als Aufgabe übergeben."}
        if lowered == "/status":
            pending = len(self._pending_approvals())
            return {"ok": True, "handled": True, "reply": f"M.I.C.A ist online. {pending} Freigabe(n) offen."}
        if lowered == "/approvals":
            pending = self._pending_approvals()
            if not pending:
                return {"ok": True, "handled": True, "reply": "Keine offenen Freigaben."}
            lines = [f"{item.get('tool_name')} · {item.get('action')} · {item.get('risk_level')}" for item in pending[:8]]
            return {"ok": True, "handled": True, "reply": "Offene Freigaben:\n" + "\n".join(lines)}
        parts = command.split(maxsplit=2)
        if len(parts) == 3 and parts[0].lower() in {"/approve", "/deny"}:
            return self._decide_approval(parts[0].lower() == "/approve", parts[1], parts[2], sender_id)
        if attachment_path and self._attachment_handler:
            self._start_callback(self._attachment_handler, attachment_path, channel, name="MICACommunicationAttachment")
        if self._command_handler:
            contextual = f"[{channel} von {sender_id}] {command}"
            if attachment_path:
                contextual += f"\nLokaler Anhang: {attachment_path}"
            self._start_callback(self._command_handler, contextual, name="MICACommunicationCommand")
            return {"ok": True, "handled": False, "reply": "An M.I.C.A weitergeleitet."}
        return {"ok": False, "error": "M.I.C.A command handler is not connected"}

    def _handle_callback(self, data: str, sender_id: str) -> dict[str, Any]:
        parts = data.split(":", 3)
        if len(parts) == 4 and parts[0] == "approval" and parts[1] in {"approve", "deny"}:
            return self._decide_approval(parts[1] == "approve", parts[2], parts[3], sender_id)
        return {"ok": False, "error": "unknown callback"}

    def _decide_approval(self, approve: bool, tool_name: str, action: str, sender_id: str) -> dict[str, Any]:
        from core.approval_flow import get_approval_flow

        flow = get_approval_flow()
        pending = next((item for item in flow.get_pending_requests() if item.tool_name == tool_name and item.action == action), None)
        if not pending:
            return {"ok": False, "error": "approval request not found"}
        if approve:
            pending.approve(reason="Approved through paired communication channel", decided_by=f"telegram:{sender_id}")
        else:
            pending.deny(reason="Denied through paired communication channel", decided_by=f"telegram:{sender_id}")
        return {"ok": True, "approved": approve, "reply": "Freigabe erteilt." if approve else "Freigabe abgelehnt."}

    def _pending_approvals(self) -> list[dict[str, Any]]:
        try:
            from core.approval_flow import get_approval_flow

            return [item.to_dict() for item in get_approval_flow().get_pending_requests()]
        except Exception:
            return []

    def _send_telegram_reply(self, text: str, chat_id: str) -> bool:
        bot = get_cross_device().telegram_bot
        if not bot:
            return False
        import asyncio

        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(bot.send_message(text, parse_mode="", chat_id=chat_id))
        finally:
            loop.close()

    @staticmethod
    def _start_callback(callback: Callable[..., Any], *args: Any, name: str) -> None:
        threading.Thread(target=callback, args=args, daemon=True, name=name).start()

    def _record(
        self,
        channel: str,
        direction: str,
        sender_id: str,
        kind: str,
        text: str,
        status: str,
        *,
        attachment_path: str = "",
        error: str = "",
    ) -> CommunicationEvent:
        event = CommunicationEvent(
            id=f"communication-{uuid4().hex[:12]}",
            channel=str(channel),
            direction=str(direction),
            sender_id=str(sender_id),
            kind=str(kind),
            text=str(text)[:4000],
            status=str(status),
            created_at=datetime.now().isoformat(),
            attachment_path=str(attachment_path),
            error=str(error),
        )
        with self._lock:
            self._events.append(event)
            self._events = self._events[-500:]
            self._save()
        return event

    def _update_event(self, event_id: str, status: str, error: str = "") -> None:
        with self._lock:
            event = next((item for item in self._events if item.id == event_id), None)
            if event:
                event.status = status
                event.error = error
                self._save()

    def _event_dict(self, event_id: str) -> dict[str, Any]:
        with self._lock:
            event = next((item for item in self._events if item.id == event_id), None)
            return asdict(event) if event else {}

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            allowed = CommunicationEvent.__dataclass_fields__
            self._events = [
                CommunicationEvent(**{key: value for key, value in item.items() if key in allowed})
                for item in raw.get("events", [])
                if isinstance(item, dict)
            ][-500:]
            identities = raw.get("paired_identities", {})
            self._paired_identities = identities if isinstance(identities, dict) else {}
            self._telegram_offset = int(raw.get("telegram_offset", 0) or 0)
        except Exception:
            self._events = []
            self._paired_identities = {}
            self._telegram_offset = 0

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {
                    "version": 1,
                    "telegram_offset": self._telegram_offset,
                    "paired_identities": self._paired_identities,
                    "events": [asdict(item) for item in self._events],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary.replace(self.path)


_communication_gateway: CommunicationGateway | None = None


def get_communication_gateway() -> CommunicationGateway:
    global _communication_gateway
    if _communication_gateway is None:
        _communication_gateway = CommunicationGateway()
    return _communication_gateway


def reset_communication_gateway() -> None:
    global _communication_gateway
    _communication_gateway = None


__all__ = ["CommunicationEvent", "CommunicationGateway", "get_communication_gateway", "reset_communication_gateway"]
