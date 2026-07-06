from __future__ import annotations

from collections import deque
from io import BytesIO
import threading


class UploadField:
    def __init__(self, filename: str, data: bytes):
        self.filename = filename
        self.file = BytesIO(data)


def make_ui_bridge():
    from ui_bridge import MicaUI

    ui = object.__new__(MicaUI)
    ui._lock = threading.RLock()
    ui._logs = deque(maxlen=20)
    return ui


def test_save_uploaded_files_analyzes_text_and_updates_payload(tmp_path, monkeypatch):
    import ui_bridge

    monkeypatch.setattr(ui_bridge, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(ui_bridge, "DOCUMENT_INDEX_PATH", tmp_path / "ui_documents.json")

    ui = make_ui_bridge()
    result = ui._save_uploaded_files(
        [UploadField("notes.txt", b"First useful line\nSecond line")],
        analyze=True,
        should_index=False,
    )

    assert result["status"] == "uploaded"
    assert result["errors"] == []
    assert result["indexed"] is False
    assert len(result["files"]) == 1
    assert result["files"][0]["name"] == "notes.txt"
    assert result["files"][0]["analysis"] == "First useful line"
    assert (tmp_path / "uploads" / "notes.txt").read_text(encoding="utf-8") == "First useful line\nSecond line"


def test_devices_payload_uses_lazy_psutil_import(monkeypatch):
    import ui_bridge

    ui = make_ui_bridge()
    monkeypatch.setattr(ui_bridge, "_psutil_module", None)

    result = ui._devices_payload()

    assert result["current"]["pid"]
    assert result["current"]["metrics_available"] is True
    assert result["items"][0]["status"] == "online"


def test_devices_payload_falls_back_without_psutil(monkeypatch):
    import ui_bridge

    ui = make_ui_bridge()
    monkeypatch.setattr(ui_bridge, "_get_psutil", lambda: None)

    result = ui._devices_payload()

    assert result["current"]["pid"]
    assert result["current"]["process"] == "python"
    assert result["current"]["metrics_available"] is False
    assert result["items"][0]["status"] == "online"


def test_knowledge_action_uses_shared_knowledge_manager(monkeypatch):
    import ui_bridge
    import core.knowledge_manager as knowledge_module

    class FakeManager:
        adapters = []

        def __init__(self):
            self.calls = []

        def search(self, query, *, limit, sources):
            self.calls.append(("search", query, limit, sources))
            return [
                knowledge_module.KnowledgeResult(
                    title="Docker",
                    content="Docker uses namespaces.",
                    source="documents",
                    uri="docs/Docker.md",
                )
            ]

        def suggest_notes(self, query, *, limit, sources):
            self.calls.append(("suggest_notes", query, limit, sources))
            return knowledge_module.KnowledgeNotePlan(
                query=query,
                suggestions=[
                    knowledge_module.KnowledgeNoteSuggestion(
                        title="Docker",
                        summary="Docker uses namespaces.",
                        sources=["docs/Docker.md"],
                        links=[],
                        tags=["mica-knowledge"],
                        confidence=0.7,
                        reason="test",
                        content="# Docker\n",
                    )
                ],
                graph_edges=[],
            )

    fake = FakeManager()
    monkeypatch.setattr(knowledge_module, "get_knowledge_manager", lambda: fake)

    ui = make_ui_bridge()
    search_result = ui._knowledge_action(
        {"action": "search", "query": "docker", "sources": ["documents"], "max_results": 3}
    )
    suggest_result = ui._knowledge_action(
        {"action": "suggest_notes", "query": "docker", "sources": ["documents"]}
    )

    assert fake.calls[0] == ("search", "docker", 3, ["documents"])
    assert search_result["results"][0]["title"] == "Docker"
    assert suggest_result["suggestions"][0]["title"] == "Docker"


def test_command_center_payload_aggregates_status(monkeypatch):
    ui = make_ui_bridge()

    monkeypatch.setattr(ui, "_current_state", lambda: {"state": "LISTENING", "default_view": "command-center"})
    monkeypatch.setattr(
        ui,
        "_resource_snapshot",
        lambda: {
            "threads": 3,
            "performance": {"active_tasks": 1, "current_activity": "indexing"},
        },
    )
    monkeypatch.setattr(ui, "_setup_payload", lambda: {"configured": False})
    monkeypatch.setattr(
        ui,
        "_cockpit_payload",
        lambda: {
            "calendar": {
                "items": [],
                "status": {"authenticated": False},
            },
            "reminders": [],
            "tasks": [{"id": "task-1", "title": "Index docs", "status": "aktiv"}],
            "next_best_step": {"title": "Review docs", "reason": "latest upload", "action": "Dokumente"},
        },
    )
    monkeypatch.setattr(
        ui,
        "_resume_payload",
        lambda: {
            "open_ends": [{"id": "question-1", "title": "Noch offen?", "source": "session"}],
            "recent_files": [{"id": "file-1", "title": "notes.md", "status": "bereit"}],
        },
    )
    monkeypatch.setattr(
        ui,
        "_documents_payload",
        lambda: {"files": [{"id": "doc-1", "indexed": True}, {"id": "doc-2", "indexed": False}]},
    )
    monkeypatch.setattr(
        ui,
        "_action_history_payload",
        lambda: {"records": [{"id": "action-1", "tool_name": "search", "action": "query", "status": "ok"}]},
    )
    monkeypatch.setattr(
        ui,
        "_approvals_payload",
        lambda: {
            "pending": [
                {
                    "summary": "Datei schreiben?",
                    "reason": "write action",
                    "risk_level": "medium",
                }
            ]
        },
    )
    monkeypatch.setattr(
        ui,
        "_permissions_payload",
        lambda: {"tools": [{"name": "search", "enabled": True}, {"name": "write", "enabled": False}]},
    )
    monkeypatch.setattr(
        ui,
        "_reliability_payload",
        lambda: {"status": "degraded", "recommendations": ["Run healthcheck"], "counts": {}},
    )
    monkeypatch.setattr(
        ui,
        "_quick_actions_payload",
        lambda: {"items": [{"id": "healthcheck", "label": "Healthcheck", "command": "run healthcheck"}]},
    )

    payload = ui._command_center_payload()

    assert payload["status_cards"][0]["id"] == "backend"
    assert payload["status_cards"][2]["value"] == "1/2 Dateien"
    assert payload["active_tasks"][0]["title"] == "Index docs"
    assert payload["open_questions"][1]["title"] == "Datei schreiben?"
    assert payload["recent_actions"][0]["tool_name"] == "search"
    assert any(item["id"] == "setup" for item in payload["warnings"])
    assert payload["quick_actions"][0]["command"] == "run healthcheck"
