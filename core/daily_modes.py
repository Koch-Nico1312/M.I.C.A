"""Daily-driver mode presets for Jarvis."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


MODE_PRESETS: dict[str, dict[str, Any]] = {
    "safe": {
        "security": {
            "permission_profile": "safe",
            "allow_destructive_actions": False,
            "confirmation_medium_risk": True,
            "confirmation_high_risk": True,
        },
        "proactive": {"enabled": False, "mode": "off"},
        "hud": {"enabled": False},
        "ollama": {"fallback_only": True},
    },
    "work": {
        "security": {
            "permission_profile": "normal",
            "allow_destructive_actions": False,
            "confirmation_medium_risk": True,
            "confirmation_high_risk": True,
        },
        "briefing": {"enabled": True, "include_calendar": True, "include_email": True},
        "proactive": {"enabled": True, "mode": "subtle"},
        "rag": {"enabled": True},
    },
    "focus": {
        "security": {
            "permission_profile": "normal",
            "allow_destructive_actions": False,
            "confirmation_medium_risk": False,
            "confirmation_high_risk": True,
        },
        "proactive": {"enabled": False, "mode": "off"},
        "passive_vision": {"enabled": False},
        "hud": {"enabled": False},
    },
    "offline": {
        "security": {
            "permission_profile": "normal",
            "allow_destructive_actions": False,
            "confirmation_medium_risk": True,
            "confirmation_high_risk": True,
        },
        "ollama": {"enabled": True, "fallback_only": False, "auto_start": True},
        "model_router": {"preferred_profile": "local_code", "cost_mode": "economy"},
        "rag": {"enabled": True},
        "cross_device": {"telegram": {"enabled": False}, "discord": {"enabled": False}},
    },
    "admin": {
        "security": {
            "permission_profile": "admin",
            "allow_destructive_actions": True,
            "confirmation_medium_risk": False,
            "confirmation_high_risk": True,
        },
        "proactive": {"enabled": True, "mode": "normal"},
    },
}


def _deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def list_modes() -> dict[str, Any]:
    return {
        "modes": [
            {"name": name, "settings": deepcopy(settings)}
            for name, settings in sorted(MODE_PRESETS.items())
        ]
    }


def apply_mode(mode: str) -> dict[str, Any]:
    key = str(mode or "").lower().strip()
    if key not in MODE_PRESETS:
        return {"error": f"Unknown mode: {mode}", **list_modes()}

    from config.config_loader import get_config

    config = get_config()
    updates = deepcopy(MODE_PRESETS[key])
    changed = config.update_local_settings(updates)

    security = updates.get("security", {})
    try:
        from core.approval_flow import get_approval_flow

        flow = get_approval_flow()
        if security.get("permission_profile"):
            flow.set_permission_level(str(security["permission_profile"]))
        if "confirmation_medium_risk" in security:
            flow.set_require_confirmation_for_medium(bool(security["confirmation_medium_risk"]))
        if "confirmation_high_risk" in security:
            flow.set_require_confirmation_for_high(bool(security["confirmation_high_risk"]))
    except Exception:
        pass

    return {
        "status": "applied",
        "mode": key,
        "updates": updates,
        "changed": changed,
    }
