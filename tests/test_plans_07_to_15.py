import json

from core.automation_scheduler import AutomationScheduler
from core.document_ingestion import build_ingestion_record, chunk_text
from core.knowledge_graph import build_knowledge_graph
from core.learning_feedback import LearningFeedbackStore
from core.personal_os import PersonalOSIntegration
from core.plugin_system import PluginManager
from core.privacy_modes import PrivacyModeManager
from core.project_workspace import ProjectWorkspaceManager
from memory.smart_note_composer import SmartNoteComposer, safe_note_filename


def test_knowledge_graph_builds_nodes_edges_and_filters():
    graph = build_knowledge_graph(
        memory={"notes": {"alpha": {"value": "Alpha note", "tags": ["x"]}}},
        documents=[{"name": "doc.md", "type": "MD", "indexed": True, "path": "doc.md"}],
    )

    assert graph["counts"]["nodes"] >= 3
    assert graph["counts"]["edges"] >= 1
    assert "memory" in graph["filters"]["sources"]


def test_document_ingestion_chunks_and_detects_duplicate(tmp_path):
    path = tmp_path / "note.md"
    path.write_text("hello world " * 400, encoding="utf-8")

    first, chunks = build_ingestion_record(path)
    second, _ = build_ingestion_record(path, existing_checksums={first["checksum"]})

    assert first["chunks"] == len(chunks)
    assert chunks
    assert second["status"] == "duplicate"
    assert chunk_text("abc", chunk_size=2)


def test_smart_note_composer_drafts_without_writing(tmp_path):
    composer = SmartNoteComposer(path=tmp_path / "drafts.json")

    draft = composer.create_draft("A/B: Note", "Summary", sources=["source"], tags=["tag"], links=["Other"])

    assert safe_note_filename("A/B: Note") == "AB Note"
    assert draft["status"] == "draft"
    assert "## Sources" in draft["markdown"]


def test_automation_scheduler_allows_only_safe_actions(tmp_path):
    scheduler = AutomationScheduler(path=tmp_path / "automations.json")

    item = scheduler.create("Briefing", "daily_briefing", "08:00")

    assert item["action"] == "daily_briefing"
    try:
        scheduler.create("Bad", "delete_everything", "*")
    except ValueError:
        pass
    else:
        raise AssertionError("unsafe automation action accepted")


def test_plugin_manifest_status(tmp_path):
    plugin_dir = tmp_path / "example"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text(
        json.dumps(
            {
                "id": "example",
                "name": "Example",
                "entrypoint": "plugin.py",
                "permissions": ["text:read"],
                "enabled": True,
            }
        ),
        encoding="utf-8",
    )
    (plugin_dir / "plugin.py").write_text(
        "TOOL_DECLARATION={'name':'example','description':'e','parameters':{},'enabled':True}\n"
        "def example(parameters, **kwargs): return 'ok'\n",
        encoding="utf-8",
    )

    manager = PluginManager(plugins_dir=tmp_path)
    manager.load_all_plugins()
    status = manager.status()

    assert status["manifests"][0]["id"] == "example"
    assert status["tools"][0]["name"] == "example"


def test_privacy_modes_block_external_for_secret(tmp_path):
    manager = PrivacyModeManager(path=tmp_path / "privacy.json")

    manager.set_mode("cloud_allowed")
    assert manager.allows_external_model("public")
    assert not manager.allows_external_model("secret")
    manager.set_mode("local_only")
    assert not manager.allows_external_model("public")


def test_project_workspace_tracks_active_project(tmp_path):
    manager = ProjectWorkspaceManager(path=tmp_path / "projects.json")

    first = manager.create("Alpha", paths=["/tmp/alpha"])
    second = manager.create("Beta")
    manager.set_active(second["id"])
    snapshot = manager.snapshot()

    assert snapshot["active"]["id"] == second["id"]
    assert first["id"] != second["id"]


def test_os_integration_audit_and_feedback_store(tmp_path):
    os_integration = PersonalOSIntegration(path=tmp_path / "os.json")
    feedback = LearningFeedbackStore(path=tmp_path / "feedback.json")

    validation = os_integration.validate_action("find_files")
    record = os_integration.record("find_files", {"name": "x"}, "success", "ok")
    feedback_record = feedback.add("negative", "msg-1", correction="Use shorter answer")

    assert validation["allowed"] is True
    assert record["status"] == "success"
    assert feedback_record["status"] == "pending_review"
