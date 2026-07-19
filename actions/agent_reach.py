"""Safe integration for the current Agent-Reach capability CLI.

Agent-Reach is an installer, configuration helper, health checker, and skill
bundle.  Platform access is intentionally performed by its selected upstream
tools (for example ``gh``, ``yt-dlp`` or an MCP server), not by commands such
as ``agent-reach github``.  This wrapper only exposes real upstream commands
and keeps installation or credential changes behind an explicit manual step.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any


TOOL_DECLARATION = {
    "name": "agent_reach",
    "description": (
        "Checks and maintains the optional Agent-Reach capability layer. "
        "It exposes diagnostics, version/update checks, and explicit transcription; "
        "platform content is handled by M.I.C.A's dedicated tools."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "doctor | status | capabilities | version | watch | check_update | "
                    "transcribe | run | install_preview | configure_preview. Defaults to doctor."
                ),
            },
            "args": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": (
                    "Compatibility arguments for action=run. Only the real read-only commands "
                    "doctor, watch, version, and check-update are accepted."
                ),
            },
            "source": {
                "type": "STRING",
                "description": "Audio/video URL or local path for action=transcribe.",
            },
            "provider": {
                "type": "STRING",
                "description": "auto | groq | openai for action=transcribe. Defaults to auto.",
            },
            "output": {
                "type": "STRING",
                "description": "Optional transcript output file for action=transcribe.",
            },
            "json": {
                "type": "BOOLEAN",
                "description": "Request machine-readable doctor output. Defaults to true.",
            },
            "timeout": {"type": "INTEGER", "description": "Command timeout in seconds."},
        },
        "required": [],
    },
}


READ_ONLY_SUBCOMMANDS = {"doctor", "watch", "version", "check-update"}

# These names were accepted by the old M.I.C.A wrapper but have never been
# content-reading subcommands of the current Agent-Reach CLI.
LEGACY_PLATFORM_ROUTES = {
    "web": "Use M.I.C.A's crawl_url tool for a URL or web_search for discovery.",
    "search": "Use M.I.C.A's web_search tool. Agent-Reach may configure Exa as an upstream MCP route.",
    "github": "Use M.I.C.A's GitHub integration or the gh CLI selected by Agent-Reach.",
    "youtube": "Use M.I.C.A's youtube_video tool; Agent-Reach selects yt-dlp for broader extraction.",
    "bilibili": "Use a dedicated gated bili/yt-dlp adapter after Agent-Reach doctor reports it ready.",
    "rss": "Use a dedicated RSS adapter; Agent-Reach installs feedparser but has no rss subcommand.",
    "v2ex": "Use a dedicated V2EX adapter; Agent-Reach has no v2ex subcommand.",
    "twitter": "Configure the channel manually, then use a dedicated login-state-gated adapter.",
    "x": "Configure the channel manually, then use a dedicated login-state-gated adapter.",
    "reddit": "Configure the channel manually, then use a dedicated login-state-gated adapter.",
    "facebook": "Configure the channel manually, then use a dedicated login-state-gated adapter.",
    "instagram": "Configure the channel manually, then use a dedicated login-state-gated adapter.",
    "xiaohongshu": "Configure the channel manually, then use a dedicated login-state-gated adapter.",
    "linkedin": "Configure the channel manually, then use a dedicated login-state-gated adapter.",
}


def _agent_reach_executable() -> str | None:
    return shutil.which("agent-reach") or shutil.which("agent_reach")


def _bounded_timeout(raw: Any, default: int = 60) -> int:
    try:
        return max(1, min(600, int(raw or default)))
    except (TypeError, ValueError):
        return default


def _run_agent_reach(args: list[str], timeout: int) -> str:
    executable = _agent_reach_executable()
    if not executable:
        return (
            "Agent-Reach is not installed or not on PATH. "
            "Review the upstream installer first, then run `agent-reach doctor`. "
            "M.I.C.A will continue to work without this optional capability layer."
        )

    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    try:
        completed = subprocess.run(
            [executable, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
    except subprocess.TimeoutExpired:
        return f"Agent-Reach timed out after {timeout} seconds."
    except OSError as exc:
        return f"Agent-Reach could not be started: {exc}"

    output = (completed.stdout or "").strip()
    error = (completed.stderr or "").strip()
    if completed.returncode != 0:
        return f"Agent-Reach exited with code {completed.returncode}.\n{error or output}"
    return output or error or "Agent-Reach completed without output."


def _doctor(timeout: int, *, machine_readable: bool) -> str:
    args = ["doctor", "--json"] if machine_readable else ["doctor"]
    output = _run_agent_reach(args, timeout)
    if not machine_readable:
        return output
    try:
        report = json.loads(output)
    except (TypeError, json.JSONDecodeError):
        return output
    return json.dumps(
        {
            "integration": "agent-reach",
            "role": "capability installer and health checker",
            "platform_commands": False,
            "doctor": report,
        },
        ensure_ascii=False,
        indent=2,
    )


def _capabilities(timeout: int) -> str:
    executable = _agent_reach_executable()
    payload: dict[str, Any] = {
        "installed": bool(executable),
        "executable": executable or "",
        "cli_commands": [
            "setup",
            "install",
            "configure",
            "doctor",
            "uninstall",
            "skill",
            "format",
            "transcribe",
            "check-update",
            "watch",
            "version",
        ],
        "safe_mica_actions": [
            "doctor",
            "capabilities",
            "version",
            "watch",
            "check_update",
            "transcribe",
            "install_preview",
            "configure_preview",
        ],
        "platform_access": (
            "Agent-Reach selects and configures upstream tools. It does not expose "
            "web, github, youtube, rss, or social platforms as CLI subcommands."
        ),
        "legacy_route_guidance": LEGACY_PLATFORM_ROUTES,
    }
    if executable:
        raw = _run_agent_reach(["doctor", "--json"], timeout)
        try:
            payload["doctor"] = json.loads(raw)
        except json.JSONDecodeError:
            payload["doctor_output"] = raw
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _validate_compatibility_args(args: list[Any]) -> tuple[list[str] | None, str]:
    normalized = [str(arg).strip() for arg in args if str(arg).strip()]
    if not normalized:
        return None, "Provide a real Agent-Reach command or use action=doctor."
    if normalized[0].startswith(("-", "/")):
        return None, "The first Agent-Reach argument must be a command, not a flag."

    command = normalized[0].lower().replace("_", "-")
    if command in LEGACY_PLATFORM_ROUTES:
        return None, (
            f"`agent-reach {command}` is not an Agent-Reach CLI command. "
            f"{LEGACY_PLATFORM_ROUTES[command]}"
        )
    if command not in READ_ONLY_SUBCOMMANDS:
        return None, (
            f"Agent-Reach command '{command}' is not available through action=run. "
            "Use a named M.I.C.A action; setup, install, configure, skill, and uninstall "
            "change external state and must be performed explicitly outside this wrapper."
        )

    # Do not permit arbitrary flags through the compatibility path. Doctor's
    # machine-readable mode is the only useful safe flag and has a named action.
    if len(normalized) > 1:
        return None, "Extra arguments are not accepted through action=run; use a named action instead."
    return [command], ""


def _transcribe(params: dict[str, Any], timeout: int) -> str:
    source = str(params.get("source") or "").strip()
    if not source:
        return "action=transcribe requires a source URL or local audio/video path."
    if "\x00" in source:
        return "The transcription source contains an invalid null character."

    provider = str(params.get("provider") or "auto").strip().lower()
    if provider not in {"auto", "groq", "openai"}:
        return "Unknown transcription provider. Use auto, groq, or openai."

    args = ["transcribe", source, "--provider", provider]
    output = str(params.get("output") or "").strip()
    if output:
        if "\x00" in output:
            return "The transcription output path contains an invalid null character."
        args.extend(["--output", output])
    return _run_agent_reach(args, timeout)


def agent_reach(parameters: dict, player=None, speak=None, **kwargs) -> str:
    params = parameters or {}
    action = str(params.get("action", "doctor") or "doctor").strip().lower().replace("-", "_")
    timeout = _bounded_timeout(params.get("timeout"))

    if action in {"doctor", "status"}:
        return _doctor(timeout, machine_readable=bool(params.get("json", True)))
    if action == "capabilities":
        return _capabilities(timeout)
    if action == "version":
        return _run_agent_reach(["version"], timeout)
    if action == "watch":
        return _run_agent_reach(["watch"], timeout)
    if action == "check_update":
        return _run_agent_reach(["check-update"], timeout)
    if action == "transcribe":
        return _transcribe(params, timeout)

    if action == "install_preview":
        return (
            "Agent-Reach is optional and is not vendored into M.I.C.A. Review the upstream "
            "instructions, then preview changes with `agent-reach install --safe --dry-run`. "
            "The preview is not executed automatically because even installer setup may touch "
            "user-level tool directories."
        )
    if action == "configure_preview":
        return (
            "Configuration is intentionally manual because it may store API keys or browser "
            "cookies. Use `agent-reach configure --help` and approve the selected channel "
            "outside M.I.C.A before adding a dedicated gated adapter."
        )

    if action == "run":
        command, message = _validate_compatibility_args(params.get("args") or [])
        if command is None:
            return message
        return _run_agent_reach(command, timeout)

    return (
        "Unknown Agent-Reach action. Use doctor, status, capabilities, version, watch, "
        "check_update, transcribe, install_preview, or configure_preview."
    )
