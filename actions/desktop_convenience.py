"""Desktop convenience controls: autostart, clipboard, identity, and wake word."""

from __future__ import annotations

import json
from typing import Any

from core.app_autostart import AppAutostartManager
from core.assistant_identity import get_assistant_identity_manager
from core.clipboard_history import get_clipboard_history
from core.wake_word import configure_wake_word_detector, get_wake_word_detector


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _entry(item: Any) -> dict[str, Any]:
    return {
        "content": str(item.content),
        "content_type": str(item.content_type),
        "timestamp": item.timestamp.isoformat(),
    }


def desktop_convenience(parameters: dict, player=None, speak=None, **kwargs) -> str:
    params = parameters or {}
    action = str(params.get("action") or "status").strip().lower().replace("-", "_")
    identity = get_assistant_identity_manager()
    autostart = AppAutostartManager()
    clipboard = get_clipboard_history()
    try:
        if action == "status":
            return _json(
                {
                    "autostart": autostart.status(),
                    "clipboard_monitoring": clipboard.is_monitoring(),
                    "identity": identity.snapshot(),
                    "wake_word": get_wake_word_detector().status(),
                }
            )
        if action == "autostart_preview":
            return _json(autostart.preview())
        if action == "autostart_enable":
            return _json(autostart.enable())
        if action == "autostart_disable":
            return _json(autostart.disable())
        if action == "clipboard_read":
            import pyperclip

            return _json({"content": str(pyperclip.paste() or "")})
        if action == "clipboard_write":
            content = str(params.get("content") or "")
            if not content:
                raise ValueError("clipboard content is required")
            if not clipboard.set_content(content):
                raise RuntimeError("clipboard backend is unavailable")
            return _json({"written": True, "characters": len(content)})
        if action in {"clipboard_start", "clipboard_stop"}:
            clipboard.start_monitoring() if action.endswith("start") else clipboard.stop_monitoring()
            return _json({"monitoring": clipboard.is_monitoring()})
        if action == "clipboard_history":
            limit = max(1, min(100, int(params.get("limit", 10))))
            return _json({"entries": [_entry(item) for item in clipboard.get_recent(limit)]})
        if action == "clipboard_search":
            return _json({"entries": [_entry(item) for item in clipboard.search(str(params.get("query") or ""))]})
        if action == "clipboard_clear":
            clipboard.clear_history()
            return _json({"cleared": True})
        if action == "identity_get":
            return _json(identity.snapshot())
        if action == "identity_set":
            from core.voice_conversation import get_voice_conversation_mode

            aliases = params.get("aliases") if isinstance(params.get("aliases"), list) else None
            updated = identity.configure(
                display_name=params.get("display_name"),
                wake_word=params.get("wake_word"),
                aliases=aliases,
            )
            get_voice_conversation_mode().configure(wakeword=updated["wake_word"])
            return _json(updated)
        if action == "wakeword_status":
            return _json(get_wake_word_detector().status())
        if action == "wakeword_configure":
            from core.voice_conversation import get_voice_conversation_mode

            detector = configure_wake_word_detector(
                engine=str(params.get("engine") or "auto"),
                model_path=str(params.get("model_path") or ""),
                threshold=float(params.get("threshold", 0.5)),
                access_key=str(params.get("access_key") or ""),
            )
            status = detector.status()
            get_voice_conversation_mode().configure(
                wakeword_enabled=status["available"],
                wakeword=identity.snapshot()["wake_word"],
            )
            return _json(status)
        raise ValueError("unknown desktop convenience action")
    except Exception as exc:
        return _json({"success": False, "action": action, "error": str(exc)})


TOOL_DECLARATION = {
    "name": "desktop_convenience",
    "description": "Controls M.I.C.A autostart, clipboard history, assistant naming, and real wake-word detection.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "status | autostart_preview | autostart_enable | autostart_disable | clipboard_read | clipboard_write | clipboard_start | clipboard_stop | clipboard_history | clipboard_search | clipboard_clear | identity_get | identity_set | wakeword_status | wakeword_configure"},
            "content": {"type": "STRING"},
            "query": {"type": "STRING"},
            "limit": {"type": "INTEGER"},
            "display_name": {"type": "STRING"},
            "wake_word": {"type": "STRING"},
            "aliases": {"type": "ARRAY", "items": {"type": "STRING"}},
            "engine": {"type": "STRING"},
            "model_path": {"type": "STRING"},
            "threshold": {"type": "NUMBER"},
        },
        "required": [],
    },
}
