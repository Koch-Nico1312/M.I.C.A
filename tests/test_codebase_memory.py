import json
from pathlib import Path
from types import SimpleNamespace


class FakeClient:
    def __init__(self, *, enabled=True, connected=True):
        self.saved = 0
        self.connected_calls = 0
        self.executions = []
        self.servers = {
            "codebase_memory": SimpleNamespace(
                command="codebase-memory-mcp",
                enabled=enabled,
                connected=connected,
                config={"enabled": enabled},
                transport="stdio",
                tools=[{"name": "search_graph"}],
                last_connected=None,
                last_error=None,
                connection_failures=0,
            )
        }

    def _save_config(self):
        self.saved += 1

    def connect_server(self, server_id):
        self.connected_calls += 1
        self.servers[server_id].connected = True
        return True

    def execute_tool(self, server_id, operation, arguments):
        self.executions.append((server_id, operation, arguments))
        return {"success": True, "result": {"ok": True}}


def test_status_reports_optional_local_server(monkeypatch):
    from actions import codebase_memory

    client = FakeClient(enabled=False, connected=False)
    monkeypatch.setattr(codebase_memory, "_get_client", lambda: client)
    monkeypatch.setattr(codebase_memory.shutil, "which", lambda _command: None)

    result = json.loads(codebase_memory.codebase_memory({"action": "status"}))

    assert result["configured"] is True
    assert result["enabled"] is False
    assert result["installed"] is False
    assert "Local stdio" in result["privacy"]


def test_enable_is_explicit_and_persisted(monkeypatch):
    from actions import codebase_memory

    client = FakeClient(enabled=False, connected=False)
    monkeypatch.setattr(codebase_memory, "_get_client", lambda: client)
    monkeypatch.setattr(codebase_memory.shutil, "which", lambda _command: "codebase-memory-mcp")

    result = json.loads(codebase_memory.codebase_memory({"action": "enable"}))

    assert result["enabled"] is True
    assert client.servers["codebase_memory"].config["enabled"] is True
    assert client.saved == 1


def test_search_maps_to_structural_mcp_query(monkeypatch):
    from actions import codebase_memory

    client = FakeClient()
    monkeypatch.setattr(codebase_memory, "_get_client", lambda: client)
    monkeypatch.setattr(codebase_memory.shutil, "which", lambda _command: "codebase-memory-mcp")

    result = json.loads(
        codebase_memory.codebase_memory(
            {"action": "search", "project": "mica", "query": "approval routing"}
        )
    )

    assert result["success"] is True
    assert client.executions == [
        (
            "codebase_memory",
            "search_graph",
            {"project": "mica", "query": "approval routing"},
        )
    ]


def test_query_rejects_mutating_operation(monkeypatch):
    from actions import codebase_memory

    client = FakeClient()
    monkeypatch.setattr(codebase_memory, "_get_client", lambda: client)

    result = json.loads(
        codebase_memory.codebase_memory(
            {"action": "query", "operation": "delete_project", "arguments": {"project": "mica"}}
        )
    )

    assert result["success"] is False
    assert "read-only" in result["error"]
    assert client.executions == []


def test_index_uses_resolved_git_worktree(monkeypatch, tmp_path: Path):
    from actions import codebase_memory

    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / ".git").mkdir()
    client = FakeClient()
    monkeypatch.setattr(codebase_memory, "_get_client", lambda: client)
    monkeypatch.setattr(codebase_memory.shutil, "which", lambda _command: "codebase-memory-mcp")

    result = json.loads(
        codebase_memory.codebase_memory(
            {"action": "index", "repo_path": str(repository), "mode": "moderate"}
        )
    )

    assert result["success"] is True
    assert client.executions[0][1] == "index_repository"
    assert client.executions[0][2] == {
        "repo_path": str(repository.resolve()),
        "mode": "moderate",
        "persistence": False,
    }


def test_disabled_server_does_not_spawn_process(monkeypatch):
    from actions import codebase_memory

    client = FakeClient(enabled=False, connected=False)
    monkeypatch.setattr(codebase_memory, "_get_client", lambda: client)

    result = json.loads(codebase_memory.codebase_memory({"action": "projects"}))

    assert result["success"] is False
    assert "disabled" in result["error"]
    assert client.connected_calls == 0


def test_mcp_config_keeps_codebase_memory_disabled_by_default():
    config = json.loads(Path("config/mcp_servers.json").read_text(encoding="utf-8"))
    server = config["servers"]["codebase_memory"]

    assert server["transport"] == "stdio"
    assert server["command"] == "codebase-memory-mcp"
    assert server["enabled"] is False
