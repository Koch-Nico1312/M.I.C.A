import json

from actions.crew_orchestrator import crew_orchestrator
from agent.multi_agent_orchestrator import AgentResult, AgentType, MultiAgentOrchestrator


def test_create_crew_builds_roles_tasks_and_checkpoint():
    orchestrator = MultiAgentOrchestrator()

    flow = orchestrator.create_crew("Build a research brief")
    payload = orchestrator.get_crew(flow.id)

    assert payload["status"] == "ready"
    assert [role["name"] for role in payload["roles"]] == ["Planner", "Specialist", "Reviewer"]
    assert payload["tasks"][2]["requires_human_input"] is True
    assert payload["checkpoints"][0]["status"] == "created"


def test_run_crew_stops_at_human_gate(monkeypatch):
    orchestrator = MultiAgentOrchestrator()
    flow = orchestrator.create_crew("Implement a tiny feature")

    def fake_execute(task):
        return AgentResult(task.task_id, AgentType.GENERAL, True, result=f"done {task.task_id}")

    monkeypatch.setattr(orchestrator, "execute_task_sync", fake_execute)

    updated = orchestrator.run_crew(flow.id)
    payload = orchestrator.get_crew(updated.id)

    assert payload["status"] == "waiting_for_human"
    assert payload["tasks"][0]["status"] == "completed"
    assert payload["tasks"][1]["status"] == "completed"
    assert payload["tasks"][2]["status"] == "waiting_for_human"


def test_crew_action_can_create_status_and_approve(monkeypatch):
    import actions.crew_orchestrator as crew_action_module

    orchestrator = MultiAgentOrchestrator()
    monkeypatch.setattr(crew_action_module, "get_orchestrator", lambda speak=None: orchestrator)

    created = json.loads(crew_orchestrator({"action": "create", "goal": "Plan launch"}))
    status = json.loads(crew_orchestrator({"action": "status", "crew_id": created["id"]}))

    assert status["id"] == created["id"]
    assert status["status"] == "ready"
