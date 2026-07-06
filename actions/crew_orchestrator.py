"""Jarvis-native crew and flow orchestration."""

from __future__ import annotations

import json

from agent.multi_agent_orchestrator import get_orchestrator


TOOL_DECLARATION = {
    "name": "crew_orchestrator",
    "description": (
        "Creates and manages CrewAI-inspired Jarvis-native crews with roles, tasks, "
        "dependencies, checkpointing, and human-in-the-loop gates."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "create | run | status | approve"},
            "goal": {"type": "STRING", "description": "Crew goal for create"},
            "crew_id": {"type": "STRING", "description": "Crew id for run/status/approve"},
            "task_id": {"type": "STRING", "description": "Task id for approve"},
            "roles": {"type": "ARRAY", "items": {"type": "OBJECT"}, "description": "Optional role definitions"},
            "tasks": {"type": "ARRAY", "items": {"type": "OBJECT"}, "description": "Optional task definitions"},
            "process": {"type": "STRING", "description": "sequential | hierarchical"},
            "note": {"type": "STRING", "description": "Approval/checkpoint note"},
            "stop_before_human_input": {
                "type": "BOOLEAN",
                "description": "Pause before human-gated tasks during run (default true)",
            },
        },
        "required": ["action"],
    },
    "category": "agents",
    "enabled": True,
}


def crew_orchestrator(parameters: dict, response=None, player=None, session_memory=None, speak=None) -> str:
    params = parameters or {}
    action = str(params.get("action", "status")).lower().strip()
    orchestrator = get_orchestrator(speak=speak)

    try:
        if action == "create":
            flow = orchestrator.create_crew(
                str(params.get("goal", "")),
                roles=params.get("roles"),
                tasks=params.get("tasks"),
                process=str(params.get("process", "sequential")),
            )
            payload = orchestrator.get_crew(flow.id)
        elif action == "run":
            flow = orchestrator.run_crew(
                str(params.get("crew_id", "")),
                stop_before_human_input=bool(params.get("stop_before_human_input", True)),
            )
            payload = orchestrator.get_crew(flow.id)
        elif action == "approve":
            flow = orchestrator.approve_crew_task(
                str(params.get("crew_id", "")),
                str(params.get("task_id", "")),
                str(params.get("note", "")),
            )
            payload = orchestrator.get_crew(flow.id)
        elif action == "status":
            crew_id = str(params.get("crew_id", ""))
            payload = orchestrator.get_crew(crew_id) if crew_id else {
                "crews": list(orchestrator.crews.keys()),
                "count": len(orchestrator.crews),
            }
        else:
            payload = {"error": f"Unknown crew_orchestrator action: {action}"}
    except Exception as exc:
        payload = {"error": str(exc), "action": action}

    if player:
        player.write_log(f"[crew] {action}")
    return json.dumps(payload, indent=2, ensure_ascii=False)

