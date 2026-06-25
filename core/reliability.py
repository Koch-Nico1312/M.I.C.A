"""Runtime readiness snapshot for daily-driver use."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paths import project_path, resolve_project_root


@dataclass(frozen=True)
class ReliabilityCheck:
    name: str
    status: str
    message: str
    detail: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "detail": self.detail or {},
        }


def _status(ok: bool, degraded: bool = False) -> str:
    if ok:
        return "ok"
    return "degraded" if degraded else "blocked"


def _git_snapshot(root: Path) -> ReliabilityCheck:
    if not shutil.which("git"):
        return ReliabilityCheck("git", "degraded", "Git is not available on PATH.")
    try:
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=5,
        )
        status = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=5,
        )
        dirty_lines = [line for line in status.stdout.splitlines() if line.strip()]
        return ReliabilityCheck(
            "git",
            "ok",
            f"Branch {branch.stdout.strip() or 'unknown'} with {len(dirty_lines)} changed file(s).",
            {"branch": branch.stdout.strip(), "dirty_count": len(dirty_lines)},
        )
    except Exception as exc:
        return ReliabilityCheck("git", "degraded", f"Git status failed: {exc}")


def _ollama_snapshot(config: Any) -> ReliabilityCheck:
    enabled = bool(config.get("ollama.enabled", False))
    model = str(config.get("ollama.model", "llama3.1"))
    if not enabled:
        return ReliabilityCheck(
            "offline_model",
            "degraded",
            "Ollama is configured but disabled; offline coding fallback is not active.",
            {"enabled": False, "model": model},
        )
    try:
        from core.llm_fallback import get_ollama_fallback

        available = get_ollama_fallback().is_available()
        return ReliabilityCheck(
            "offline_model",
            _status(available, degraded=True),
            f"Ollama model {model} is {'available' if available else 'not reachable'}.",
            {"enabled": True, "model": model, "available": available},
        )
    except Exception as exc:
        return ReliabilityCheck(
            "offline_model",
            "degraded",
            f"Ollama check failed: {exc}",
            {"enabled": True, "model": model},
        )


def _path_check(name: str, path: Path, *, required: bool = False) -> ReliabilityCheck:
    exists = path.exists()
    return ReliabilityCheck(
        name,
        _status(exists, degraded=not required),
        f"{path} {'exists' if exists else 'is missing'}.",
        {"path": str(path), "exists": exists},
    )


def _feature_checks(config: Any) -> list[ReliabilityCheck]:
    features = {
        "rag": bool(config.get("rag.enabled", False)),
        "passive_vision": bool(config.get("passive_vision.enabled", False)),
        "calendar": bool(config.get("calendar.enabled", False)),
        "action_history": bool(config.get("security.action_history_enabled", True)),
        "workflow": bool(config.get("workflow.enabled", True)),
    }
    return [
        ReliabilityCheck(
            f"feature:{name}",
            "ok" if enabled else "degraded",
            f"{name} is {'enabled' if enabled else 'disabled'}.",
            {"enabled": enabled},
        )
        for name, enabled in features.items()
    ]


def build_reliability_report() -> dict[str, Any]:
    """Return a compact readiness report for UI and diagnostics."""
    from config.config_loader import get_config

    config = get_config()
    root = resolve_project_root()
    checks: list[ReliabilityCheck] = [
        _git_snapshot(root),
        _ollama_snapshot(config),
        _path_check("memory", project_path("memory", "long_term.json")),
        _path_check("action_history", project_path("data", "action_history.json")),
        _path_check("vector_index", project_path("data", "vector_db")),
        _path_check("uploads", project_path("data", "uploads")),
    ]
    checks.extend(_feature_checks(config))

    counts = {"ok": 0, "degraded": 0, "blocked": 0}
    for check in checks:
        counts[check.status] = counts.get(check.status, 0) + 1

    if counts["blocked"]:
        status = "blocked"
    elif counts["degraded"]:
        status = "degraded"
    else:
        status = "ok"

    return {
        "status": status,
        "generated_at": datetime.now().isoformat(),
        "counts": counts,
        "checks": [check.to_dict() for check in checks],
        "recommendations": _recommendations(checks),
    }


def _recommendations(checks: list[ReliabilityCheck]) -> list[str]:
    recommendations: list[str] = []
    by_name = {check.name: check for check in checks}
    if by_name.get("offline_model") and by_name["offline_model"].status != "ok":
        recommendations.append("Enable and verify Ollama before relying on offline self-development.")
    if by_name.get("git") and by_name["git"].status != "ok":
        recommendations.append("Fix Git availability before running self-development cycles.")
    if by_name.get("vector_index") and not by_name["vector_index"].detail.get("exists"):
        recommendations.append("Index local documents so offline answers can cite local context.")
    return recommendations[:5]
