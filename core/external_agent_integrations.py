"""Optional adapters for third-party agent infrastructure.

The adapters in this module deliberately lazy-import vendor SDKs. M.I.C.A can
ship the integration points without making startup depend on heavyweight or
platform-specific packages.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from core.logger import get_logger
from core.paths import project_path

logger = get_logger(__name__)


class OptionalIntegrationError(RuntimeError):
    """Raised when an optional third-party integration is not configured."""


@dataclass
class IntegrationResult:
    ok: bool
    provider: str
    action: str
    result: Any = None
    error: str = ""
    artifacts: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "provider": self.provider,
            "action": self.action,
            "result": self.result,
            "error": self.error,
            "artifacts": self.artifacts or {},
        }


def _runs_dir(name: str) -> Path:
    path = project_path("data", name)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def write_run_artifact(kind: str, payload: dict[str, Any]) -> Path:
    path = _runs_dir(kind) / f"{_timestamp()}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def run_json_command(command: list[str], payload: dict[str, Any], timeout: int) -> IntegrationResult:
    """Run a helper command with JSON on stdin and parse JSON-ish output."""
    try:
        completed = subprocess.run(
            command,
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        return IntegrationResult(False, command[0], "run", error=f"Command not found: {exc}")
    except subprocess.TimeoutExpired:
        return IntegrationResult(False, command[0], "run", error=f"Timed out after {timeout}s")
    except Exception as exc:
        return IntegrationResult(False, command[0], "run", error=str(exc))

    raw = completed.stdout.strip() or completed.stderr.strip()
    parsed: Any = raw
    if raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = raw[-4000:]
    return IntegrationResult(
        completed.returncode == 0,
        command[0],
        "run",
        result=parsed,
        error="" if completed.returncode == 0 else completed.stderr[-2000:],
    )


def browser_use_unavailable_message() -> str:
    return (
        "Browser Use is not installed/configured. Install optional dependency "
        "`browser-use` and set BROWSER_USE_API_KEY or a supported LLM provider key."
    )


async def run_browser_use_agent(
    task: str,
    *,
    model: str = "",
    headless: bool = False,
    allowed_domains: list[str] | None = None,
    max_steps: int | None = None,
) -> IntegrationResult:
    """Run a Browser Use agent task and persist a compact trace."""
    try:
        from browser_use import Agent, BrowserProfile, ChatBrowserUse
    except Exception as exc:
        return IntegrationResult(False, "browser_use", "agent", error=f"{browser_use_unavailable_message()} ({exc})")

    if not task.strip():
        return IntegrationResult(False, "browser_use", "agent", error="No browser task provided.")

    try:
        llm = ChatBrowserUse(model=model or os.getenv("BROWSER_USE_MODEL", "openai/gpt-5.5"))
        profile = BrowserProfile(headless=headless, allowed_domains=allowed_domains or None)
        agent_kwargs: dict[str, Any] = {"task": task, "llm": llm, "browser_profile": profile}
        agent = Agent(**agent_kwargs)
        if max_steps is not None:
            history = await agent.run(max_steps=max_steps)
        else:
            history = await agent.run()
        final = history.final_result() if hasattr(history, "final_result") else str(history)
        artifact = write_run_artifact(
            "browser_agent_runs",
            {
                "task": task,
                "model": model or os.getenv("BROWSER_USE_MODEL", "openai/gpt-5.5"),
                "headless": headless,
                "allowed_domains": allowed_domains or [],
                "final_result": final,
                "history": str(history)[-8000:],
            },
        )
        return IntegrationResult(
            True,
            "browser_use",
            "agent",
            result=final,
            artifacts={"trace": str(artifact)},
        )
    except Exception as exc:
        logger.exception("Browser Use agent failed")
        return IntegrationResult(False, "browser_use", "agent", error=str(exc))


class CUAComputerBackend:
    """Adapter for CUA driver/CLI-style computer-use backends."""

    def __init__(self, command: str | None = None):
        raw = command or (os.getenv("MICA_CUA_DRIVER_CMD") or os.getenv("JARVIS_CUA_DRIVER_CMD", "")).strip()
        self.command = raw.split() if raw else []

    def available(self) -> bool:
        if self.command:
            return True
        try:
            __import__("cua")
            return True
        except Exception:
            return False

    def status(self) -> dict[str, Any]:
        return {
            "available": self.available(),
            "mode": "command" if self.command else "python_import" if self.available() else "unconfigured",
            "command": self.command,
        }

    def execute(self, action: str, parameters: dict[str, Any], timeout: int = 60) -> IntegrationResult:
        if self.command:
            payload = {"action": action, "parameters": parameters}
            result = run_json_command(self.command, payload, timeout)
            result.provider = "cua"
            result.action = action
            return result
        try:
            __import__("cua")
        except Exception as exc:
            return IntegrationResult(
                False,
                "cua",
                action,
                error=(
                    "CUA backend is not configured. Install CUA and set "
                    "MICA_CUA_DRIVER_CMD to a JSON stdin/stdout bridge command. "
                    f"Import error: {exc}"
                ),
            )
        return IntegrationResult(
            False,
            "cua",
            action,
            error="CUA Python package detected, but no M.I.C.A CUA bridge command is configured.",
        )


class Mem0MemoryBridge:
    """Two-tier memory bridge: local JSON remains source of truth, Mem0 is retrieval layer."""

    def __init__(self, enabled: bool | None = None, user_id: str | None = None):
        self.enabled = (
            enabled
            if enabled is not None
            else (os.getenv("MICA_MEM0_ENABLED") or os.getenv("JARVIS_MEM0_ENABLED", "")).lower() in {"1", "true", "yes"}
        )
        self.user_id = user_id or os.getenv("MICA_MEM0_USER_ID") or os.getenv("JARVIS_MEM0_USER_ID", "mica-user")
        self._client: Any = None

    def _get_client(self) -> Any:
        if not self.enabled:
            raise OptionalIntegrationError("Mem0 is disabled. Set MICA_MEM0_ENABLED=true.")
        if self._client is not None:
            return self._client
        try:
            from mem0 import MemoryClient

            self._client = MemoryClient(api_key=os.getenv("MEM0_API_KEY") or None)
        except Exception:
            try:
                from mem0 import Memory

                self._client = Memory.from_config({})
            except Exception as exc:
                raise OptionalIntegrationError(f"Mem0 SDK unavailable: {exc}") from exc
        return self._client

    def add(self, text: str, metadata: dict[str, Any] | None = None) -> IntegrationResult:
        try:
            client = self._get_client()
            if hasattr(client, "add"):
                try:
                    result = client.add(text, user_id=self.user_id, metadata=metadata or {})
                except TypeError:
                    result = client.add(
                        messages=[{"role": "user", "content": text}],
                        user_id=self.user_id,
                        metadata=metadata or {},
                    )
                return IntegrationResult(True, "mem0", "add", result=result)
            return IntegrationResult(False, "mem0", "add", error="Mem0 client has no add method.")
        except Exception as exc:
            return IntegrationResult(False, "mem0", "add", error=str(exc))

    def search(self, query: str, limit: int = 5) -> IntegrationResult:
        try:
            client = self._get_client()
            if hasattr(client, "search"):
                try:
                    result = client.search(query, user_id=self.user_id, limit=limit)
                except TypeError:
                    result = client.search(query=query, user_id=self.user_id, limit=limit)
                return IntegrationResult(True, "mem0", "search", result=result)
            return IntegrationResult(False, "mem0", "search", error="Mem0 client has no search method.")
        except Exception as exc:
            return IntegrationResult(False, "mem0", "search", error=str(exc))


_mem0_bridge: Mem0MemoryBridge | None = None


def get_mem0_bridge() -> Mem0MemoryBridge:
    global _mem0_bridge
    if _mem0_bridge is None:
        _mem0_bridge = Mem0MemoryBridge()
    return _mem0_bridge


class ComposioToolProvider:
    """Lazy Composio provider for external authenticated toolkits."""

    def __init__(self):
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from composio import Composio
        except Exception as exc:
            raise OptionalIntegrationError(f"Composio SDK unavailable: {exc}") from exc
        self._client = Composio(api_key=os.getenv("COMPOSIO_API_KEY") or None)
        return self._client

    def list_tools(self, user_id: str, toolkits: list[str]) -> IntegrationResult:
        try:
            client = self._get_client()
            tools = client.tools.get(user_id=user_id, toolkits=toolkits)
            compact = []
            for tool in tools:
                compact.append(
                    {
                        "name": getattr(tool, "name", None) or getattr(tool, "__name__", str(tool)),
                        "description": getattr(tool, "description", ""),
                    }
                )
            return IntegrationResult(True, "composio", "list_tools", result=compact)
        except Exception as exc:
            return IntegrationResult(False, "composio", "list_tools", error=str(exc))

    def execute_tool(self, user_id: str, slug: str, arguments: dict[str, Any]) -> IntegrationResult:
        try:
            client = self._get_client()
            if hasattr(client.tools, "execute"):
                result = client.tools.execute(slug=slug, user_id=user_id, arguments=arguments)
                return IntegrationResult(True, "composio", "execute_tool", result=result)
            return IntegrationResult(False, "composio", "execute_tool", error="Composio tools.execute is unavailable in this SDK version.")
        except Exception as exc:
            return IntegrationResult(False, "composio", "execute_tool", error=str(exc))


def openhands_status() -> IntegrationResult:
    commands = [
        [sys.executable, "-m", "pip", "show", "openhands"],
        ["agent-canvas", "--help"],
    ]
    checks = []
    for command in commands:
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
            checks.append(
                {
                    "command": command,
                    "ok": result.returncode == 0,
                    "output": (result.stdout or result.stderr)[-1200:],
                }
            )
        except Exception as exc:
            checks.append({"command": command, "ok": False, "output": str(exc)})
    return IntegrationResult(any(check["ok"] for check in checks), "openhands", "status", result=checks)
