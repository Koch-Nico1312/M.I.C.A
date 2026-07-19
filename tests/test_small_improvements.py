from core.project_summary import build_project_summary
from core.system_status import SystemStatusManager


def test_system_status_collects_all_requested_services(monkeypatch):
    import core.system_status as status_module

    def available(check_id, label):
        return lambda: status_module._result(check_id, label, "available", "Bereit")

    for check_id, function_name, label in (
        ("gemini", "_check_gemini", "Gemini"),
        ("ollama", "_check_ollama", "Ollama"),
        ("microphone", "_check_microphone", "Mikrofon"),
        ("browser", "_check_browser", "Browser"),
        ("mcp", "_check_mcp", "MCP"),
        ("database", "_check_database", "Datenbank"),
    ):
        monkeypatch.setattr(status_module, function_name, available(check_id, label))

    payload = SystemStatusManager(cache_seconds=60).snapshot(force=True)

    assert payload["status"] == "available"
    assert payload["counts"] == {"available": 6, "degraded": 0, "unavailable": 0}
    assert {item["id"] for item in payload["services"]} == {
        "gemini",
        "ollama",
        "microphone",
        "browser",
        "mcp",
        "database",
    }


def test_project_summary_reports_progress_blockers_and_next_steps():
    payload = build_project_summary(
        {"focus": "Release vorbereiten", "active_project": {"name": "M.I.C.A"}},
        {
            "pipelines": [
                {
                    "id": "done",
                    "goal": "UI bauen",
                    "status": "completed",
                    "steps": [{"status": "completed"}, {"status": "completed"}],
                },
                {
                    "id": "blocked",
                    "goal": "Release prüfen",
                    "status": "blocked",
                    "steps": [{"status": "completed"}, {"status": "blocked"}],
                },
            ]
        },
        {"artifacts": [{"id": "artifact-1"}], "agent_runs": []},
        {"records": [{"id": "action-1"}]},
    )

    assert payload["title"] == "M.I.C.A"
    assert payload["progress_percent"] == 75
    assert payload["counts"]["blocked"] == 1
    assert payload["blockers"][0]["title"] == "Release prüfen"
    assert payload["next_steps"][0].startswith("Blocker prüfen")
    assert "## Nächste Schritte" in payload["markdown"]


def test_customized_duplicate_keeps_origin_metadata(tmp_path):
    from agent.task_pipeline import TaskPipelineManager

    manager = TaskPipelineManager(path=tmp_path / "pipelines.json")
    source = manager.create_pipeline("Original", steps=["Plan", "Umsetzen"])
    duplicate = manager.create_pipeline(
        "Angepasste Kopie",
        steps=["Neuer Plan", "Umsetzen", "Prüfen"],
        origin_id=source.id,
        origin_relation="duplicate",
    )

    assert duplicate.goal == "Angepasste Kopie"
    assert [step.title for step in duplicate.steps] == ["Neuer Plan", "Umsetzen", "Prüfen"]
    assert duplicate.origin_id == source.id
    assert duplicate.origin_relation == "duplicate"
