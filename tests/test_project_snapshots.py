from agent.task_pipeline import TaskPipelineManager
from core.project_snapshots import ProjectSnapshotManager
from core.project_workspace import ProjectWorkspaceManager


def test_snapshot_roundtrip_is_secret_free(tmp_path):
    manager = ProjectSnapshotManager(tmp_path / "snapshots")
    created = manager.create(
        "Before refactor",
        {
            "project_state": {"focus": "Agent Hub", "api_key": "must-not-leak"},
            "supervisor_automation": {"enabled": True, "token": "must-not-leak"},
            "project_workspaces": {"items": [{"id": "proj-1"}]},
            "task_pipelines": {"pipelines": [{"id": "pipe-1"}]},
        },
    )

    package = manager.export(created["id"])
    encoded = str(package)
    assert package["format"] == "mica-solo-project/v1"
    assert package["data"]["project_state"]["focus"] == "Agent Hub"
    assert "must-not-leak" not in encoded
    assert created["pipeline_count"] == 1


def test_snapshot_import_gets_new_identity_and_can_be_deleted(tmp_path):
    manager = ProjectSnapshotManager(tmp_path / "snapshots")
    original = manager.create("Original", {"project_state": {"focus": "A"}})
    imported = manager.import_package(manager.export(original["id"]))

    assert imported["id"] != original["id"]
    assert len(manager.list()["items"]) == 2
    manager.delete(imported["id"])
    assert [item["id"] for item in manager.list()["items"]] == [original["id"]]


def test_workspace_and_pipeline_restore_replace_current_state(tmp_path):
    workspaces = ProjectWorkspaceManager(tmp_path / "workspaces.json")
    pipelines = TaskPipelineManager(tmp_path / "pipelines.json")
    workspaces.create("Temporary")
    pipelines.create_pipeline("Temporary task")

    workspace_result = workspaces.restore(
        {"items": [{"id": "proj-restored", "name": "Restored", "paths": [], "notes": [], "tags": [], "active": True, "archived": False, "created_at": "2026-01-01T00:00:00"}]}
    )
    pipeline_result = pipelines.restore(
        {"pipelines": [{"id": "pipe-restored", "goal": "Restored task", "status": "paused", "created_at": "2026-01-01T00:00:00", "updated_at": "2026-01-01T00:00:00", "steps": [], "requires_approval": False}]}
    )

    assert workspace_result["active"]["id"] == "proj-restored"
    assert [item["id"] for item in pipeline_result["pipelines"]] == ["pipe-restored"]
