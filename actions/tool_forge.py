"""M.I.C.A action wrapper for controlled generated tools and personality changes."""

from __future__ import annotations

import json
from typing import Any

from core.tool_forge import get_tool_forge


TOOL_DECLARATION = {
    "name": "tool_forge",
    "description": (
        "Controlled Tool-Maker/Forge system. Use when M.I.C.A lacks a requested capability. "
        "It plans a generated plugin, writes it only into plugins/generated/<tool_name>/ after "
        "plan approval, validates it, and activates it only after a second approval. Also handles "
        "personality soul.md change proposals as diffs with versioned backups."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "plan | forge | validate | activate | status | "
                    "personality_propose | personality_apply"
                ),
            },
            "description": {
                "type": "STRING",
                "description": "Capability to build when action=plan.",
            },
            "tool_name": {
                "type": "STRING",
                "description": "Short snake_case tool name for plan, validate, or activate.",
            },
            "permissions": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": "Requested permission strings, e.g. text:read or network:http.",
            },
            "plan_id": {"type": "STRING", "description": "Plan id returned by action=plan."},
            "approved_plan": {
                "type": "BOOLEAN",
                "description": "Must be true before code is generated into quarantine.",
            },
            "activation_approved": {
                "type": "BOOLEAN",
                "description": "Must be true before a validated quarantined plugin is enabled.",
            },
            "plugin_code": {
                "type": "STRING",
                "description": "Optional complete plugin.py code. If omitted, a safe scaffold is used.",
            },
            "test_code": {
                "type": "STRING",
                "description": "Optional complete generated plugin test code.",
            },
            "use_model": {
                "type": "BOOLEAN",
                "description": "Allow the forge to ask the routed code_edit model to draft plugin code/tests.",
            },
            "request": {
                "type": "STRING",
                "description": "Personality change request for personality_propose.",
            },
            "proposed_content": {
                "type": "STRING",
                "description": "Optional complete proposed soul.md content.",
            },
            "proposal_id": {
                "type": "STRING",
                "description": "Proposal id returned by personality_propose.",
            },
            "approved": {
                "type": "BOOLEAN",
                "description": "Must be true before a personality proposal is applied.",
            },
        },
        "required": ["action"],
    },
}


def tool_forge(
    parameters: dict[str, Any],
    response=None,
    player=None,
    session_memory=None,
    speak=None,
) -> str:
    params = parameters or {}
    action = str(params.get("action", "status")).strip().lower()
    forge = get_tool_forge()

    if action == "plan":
        result = forge.plan_tool(
            description=str(params.get("description", "")),
            tool_name=str(params.get("tool_name", "")),
            permissions=list(params.get("permissions") or ["text:read"]),
        )
    elif action == "forge":
        result = forge.forge_tool(
            str(params.get("plan_id", "")),
            approved_plan=bool(params.get("approved_plan", False)),
            plugin_code=str(params.get("plugin_code", "")),
            test_code=str(params.get("test_code", "")),
            use_model=bool(params.get("use_model", False)),
        )
    elif action == "validate":
        result = forge.validate_tool(str(params.get("tool_name", ""))).to_dict()
    elif action == "activate":
        result = forge.activate_tool(
            str(params.get("tool_name", "")),
            activation_approved=bool(params.get("activation_approved", False)),
        )
    elif action == "status":
        result = forge.status()
    elif action == "personality_propose":
        result = forge.propose_personality_change(
            request=str(params.get("request", "")),
            proposed_content=str(params.get("proposed_content", "")),
        )
    elif action == "personality_apply":
        result = forge.apply_personality_change(
            str(params.get("proposal_id", "")),
            approved=bool(params.get("approved", False)),
        )
    else:
        result = {"ok": False, "error": f"Unknown tool_forge action: {action}"}

    try:
        from core.action_history import ActionStatus, get_action_history

        get_action_history().record_action(
            "tool_forge",
            action,
            {k: v for k, v in params.items() if k not in {"plugin_code", "test_code"}},
            result=json.dumps(result, ensure_ascii=False)[:2000],
            status=ActionStatus.SUCCESS if not result.get("error") else ActionStatus.FAILED,
        )
    except Exception:
        pass

    if player:
        try:
            player.write_log(f"[Forge] {action}: {'ok' if not result.get('error') else 'blocked'}")
        except Exception:
            pass

    return json.dumps(result, indent=2, ensure_ascii=False)
