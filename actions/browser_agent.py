"""Natural-language browser automation via Browser Use."""

from __future__ import annotations

import asyncio
import json
import threading
from typing import Any

from core.external_agent_integrations import run_browser_use_agent


TOOL_DECLARATION = {
    "name": "browser_agent",
    "description": (
        "Runs a natural-language web task with Browser Use and stores the result plus trace "
        "artifact in Jarvis action history. Use for multi-step browser tasks where selectors "
        "are unknown or the web page needs agentic navigation."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "task": {"type": "STRING", "description": "Natural-language browser task"},
            "model": {"type": "STRING", "description": "Optional Browser Use model id"},
            "headless": {"type": "BOOLEAN", "description": "Run without visible browser window"},
            "allowed_domains": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": "Optional domain allow-list, e.g. ['*.github.com']",
            },
            "max_steps": {"type": "INTEGER", "description": "Optional maximum agent steps"},
        },
        "required": ["task"],
    },
    "category": "browser",
    "enabled": True,
}


def _run_coro(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    box: dict[str, Any] = {}

    def runner() -> None:
        try:
            box["result"] = asyncio.run(coro)
        except Exception as exc:
            box["error"] = exc

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join()
    if "error" in box:
        raise box["error"]
    return box.get("result")


def _record(params: dict[str, Any], payload: dict[str, Any]) -> None:
    try:
        from core.action_history import ActionStatus, get_action_history

        get_action_history().record_action(
            "browser_agent",
            "run",
            params,
            result=json.dumps(payload, ensure_ascii=False)[:2000],
            status=ActionStatus.SUCCESS if payload.get("ok") else ActionStatus.FAILED,
        )
    except Exception:
        return


def browser_agent(parameters: dict, response=None, player=None, session_memory=None, speak=None) -> str:
    params = parameters or {}
    task = str(params.get("task", "")).strip()
    allowed_domains = params.get("allowed_domains") or []
    if isinstance(allowed_domains, str):
        allowed_domains = [part.strip() for part in allowed_domains.split(",") if part.strip()]

    result = _run_coro(
        run_browser_use_agent(
            task,
            model=str(params.get("model", "")).strip(),
            headless=bool(params.get("headless", False)),
            allowed_domains=allowed_domains,
            max_steps=params.get("max_steps"),
        )
    )
    payload = result.to_dict()
    _record(params, payload)

    if player:
        player.write_log(f"[browser-agent] {'ok' if result.ok else 'failed'}")

    return json.dumps(payload, indent=2, ensure_ascii=False)
