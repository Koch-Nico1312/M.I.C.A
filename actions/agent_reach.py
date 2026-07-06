"""Optional Agent-Reach CLI wrapper for JARVIS."""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any


TOOL_DECLARATION = {
    "name": "agent_reach",
    "description": (
        "Runs safe Agent-Reach CLI capability checks and read/search commands. "
        "Use doctor/status for diagnostics. Login-state platforms should be configured explicitly."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "doctor | run | install_preview. Defaults to doctor.",
            },
            "args": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": "Arguments for action=run. Only safe read/diagnostic subcommands are allowed by default.",
            },
            "timeout": {"type": "INTEGER", "description": "Command timeout in seconds."},
            "allow_login_state": {
                "type": "BOOLEAN",
                "description": "Allow commands for platforms that may use browser login state/cookies.",
            },
        },
        "required": [],
    },
}


SAFE_SUBCOMMANDS = {
    "doctor",
    "status",
    "web",
    "rss",
    "github",
    "youtube",
    "bilibili",
    "v2ex",
    "search",
}
LOGIN_STATE_SUBCOMMANDS = {
    "twitter",
    "x",
    "reddit",
    "facebook",
    "instagram",
    "xiaohongshu",
    "linkedin",
}


def _agent_reach_executable() -> str | None:
    return shutil.which("agent-reach") or shutil.which("agent_reach")


def _run_agent_reach(args: list[str], timeout: int) -> str:
    executable = _agent_reach_executable()
    if not executable:
        return (
            "Agent-Reach is not installed or not on PATH. "
            "Install it separately with `pip install agent-reach`, then run `agent-reach doctor`."
        )

    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    completed = subprocess.run(
        [executable, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    output = (completed.stdout or "").strip()
    error = (completed.stderr or "").strip()
    if completed.returncode != 0:
        return f"Agent-Reach exited with code {completed.returncode}.\n{error or output}"
    return output or error or "Agent-Reach completed without output."


def _validate_args(args: list[Any], allow_login_state: bool) -> tuple[bool, str]:
    if not args:
        return False, "Please provide Agent-Reach arguments or use action=doctor."
    normalized = [str(arg).strip() for arg in args if str(arg).strip()]
    if not normalized:
        return False, "Please provide non-empty Agent-Reach arguments."
    if any(arg.startswith(("-", "/")) for arg in normalized[:1]):
        return False, "The first Agent-Reach argument must be a subcommand, not a flag."

    subcommand = normalized[0].lower()
    if subcommand in LOGIN_STATE_SUBCOMMANDS and not allow_login_state:
        return (
            False,
            "This Agent-Reach command may use browser login state or cookies. "
            "Set allow_login_state=true only after you intentionally configured that platform.",
        )
    if subcommand not in SAFE_SUBCOMMANDS and subcommand not in LOGIN_STATE_SUBCOMMANDS:
        return (
            False,
            f"Agent-Reach subcommand '{subcommand}' is not allowlisted. "
            "Use doctor/status or add an explicit safe wrapper before running it.",
        )
    return True, ""


def agent_reach(parameters: dict, player=None, speak=None, **kwargs) -> str:
    params = parameters or {}
    action = str(params.get("action", "doctor") or "doctor").strip().lower()
    timeout = int(params.get("timeout") or 60)
    allow_login_state = bool(params.get("allow_login_state", False))

    if action in {"doctor", "status"}:
        return _run_agent_reach(["doctor"], timeout)

    if action == "install_preview":
        return (
            "Agent-Reach is intentionally not vendored into Jarvis. "
            "Preview installation outside Jarvis with: `agent-reach install --dry-run` "
            "or use the upstream safe install guide before enabling login-state platforms."
        )

    if action == "run":
        args = params.get("args") or []
        ok, message = _validate_args(args, allow_login_state=allow_login_state)
        if not ok:
            return message
        return _run_agent_reach([str(arg) for arg in args], timeout)

    return "Unknown Agent-Reach action. Use doctor, status, run, or install_preview."
