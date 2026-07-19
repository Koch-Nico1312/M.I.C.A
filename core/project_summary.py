"""Structured, deterministic summaries for the active M.I.C.A project."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def build_project_summary(
    project_state: dict[str, Any],
    pipelines_payload: dict[str, Any],
    platform: dict[str, Any],
    action_history: dict[str, Any],
) -> dict[str, Any]:
    pipelines = [item for item in pipelines_payload.get("pipelines", []) if isinstance(item, dict)]
    artifacts = [item for item in platform.get("artifacts", []) if isinstance(item, dict)]
    runs = [item for item in platform.get("agent_runs", []) if isinstance(item, dict)]
    actions = [item for item in action_history.get("records", []) if isinstance(item, dict)]
    completed = [item for item in pipelines if item.get("status") == "completed"]
    active = [item for item in pipelines if item.get("status") in {"ready", "running", "paused"}]
    blocked = [
        item
        for item in pipelines
        if item.get("status") in {"blocked", "budget_exceeded"} or item.get("budget_exceeded")
    ]
    failed_runs = [item for item in runs if item.get("status") in {"failed", "blocked", "stopped"}]
    total_steps = sum(len(item.get("steps", [])) for item in pipelines)
    completed_steps = sum(
        len([step for step in item.get("steps", []) if step.get("status") == "completed"])
        for item in pipelines
    )
    progress = round((completed_steps / total_steps) * 100) if total_steps else 0

    blockers = [
        {"id": item.get("id"), "title": item.get("goal", "Blockierte Aufgabe"), "reason": item.get("status", "blocked")}
        for item in blocked[:5]
    ]
    blockers.extend(
        {"id": item.get("id"), "title": item.get("assignment", "Fehlgeschlagener Agentenlauf"), "reason": item.get("error") or item.get("status")}
        for item in failed_runs[: max(0, 5 - len(blockers))]
    )

    next_steps: list[str] = []
    if blockers:
        next_steps.append(f"Blocker prüfen: {blockers[0]['title']}")
    paused = next((item for item in active if item.get("status") == "paused"), None)
    running = next((item for item in active if item.get("status") in {"running", "ready"}), None)
    if paused:
        next_steps.append(f"Pausierten Lauf fortsetzen: {paused.get('goal')}")
    if running:
        pending = next((step for step in running.get("steps", []) if step.get("status") != "completed"), None)
        next_steps.append(str((pending or {}).get("title") or f"Aufgabe fortsetzen: {running.get('goal')}"))
    if not project_state.get("focus"):
        next_steps.append("Aktuellen Projektfokus festlegen")
    if not next_steps:
        next_steps.append("Nächsten priorisierten Auftrag festlegen")

    title = str((project_state.get("active_project") or {}).get("name") or "Aktives M.I.C.A-Projekt")
    focus = str(project_state.get("focus") or project_state.get("objective") or "Kein Fokus gesetzt")
    overview = (
        f"{len(completed)} von {len(pipelines)} Aufgaben abgeschlossen, "
        f"{len(active)} aktiv und {len(blocked)} blockiert. "
        f"Der Schrittfortschritt liegt bei {progress} %."
    )
    markdown_lines = [
        f"# {title}",
        "",
        f"**Fokus:** {focus}",
        "",
        overview,
        "",
        "## Blocker",
        *([f"- {item['title']} ({item['reason']})" for item in blockers] or ["- Keine bekannten Blocker"]),
        "",
        "## Nächste Schritte",
        *[f"- {item}" for item in next_steps[:3]],
    ]
    return {
        "generated_at": datetime.now().isoformat(),
        "title": title,
        "focus": focus,
        "overview": overview,
        "progress_percent": progress,
        "counts": {
            "pipelines": len(pipelines),
            "completed": len(completed),
            "active": len(active),
            "blocked": len(blocked),
            "artifacts": len(artifacts),
            "agent_runs": len(runs),
            "recent_actions": len(actions),
        },
        "blockers": blockers,
        "next_steps": next_steps[:3],
        "markdown": "\n".join(markdown_lines),
    }
