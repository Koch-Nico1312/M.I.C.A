from core.project_state import ProjectStateManager


def test_project_state_persists_solo_resume_context(tmp_path):
    path = tmp_path / "project_state.json"
    manager = ProjectStateManager(path)
    manager.update(
        {
            "active_project_id": "proj-mica",
            "objective": "Agent-Hub fertigstellen",
            "focus": "Supervisor-Zustand",
            "last_tab": "tasks",
            "pipeline_ids": ["pipe-1", "pipe-1", "pipe-2"],
            "agent_ids": ["planner", "review"],
        }
    )
    manager.checkpoint("Aufgabenansicht umgesetzt")

    restored = ProjectStateManager(path).snapshot()
    assert restored["active_project_id"] == "proj-mica"
    assert restored["last_tab"] == "tasks"
    assert restored["pipeline_ids"] == ["pipe-1", "pipe-2"]
    assert restored["checkpoint"] == "Aufgabenansicht umgesetzt"


def test_project_state_rejects_unknown_tab(tmp_path):
    manager = ProjectStateManager(tmp_path / "state.json")
    assert manager.update({"last_tab": "enterprise-admin"})["last_tab"] == "hub"


def test_project_state_persists_personal_commands_and_views(tmp_path):
    path = tmp_path / "state.json"
    manager = ProjectStateManager(path)
    manager.update(
        {
            "favorite_commands": ["agent-research", "open-tasks"],
            "recent_commands": [f"command-{index}" for index in range(25)],
            "saved_views": {"daily": {"tab": "activity", "query": "error"}},
            "dashboard_widgets": ["runs", "supervisor", "runs", "unknown"],
            "run_budget": {"max_steps": 4, "max_minutes": 30, "max_agent_calls": 9, "stop_on_limit": True},
        }
    )

    restored = ProjectStateManager(path).snapshot()
    assert restored["favorite_commands"] == ["agent-research", "open-tasks"]
    assert len(restored["recent_commands"]) == 20
    assert restored["recent_commands"][0] == "command-5"
    assert restored["saved_views"]["daily"]["tab"] == "activity"
    assert restored["dashboard_widgets"] == ["runs", "supervisor"]
    assert restored["run_budget"]["max_steps"] == 4


def test_personal_state_v2_persists_telos_current_and_ideal_state(tmp_path):
    path = tmp_path / "state.json"
    manager = ProjectStateManager(path)

    manager.update(
        {
            "telos": {
                "mission": "Build a trustworthy personal AI system",
                "goals": ["Ship M.I.C.A", "Ship M.I.C.A"],
                "strategies": ["Local first"],
            },
            "current_state": {
                "summary": "Useful but fragmented",
                "constraints": ["One operator"],
            },
            "ideal_state": {
                "summary": "A reliable personal operating system",
                "metrics": ["All critical claims verified"],
            },
        }
    )

    restored = ProjectStateManager(path).snapshot()
    assert restored["version"] == 2
    assert restored["telos"]["mission"] == "Build a trustworthy personal AI system"
    assert restored["telos"]["goals"] == ["Ship M.I.C.A"]
    assert restored["current_state"]["constraints"] == ["One operator"]
    assert restored["ideal_state"]["metrics"] == ["All critical claims verified"]


def test_personal_state_v2_tracks_criteria_decisions_and_evidence(tmp_path):
    manager = ProjectStateManager(tmp_path / "state.json")

    state = manager.set_acceptance_criterion(
        "Agent-Reach diagnostics match the installed CLI",
        criterion_id="isc-agent-reach",
        status="passed",
    )
    assert state["completion"]["ready_to_close"] is False

    manager.record_decision(
        "Keep external integrations disabled by default",
        rationale="Installation and credentials require explicit consent",
    )
    state = manager.record_evidence(
        "Agent-Reach diagnostics match the installed CLI",
        source="pytest tests/test_agent_reach.py: 39 passed",
        result="passed",
        criterion_id="isc-agent-reach",
    )

    assert state["acceptance_criteria"][0]["evidence_ids"] == [state["evidence"][0]["id"]]
    assert state["decisions"][0]["status"] == "active"
    assert state["completion"] == {
        "criteria_total": 1,
        "counts": {"blocked": 0, "failed": 0, "passed": 1, "pending": 0, "waived": 0},
        "evidence_total": 1,
        "decision_total": 1,
        "ready_to_close": True,
    }


def test_project_state_migrates_version_one_without_losing_resume_context(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(
        '{"version": 1, "objective": "Finish M.I.C.A", "focus": "Project state"}',
        encoding="utf-8",
    )

    state = ProjectStateManager(path).snapshot()

    assert state["version"] == 2
    assert state["objective"] == "Finish M.I.C.A"
    assert state["focus"] == "Project state"
    assert state["telos"]["mission"] == ""
    assert state["acceptance_criteria"] == []


def test_supervisor_inbox_prioritizes_approvals_and_paused_work(monkeypatch):
    import core.project_state as state_module
    import ui_bridge

    manager = ProjectStateManager()
    manager._state.focus = "Ship the Agent Hub"
    manager._state.pipeline_ids = ["pipe-paused"]
    monkeypatch.setattr(state_module, "get_project_state_manager", lambda: manager)

    class FakeHub:
        def snapshot(self):
            return {"agents": [], "artifacts": [], "agent_runs": []}

    monkeypatch.setattr(ui_bridge, "get_platform_hub", lambda: FakeHub())
    ui = object.__new__(ui_bridge.MicaUI)
    ui._project_workspaces_payload = lambda: {"active": {"id": "proj-solo", "name": "Solo"}}
    ui._task_pipelines_payload = lambda: {
        "pipelines": [{"id": "pipe-paused", "goal": "Continue work", "status": "paused", "requires_approval": False}],
        "active": [],
    }
    ui._approvals_payload = lambda: {"pending": [{"tool_name": "system", "action": "change"}]}

    payload = ui._project_state_payload()

    assert payload["inbox"][0]["id"] == "pending-approvals"
    assert payload["inbox"][0]["priority"] == "urgent"
    resume = next(item for item in payload["inbox"] if item["id"] == "resume-pipe-paused")
    assert resume["action"]["kind"] == "resume_pipeline"
    assert payload["resume_available"] is True
