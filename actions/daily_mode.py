"""Action wrapper for daily-driver mode presets."""

from __future__ import annotations

import json

from core.daily_modes import apply_mode, list_modes


def daily_mode(parameters: dict, response=None, player=None, session_memory=None, speak=None) -> str:
    params = parameters or {}
    action = str(params.get("action", "list")).lower().strip()
    if action == "list":
        return json.dumps(list_modes(), indent=2)
    if action == "apply":
        mode = str(params.get("mode", "")).strip()
        result = apply_mode(mode)
        if player and "error" not in result:
            player.write_log(f"[mode] Applied {result['mode']} mode")
        return json.dumps(result, indent=2)
    return "Unknown daily_mode action. Use list or apply."
