"""Optional codebase-memory-mcp gateway for M.I.C.A coding agents."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from core.paths import project_path


SERVER_ID = "codebase_memory"
DEFAULT_REPOSITORY = project_path()

READ_OPERATIONS = {
    "list_projects",
    "index_status",
    "check_index_coverage",
    "search_graph",
    "query_graph",
    "trace_path",
    "trace_call_path",
    "get_code_snippet",
    "get_graph_schema",
    "get_architecture",
    "search_code",
    "detect_changes",
}


TOOL_DECLARATION = {
    "name": "codebase_memory",
    "description": (
        "Uses the optional local codebase-memory MCP server for repository indexing, "
        "architecture, structural search, call tracing, and change-impact analysis."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": (
                    "status | setup_preview | enable | disable | connect | projects | index | "
                    "architecture | search | trace | impact | query | adr | ingest_traces | delete_project"
                ),
            },
            "project": {
                "type": "STRING",
                "description": "Indexed project name returned by action=projects.",
            },
            "repo_path": {
                "type": "STRING",
                "description": "Absolute or workspace-relative repository path for action=index.",
            },
            "query": {
                "type": "STRING",
                "description": "Natural-language code search or Cypher query, depending on the action.",
            },
            "symbol": {
                "type": "STRING",
                "description": "Function or qualified symbol name for action=trace.",
            },
            "operation": {
                "type": "STRING",
                "description": "Read-only MCP operation for action=query.",
            },
            "arguments": {
                "type": "OBJECT",
                "description": "Additional operation-specific MCP arguments.",
            },
            "mode": {
                "type": "STRING",
                "description": "full | moderate | fast for indexing; get | update | sections for ADRs.",
            },
            "persistence": {
                "type": "BOOLEAN",
                "description": "Persist a shareable graph artifact when indexing. Defaults to false.",
            },
        },
        "required": [],
    },
}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _get_client():
    from core.mcp_client import get_mcp_client

    return get_mcp_client()


def _server_status(client: Any) -> dict[str, Any]:
    server = client.servers.get(SERVER_ID)
    if server is None:
        return {
            "configured": False,
            "enabled": False,
            "connected": False,
            "installed": False,
            "message": "The codebase_memory server entry is missing from config/mcp_servers.json.",
        }

    command = str(server.command or "codebase-memory-mcp")
    installed = bool(shutil.which(command)) if not Path(command).is_file() else True
    return {
        "configured": True,
        "enabled": bool(server.enabled),
        "connected": bool(server.connected),
        "installed": installed,
        "command": command,
        "transport": server.transport,
        "tool_count": len(server.tools),
        "tools": [str(item.get("name") or "") for item in server.tools],
        "last_connected": server.last_connected,
        "last_error": server.last_error,
        "connection_failures": server.connection_failures,
        "privacy": "Local stdio process; repository data is not sent to an external service.",
    }


def _set_enabled(client: Any, enabled: bool) -> str:
    server = client.servers.get(SERVER_ID)
    if server is None:
        return _json(_server_status(client))
    server.enabled = enabled
    server.config["enabled"] = enabled
    if not enabled:
        server.connected = False
        server.tools = []
    client._save_config()
    return _json({"status": "enabled" if enabled else "disabled", **_server_status(client)})


def _connect(client: Any) -> tuple[bool, str]:
    server = client.servers.get(SERVER_ID)
    if server is None:
        return False, "codebase-memory-mcp is not configured."
    if not server.enabled:
        return False, "codebase-memory-mcp is disabled. Approve action=enable first."

    command = str(server.command or "codebase-memory-mcp")
    if not Path(command).is_file() and not shutil.which(command):
        return (
            False,
            "codebase-memory-mcp is enabled but its executable is not on PATH. "
            "Use action=setup_preview for local installation guidance.",
        )
    if server.connected or client.connect_server(SERVER_ID):
        return True, "connected"
    return False, server.last_error or "MCP connection failed."


def _execute(client: Any, operation: str, arguments: dict[str, Any]) -> str:
    connected, message = _connect(client)
    if not connected:
        return _json({"success": False, "error": message, **_server_status(client)})
    result = client.execute_tool(SERVER_ID, operation, arguments)
    if isinstance(result, dict):
        return _json({"operation": operation, **result})
    return _json({"operation": operation, "success": True, "result": result})


def _resolve_repository(raw: Any) -> tuple[Path | None, str]:
    value = str(raw or "").strip()
    candidate = Path(value).expanduser() if value else DEFAULT_REPOSITORY
    if not candidate.is_absolute():
        candidate = DEFAULT_REPOSITORY / candidate
    try:
        candidate = candidate.resolve(strict=True)
    except (OSError, RuntimeError):
        return None, f"Repository path does not exist: {candidate}"
    if not candidate.is_dir():
        return None, f"Repository path is not a directory: {candidate}"
    if not (candidate / ".git").exists():
        return None, f"Repository path is not a Git working tree: {candidate}"
    return candidate, ""


def codebase_memory(parameters: dict, player=None, speak=None, **kwargs) -> str:
    params = parameters or {}
    action = str(params.get("action") or "status").strip().lower().replace("-", "_")
    client = _get_client()

    if action == "status":
        return _json(_server_status(client))
    if action == "setup_preview":
        return _json(
            {
                "automatic_changes": False,
                "steps": [
                    "Review https://github.com/DeusData/codebase-memory-mcp and its install script.",
                    "Install the signed Windows binary so codebase-memory-mcp is on PATH.",
                    "Approve action=enable, then call action=connect.",
                    "Call action=index with the repository path; use action=projects for its project name.",
                ],
                "configuration": "config/mcp_servers.json -> servers.codebase_memory",
                "default_enabled": False,
            }
        )
    if action == "enable":
        return _set_enabled(client, True)
    if action == "disable":
        return _set_enabled(client, False)
    if action == "connect":
        connected, message = _connect(client)
        return _json({"success": connected, "message": message, **_server_status(client)})
    if action == "projects":
        return _execute(client, "list_projects", {})

    project = str(params.get("project") or "").strip()
    arguments = dict(params.get("arguments") or {})

    if action == "index":
        repository, error = _resolve_repository(params.get("repo_path"))
        if repository is None:
            return _json({"success": False, "error": error})
        mode = str(params.get("mode") or "full").strip().lower()
        if mode not in {"full", "moderate", "fast"}:
            return _json({"success": False, "error": "Index mode must be full, moderate, or fast."})
        arguments = {
            "repo_path": str(repository),
            "mode": mode,
            "persistence": bool(params.get("persistence", False)),
            **arguments,
        }
        return _execute(client, "index_repository", arguments)

    if action in {"architecture", "search", "trace", "impact"} and not project:
        return _json({"success": False, "error": "A project name from action=projects is required."})
    if action == "architecture":
        return _execute(client, "get_architecture", {"project": project, **arguments})
    if action == "search":
        query = str(params.get("query") or "").strip()
        if not query:
            return _json({"success": False, "error": "action=search requires a query."})
        return _execute(client, "search_graph", {"project": project, "query": query, **arguments})
    if action == "trace":
        symbol = str(params.get("symbol") or "").strip()
        if not symbol:
            return _json({"success": False, "error": "action=trace requires a symbol."})
        return _execute(
            client,
            "trace_path",
            {"project": project, "function_name": symbol, **arguments},
        )
    if action == "impact":
        return _execute(client, "detect_changes", {"project": project, **arguments})
    if action == "query":
        operation = str(params.get("operation") or "").strip()
        if operation not in READ_OPERATIONS:
            return _json(
                {
                    "success": False,
                    "error": "action=query accepts only read-only codebase-memory operations.",
                    "allowed_operations": sorted(READ_OPERATIONS),
                }
            )
        return _execute(client, operation, arguments)
    if action == "adr":
        if not project:
            return _json({"success": False, "error": "action=adr requires a project."})
        mode = str(params.get("mode") or "get").strip().lower()
        return _execute(client, "manage_adr", {"project": project, "mode": mode, **arguments})
    if action == "ingest_traces":
        if not project:
            return _json({"success": False, "error": "action=ingest_traces requires a project."})
        return _execute(client, "ingest_traces", {"project": project, **arguments})
    if action == "delete_project":
        if not project:
            return _json({"success": False, "error": "action=delete_project requires a project."})
        return _execute(client, "delete_project", {"project": project})

    return _json(
        {
            "success": False,
            "error": (
                "Unknown action. Use status, setup_preview, enable, disable, connect, projects, "
                "index, architecture, search, trace, impact, query, adr, ingest_traces, or delete_project."
            ),
        }
    )
