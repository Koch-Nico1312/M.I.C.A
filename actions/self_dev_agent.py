"""Controlled self-development workflow for the Jarvis repository."""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paths import project_path, resolve_project_root


ROOT = resolve_project_root()
RUNS_DIR = project_path("data", "self_dev_runs")
DEFAULT_TEST_COMMAND = ["pytest", "-q"]


def _run(args: list[str], *, timeout: int = 120, input_text: str | None = None) -> dict[str, Any]:
    started = datetime.now()
    try:
        result = subprocess.run(
            args,
            cwd=str(ROOT),
            input=input_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return {
            "command": args,
            "returncode": result.returncode,
            "stdout": result.stdout[-6000:],
            "stderr": result.stderr[-6000:],
            "started_at": started.isoformat(),
            "finished_at": datetime.now().isoformat(),
            "ok": result.returncode == 0,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": args,
            "returncode": None,
            "stdout": (exc.stdout or "")[-6000:] if isinstance(exc.stdout, str) else "",
            "stderr": (exc.stderr or "")[-6000:] if isinstance(exc.stderr, str) else "",
            "started_at": started.isoformat(),
            "finished_at": datetime.now().isoformat(),
            "ok": False,
            "error": f"Timed out after {timeout}s",
        }
    except Exception as exc:
        return {
            "command": args,
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "started_at": started.isoformat(),
            "finished_at": datetime.now().isoformat(),
            "ok": False,
            "error": str(exc),
        }


def _git(args: list[str], *, timeout: int = 60, input_text: str | None = None) -> dict[str, Any]:
    return _run(["git", *args], timeout=timeout, input_text=input_text)


def _current_branch() -> str:
    result = _git(["branch", "--show-current"], timeout=10)
    return str(result.get("stdout", "")).strip()


def _status() -> dict[str, Any]:
    status = _git(["status", "--short"], timeout=10)
    branch = _current_branch()
    diff = _git(["diff", "--stat"], timeout=10)
    return {
        "branch": branch,
        "dirty_files": [line for line in status.get("stdout", "").splitlines() if line.strip()],
        "diff_stat": diff.get("stdout", "").strip(),
        "ready_for_cycle": bool(branch.startswith("codex/")),
    }


def _safe_branch_name(goal: str) -> str:
    raw = re.sub(r"[^a-zA-Z0-9]+", "-", goal.lower()).strip("-")[:48]
    return f"codex/self-dev-{raw or datetime.now().strftime('%Y%m%d-%H%M%S')}"


def _ensure_branch(goal: str, requested: str = "") -> dict[str, Any]:
    current = _current_branch()
    if current.startswith("codex/"):
        return {"status": "already_on_codex_branch", "branch": current}
    branch = requested.strip() or _safe_branch_name(goal)
    created = _git(["switch", "-c", branch], timeout=30)
    return {"status": "created" if created["ok"] else "failed", "branch": branch, "result": created}


def _split_command(command: str) -> list[str]:
    if not command.strip():
        return list(DEFAULT_TEST_COMMAND)
    return command.split()


def _run_tests(command: str = "", timeout: int = 180) -> dict[str, Any]:
    return _run(_split_command(command), timeout=timeout)


def _diff() -> dict[str, Any]:
    stat = _git(["diff", "--stat"], timeout=20)
    patch = _git(["diff"], timeout=20)
    return {
        "stat": stat.get("stdout", "").strip(),
        "patch": patch.get("stdout", "")[-12000:],
        "ok": stat.get("ok", False) and patch.get("ok", False),
    }


def _write_report(kind: str, payload: dict[str, Any]) -> Path:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = RUNS_DIR / f"{stamp}_{kind}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _plan(goal: str, context: str = "", use_model: bool = False) -> dict[str, Any]:
    checklist = [
        "Create or switch to a codex/self-dev branch.",
        "Inspect current git status and avoid overwriting unrelated user changes.",
        "Make the smallest code change that addresses the goal.",
        "Run focused tests first, then broader tests if the focused pass is clean.",
        "Review git diff for security, filesystem, network, and regression risk.",
        "Produce a merge report and wait for human merge approval.",
    ]
    model_plan = ""
    if use_model:
        try:
            from core.model_runner import CodeVerificationLoop

            model_plan = CodeVerificationLoop().plan(goal, context)
        except Exception as exc:
            model_plan = f"Model planning unavailable: {exc}"
    return {"goal": goal, "checklist": checklist, "model_plan": model_plan}


def _review(context: str = "", use_model: bool = False) -> dict[str, Any]:
    diff = _diff()
    notes = [
        "No automatic merge is performed.",
        "Review changed files and test output before merging.",
    ]
    model_review = ""
    if use_model and diff.get("patch"):
        try:
            from core.model_runner import CodeVerificationLoop

            model_review = CodeVerificationLoop().review(str(diff["patch"]), context=context)
        except Exception as exc:
            model_review = f"Model review unavailable: {exc}"
    return {"diff": diff, "notes": notes, "model_review": model_review}


def _apply_patch(patch: str, test_command: str, timeout: int) -> dict[str, Any]:
    if not patch.strip():
        return {"ok": False, "error": "No patch provided."}
    check = _git(["apply", "--check", "-"], timeout=30, input_text=patch)
    if not check["ok"]:
        return {"ok": False, "stage": "check", "result": check}
    applied = _git(["apply", "-"], timeout=30, input_text=patch)
    if not applied["ok"]:
        return {"ok": False, "stage": "apply", "result": applied}
    tests = _run_tests(test_command, timeout=timeout)
    review = _review(use_model=False)
    payload = {"ok": tests["ok"], "applied": applied, "tests": tests, "review": review}
    report = _write_report("patch", payload)
    payload["report_path"] = str(report)
    return payload


def _cycle(goal: str, test_command: str, timeout: int, create_branch: bool, branch: str) -> dict[str, Any]:
    before = _status()
    branch_result = _ensure_branch(goal, branch) if create_branch else {"status": "skipped"}
    tests = _run_tests(test_command, timeout=timeout)
    review = _review(use_model=False)
    payload = {
        "goal": goal,
        "before": before,
        "branch": branch_result,
        "tests": tests,
        "review": review,
        "merge_state": "ready" if tests["ok"] else "blocked",
    }
    report = _write_report("cycle", payload)
    payload["report_path"] = str(report)
    return payload


def self_dev_agent(parameters: dict, response=None, player=None, session_memory=None, speak=None) -> str:
    params = parameters or {}
    action = str(params.get("action", "status")).lower().strip()
    goal = str(params.get("goal", "")).strip()
    test_command = str(params.get("test_command", "")).strip()
    timeout = int(params.get("timeout", 180) or 180)
    use_model = bool(params.get("use_model", False))

    if action == "status":
        result = _status()
    elif action == "branch":
        result = _ensure_branch(goal or "self development", str(params.get("branch", "")))
    elif action == "plan":
        result = _plan(goal or "Improve Jarvis", str(params.get("context", "")), use_model)
    elif action == "test":
        result = _run_tests(test_command, timeout=timeout)
    elif action == "review":
        result = _review(str(params.get("context", "")), use_model)
    elif action == "patch":
        result = _apply_patch(str(params.get("patch", "")), test_command, timeout)
    elif action == "cycle":
        result = _cycle(
            goal or "Self-development cycle",
            test_command,
            timeout,
            bool(params.get("create_branch", True)),
            str(params.get("branch", "")),
        )
    else:
        result = {"error": f"Unknown self_dev_agent action: {action}"}

    try:
        from core.action_history import ActionStatus, get_action_history

        status = ActionStatus.SUCCESS if "error" not in result else ActionStatus.FAILED
        get_action_history().record_action(
            "self_dev_agent",
            action,
            {k: v for k, v in params.items() if k != "patch"},
            result=json.dumps(result, ensure_ascii=False)[:2000],
            status=status,
        )
    except Exception:
        pass
    if player:
        player.write_log(f"[self-dev] {action}: {result.get('merge_state') or result.get('status') or 'done'}")
    return json.dumps(result, indent=2, ensure_ascii=False)
