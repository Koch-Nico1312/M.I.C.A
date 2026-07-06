"""External tool provider action backed by Composio."""

from __future__ import annotations

import json
from typing import Any

from core.external_agent_integrations import ComposioToolProvider


TOOL_DECLARATION = {
    "name": "tool_provider",
    "description": (
        "Loads external authenticated tools through Composio. Use status/list_tools to inspect "
        "available provider tools and execute_tool only when a specific Composio tool slug is known."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "status | list_tools | execute_tool"},
            "user_id": {"type": "STRING", "description": "Stable Composio user id"},
            "toolkits": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": "Composio toolkit names, e.g. ['GITHUB', 'GMAIL']",
            },
            "slug": {"type": "STRING", "description": "Composio tool slug for execute_tool"},
            "arguments": {"type": "OBJECT", "description": "Tool arguments for execute_tool"},
        },
        "required": ["action"],
    },
    "category": "integrations",
    "enabled": True,
}


def _record(action: str, params: dict[str, Any], payload: dict[str, Any]) -> None:
    try:
        from core.action_history import ActionStatus, get_action_history

        get_action_history().record_action(
            "tool_provider",
            action,
            params,
            result=json.dumps(payload, ensure_ascii=False)[:2000],
            status=ActionStatus.SUCCESS if payload.get("ok") else ActionStatus.FAILED,
        )
    except Exception:
        return


def tool_provider(parameters: dict, response=None, player=None, session_memory=None, speak=None) -> str:
    params = parameters or {}
    action = str(params.get("action", "status")).lower().strip()
    provider = ComposioToolProvider()

    if action == "status":
        try:
            provider._get_client()
            payload = {"ok": True, "provider": "composio", "action": "status", "result": "configured"}
        except Exception as exc:
            payload = {"ok": False, "provider": "composio", "action": "status", "error": str(exc)}
    elif action == "list_tools":
        user_id = str(params.get("user_id") or "mica-user")
        toolkits = params.get("toolkits") or []
        if isinstance(toolkits, str):
            toolkits = [part.strip().upper() for part in toolkits.split(",") if part.strip()]
        payload = provider.list_tools(user_id=user_id, toolkits=toolkits).to_dict()
    elif action == "execute_tool":
        payload = provider.execute_tool(
            user_id=str(params.get("user_id") or "mica-user"),
            slug=str(params.get("slug", "")),
            arguments=dict(params.get("arguments") or {}),
        ).to_dict()
    else:
        payload = {"ok": False, "provider": "composio", "action": action, "error": f"Unknown action: {action}"}

    _record(action, params, payload)
    if player:
        player.write_log(f"[tool-provider] {action}: {'ok' if payload.get('ok') else 'failed'}")
    return json.dumps(payload, indent=2, ensure_ascii=False)
