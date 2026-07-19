"""
MCP CLIENT - MODEL CONTEXT PROTOCOL
===================================
Implements the Model Context Protocol for external tool server integration.
Allows M.I.C.A to connect to external MCP servers and use their tools.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp_client")

# Optional MCP SDK support
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    print("[MCP] ⚠️ MCP Python SDK is not available. Stdio transport will be disabled.")

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("[MCP] ⚠️ Requests library is not available. HTTP transport will be disabled.")

BASE_DIR = Path(__file__).resolve().parent.parent
MCP_CONFIG_FILE = BASE_DIR / "config" / "mcp_servers.json"

DEFAULT_TIMEOUT = 10  # seconds


class MCPServer:
    """Configuration for an MCP server."""

    def __init__(self, server_id: str, name: str, config: dict[str, Any]):
        self.server_id = server_id
        self.name = name
        self.config = config
        self.transport = config.get("transport", "stdio")  # stdio or http
        self.command = config.get("command")
        self.args = config.get("args", [])
        self.env = config.get("env", {})
        self.url = config.get("url")
        self.headers = config.get("headers", {})
        self.enabled = config.get("enabled", True)
        self.timeout = config.get("timeout", DEFAULT_TIMEOUT)
        self.tools: list[dict[str, Any]] = []
        self.connected = False
        self.last_connected: str | None = None
        self.last_error: str | None = None
        self.connection_failures = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "server_id": self.server_id,
            "name": self.name,
            "transport": self.transport,
            "enabled": self.enabled,
            "connected": self.connected,
            "tool_count": len(self.tools),
            "last_connected": self.last_connected,
            "last_error": self.last_error,
            "connection_failures": self.connection_failures,
        }


class MCPClient:
    """
    MCP Client for connecting to external tool servers.
    """

    def __init__(self):
        self.servers: dict[str, MCPServer] = {}
        self._load_config()

    def _load_config(self) -> None:
        """Load MCP server configuration."""
        try:
            if MCP_CONFIG_FILE.exists():
                with open(MCP_CONFIG_FILE, "r", encoding="utf-8") as f:
                    config = json.load(f)

                    for server_id, server_config in config.get("servers", {}).items():
                        server = MCPServer(
                            server_id, server_config.get("name", server_id), server_config
                        )
                        self.servers[server_id] = server

                print(f"[MCP] Loaded {len(self.servers)} MCP server configurations")
            else:
                self._create_default_config()

        except Exception as e:
            print(f"[MCP] Failed to load MCP config: {e}")
            self._create_default_config()

    def _create_default_config(self) -> None:
        """Create default MCP configuration."""
        default_config = {
            "servers": {
                "fetch": {
                    "name": "Fetch MCP Server",
                    "transport": "http",
                    "url": "http://localhost:8000",
                    "enabled": False,
                    "timeout": DEFAULT_TIMEOUT,
                }
            }
        }

        try:
            MCP_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(MCP_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=2)
            print("[MCP] Created default MCP configuration at config/mcp_servers.json")
        except Exception as e:
            print(f"[MCP] Failed to create default config: {e}")

    def _save_config(self) -> None:
        """Save MCP server configuration."""
        try:
            config = {
                "servers": {server_id: server.config for server_id, server in self.servers.items()}
            }

            with open(MCP_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)

        except Exception as e:
            print(f"[MCP] Failed to save MCP config: {e}")

    def add_server(self, server_id: str, name: str, config: dict[str, Any]) -> bool:
        """Add a new MCP server configuration."""
        try:
            server = MCPServer(server_id, name, config)
            self.servers[server_id] = server
            self._save_config()
            print(f"[MCP] Added MCP server: {name}")
            return True
        except Exception as e:
            print(f"[MCP] Failed to add server: {e}")
            return False

    def remove_server(self, server_id: str) -> bool:
        """Remove an MCP server configuration."""
        try:
            if server_id in self.servers:
                self.servers[server_id].connected = False
                del self.servers[server_id]
                self._save_config()
                print(f"[MCP] Removed MCP server: {server_id}")
                return True
            return False
        except Exception as e:
            print(f"[MCP] Failed to remove server: {e}")
            return False

    def connect_server(self, server_id: str) -> bool:
        """Connect to an MCP server."""
        server = self.servers.get(server_id)
        if not server or not server.enabled:
            return False

        if server.connected:
            return True

        try:
            if server.transport == "http":
                return self._connect_http(server)
            elif server.transport == "stdio":
                return self._connect_stdio(server)
            else:
                print(f"[MCP] Unknown transport type '{server.transport}' for server {server_id}")
                return False
        except Exception as e:
            server.last_error = str(e)
            server.connection_failures += 1
            print(f"[MCP] Failed to connect to server {server_id}: {e}")
            return False

    def _connect_http(self, server: MCPServer) -> bool:
        if not REQUESTS_AVAILABLE:
            print("[MCP] Requests library is not available. HTTP connection aborted.")
            return False
        try:
            url = f"{server.url.rstrip('/')}/tools"
            response = requests.get(url, headers=server.headers, timeout=server.timeout)
            if response.status_code == 200:
                data = response.json()
                server.tools = data.get("tools", [])
                server.connected = True
                server.last_connected = datetime.now().isoformat()
                server.last_error = None
                print(
                    f"[MCP] Connected to HTTP server '{server.name}' with {len(server.tools)} tools."
                )
                return True
            else:
                server.last_error = f"HTTP {response.status_code}"
                server.connection_failures += 1
                return False
        except Exception as e:
            server.last_error = str(e)
            server.connection_failures += 1
            print(f"[MCP] HTTP connection failed for '{server.name}': {e}")
            return False

    def _connect_stdio(self, server: MCPServer) -> bool:
        if not MCP_AVAILABLE:
            print("[MCP] MCP Python SDK is not available. Stdio connection aborted.")
            return False
        try:
            # Gather server tools synchronously by running a temporary loop
            loop = asyncio.new_event_loop()

            async def discover():
                server_params = StdioServerParameters(
                    command=server.command, args=server.args, env={**os.environ, **server.env}
                )
                async with stdio_client(server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        tools_result = await session.list_tools()
                        return tools_result.tools

            tools = loop.run_until_complete(discover())
            loop.close()

            server.tools = []
            for t in tools:
                server.tools.append(
                    {"name": t.name, "description": t.description, "input_schema": t.inputSchema}
                )

            server.connected = True
            server.last_connected = datetime.now().isoformat()
            server.last_error = None
            print(
                f"[MCP] Connected to Stdio server '{server.name}' with {len(server.tools)} tools."
            )
            return True
        except Exception as e:
            server.last_error = str(e)
            server.connection_failures += 1
            print(f"[MCP] Stdio connection failed for '{server.name}': {e}")
            return False

    def execute_tool(
        self, server_id: str, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute a tool on a connected server."""
        server = self.servers.get(server_id)
        if not server or not server.connected:
            return {"success": False, "error": f"Server '{server_id}' is not connected."}

        try:
            if server.transport == "http":
                return self._execute_http(server, tool_name, arguments)
            elif server.transport == "stdio":
                return self._execute_stdio(server, tool_name, arguments)
            else:
                return {"success": False, "error": f"Unknown transport: {server.transport}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _execute_http(
        self, server: MCPServer, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            url = f"{server.url.rstrip('/')}/tools/{tool_name}"
            response = requests.post(
                url, json=arguments, headers=server.headers, timeout=server.timeout
            )
            if response.status_code == 200:
                return {"success": True, "result": response.json()}
            else:
                return {
                    "success": False,
                    "error": f"HTTP status {response.status_code}: {response.text}",
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _execute_stdio(
        self, server: MCPServer, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        if not MCP_AVAILABLE:
            return {"success": False, "error": "MCP SDK is not installed."}
        try:
            loop = asyncio.new_event_loop()

            async def run():
                server_params = StdioServerParameters(
                    command=server.command, args=server.args, env={**os.environ, **server.env}
                )
                async with stdio_client(server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool(tool_name, arguments)
                        return result

            res = loop.run_until_complete(run())
            loop.close()

            content_list = []
            for item in res.content:
                if hasattr(item, "text"):
                    content_list.append(item.text)
                elif isinstance(item, dict) and "text" in item:
                    content_list.append(item["text"])
                else:
                    content_list.append(str(item))

            return {"success": True, "result": "\n".join(content_list)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def connect_all_enabled(self) -> dict[str, bool]:
        results = {}
        for server_id, server in self.servers.items():
            if server.enabled:
                results[server_id] = self.connect_server(server_id)
        return results

    def get_tools(self, server_id: str | None = None) -> list[dict[str, Any]]:
        """Get available tools from connected servers."""
        tools_list = []
        if server_id:
            server = self.servers.get(server_id)
            if server and server.connected:
                for t in server.tools:
                    tools_list.append(
                        {
                            "server_id": server_id,
                            "original_name": t["name"],
                            "name": f"mcp_{server_id}_{t['name']}",
                            "description": f"[MCP: {server.name}] {t.get('description', '')}",
                            "parameters": t.get("input_schema", {"type": "object"}),
                        }
                    )
        else:
            for s_id, server in self.servers.items():
                if server.connected:
                    for t in server.tools:
                        tools_list.append(
                            {
                                "server_id": s_id,
                                "original_name": t["name"],
                                "name": f"mcp_{s_id}_{t['name']}",
                                "description": f"[MCP: {server.name}] {t.get('description', '')}",
                                "parameters": t.get("input_schema", {"type": "object"}),
                            }
                        )
        return tools_list


# Global instance management
_client: MCPClient | None = None
_client_lock = threading.Lock()


def get_mcp_client() -> MCPClient:
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = MCPClient()
    return _client


def add_mcp_server(server_id: str, name: str, config: dict[str, Any]) -> bool:
    return get_mcp_client().add_server(server_id, name, config)


def execute_mcp_tool(server_id: str, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return get_mcp_client().execute_tool(server_id, tool_name, arguments)


def get_mcp_tools(server_id: str | None = None) -> list[dict[str, Any]]:
    return get_mcp_client().get_tools(server_id)


__all__ = [
    "MCPClient",
    "MCPServer",
    "get_mcp_client",
    "add_mcp_server",
    "execute_mcp_tool",
    "get_mcp_tools",
]
