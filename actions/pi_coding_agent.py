"""Pi coding-agent bridge with strict workspace confinement."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paths import project_path


DEFAULT_WORKSPACE_ROOT = "/workspace/projects"
DEFAULT_TIMEOUT_SECONDS = 900
MAX_OUTPUT_CHARS = 12000


def _env_enabled() -> bool:
    return str(os.getenv("MICA_PI_ENABLED", "false")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _workspace_root() -> Path:
    raw = os.getenv("MICA_PI_WORKSPACE_ROOT", DEFAULT_WORKSPACE_ROOT).strip()
    return Path(raw).expanduser().resolve()


def _reject_host_path(raw_path: str) -> None:
    if ":" in raw_path or "\\" in raw_path:
        raise ValueError(
            "Windows/host paths are not allowed. Pass a path relative to MICA_PI_WORKSPACE_ROOT."
        )


def _resolve_project_path(project_path_param: str) -> Path:
    root = _workspace_root()
    root.mkdir(parents=True, exist_ok=True)

    raw_path = (project_path_param or ".").strip() or "."
    _reject_host_path(raw_path)

    requested = Path(raw_path).expanduser()
    target = requested if requested.is_absolute() else root / requested
    resolved = target.resolve(strict=False)

    if not resolved.is_relative_to(root):
        raise ValueError(f"Project path escapes workspace root: {raw_path}")

    resolved.mkdir(parents=True, exist_ok=True)
    real_target = resolved.resolve()
    if not real_target.is_relative_to(root):
        raise ValueError(f"Resolved project path escapes workspace root: {raw_path}")

    return real_target


def _run(args: list[str], cwd: Path, timeout: int) -> dict[str, Any]:
    try:
        result = subprocess.run(
            args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env={**os.environ, "NO_COLOR": "1", "TERM": os.getenv("TERM", "xterm-256color")},
        )
        return {
            "command": args,
            "returncode": result.returncode,
            "stdout": result.stdout[-MAX_OUTPUT_CHARS:],
            "stderr": result.stderr[-MAX_OUTPUT_CHARS:],
            "ok": result.returncode == 0,
        }
    except FileNotFoundError as exc:
        return {
            "command": args,
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "ok": False,
            "error": f"Command not found: {exc.filename}",
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        return {
            "command": args,
            "returncode": None,
            "stdout": stdout[-MAX_OUTPUT_CHARS:],
            "stderr": stderr[-MAX_OUTPUT_CHARS:],
            "ok": False,
            "error": f"Timed out after {timeout}s",
        }


def _git_diff_stat(project_dir: Path) -> str:
    result = _run(["git", "diff", "--stat"], project_dir, timeout=30)
    if result.get("ok"):
        return str(result.get("stdout") or "").strip()
    return ""


def _write_run_log(payload: dict[str, Any]) -> Path:
    runs_dir = project_path("data", "pi_runs")
    runs_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = runs_dir / f"{stamp}_pi_coding_agent.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def _build_pi_prompt(task: str, allow_tests: bool) -> str:
    test_instruction = (
        "Run focused tests or checks if useful, but do not commit, push, or merge."
        if allow_tests
        else "Do not run tests or long-running checks unless explicitly required by the task."
    )
    return (
        "You are being called by M.I.C.A inside a sandboxed container. "
        "Work only in the current project directory. "
        "Do not access parent directories. Do not commit, push, merge, or use remotes. "
        f"{test_instruction}\n\nTask:\n{task.strip()}"
    )


def pi_coding_agent(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None,
    speak=None,
) -> str:
    params = parameters or {}
    task = str(params.get("task", "")).strip()
    if not task:
        return "Please provide a coding task for Pi."

    if not _env_enabled():
        return "Pi coding agent is disabled. Set MICA_PI_ENABLED=true in the container environment."

    timeout_default = _bounded_int(
        os.getenv("MICA_PI_TIMEOUT_SECONDS"),
        DEFAULT_TIMEOUT_SECONDS,
        30,
        7200,
    )
    timeout = _bounded_int(params.get("timeout"), timeout_default, 30, 7200)
    project_dir = _resolve_project_path(str(params.get("project_path", ".") or "."))
    allow_tests = bool(params.get("allow_tests", True))
    mode = str(params.get("mode", "json") or "json").strip().lower()
    if mode not in {"json", "print"}:
        mode = "json"

    pi_prompt = _build_pi_prompt(task, allow_tests)
    command = ["pi", "--no-session"]
    default_model = str(os.getenv("MICA_PI_DEFAULT_MODEL", "") or "").strip()
    if default_model:
        command.extend(["--model", default_model])
    if mode == "json":
        command.extend(["--mode", "json"])
    command.extend(["-p", pi_prompt])

    started = datetime.now()
    run_result = _run(command, project_dir, timeout=timeout)
    diff_stat = _git_diff_stat(project_dir)
    payload = {
        "tool": "pi_coding_agent",
        "project_dir": str(project_dir),
        "workspace_root": str(_workspace_root()),
        "task": task,
        "mode": mode,
        "allow_tests": allow_tests,
        "started_at": started.isoformat(),
        "finished_at": datetime.now().isoformat(),
        "pi": run_result,
        "diff_stat": diff_stat,
    }
    log_path = _write_run_log(payload)

    status = "succeeded" if run_result.get("ok") else "failed"
    output = str(run_result.get("stdout") or run_result.get("stderr") or run_result.get("error") or "")
    preview = output[-3000:].strip()
    response_payload = {
        "status": status,
        "project_dir": str(project_dir),
        "returncode": run_result.get("returncode"),
        "diff_stat": diff_stat,
        "log_path": str(log_path),
        "output_preview": preview,
    }
    return json.dumps(response_payload, indent=2, ensure_ascii=False)
