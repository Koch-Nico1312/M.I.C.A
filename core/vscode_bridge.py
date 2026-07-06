from __future__ import annotations

"""
VS Code Extension Bridge
Allows M.I.C.A to communicate with VS Code for real-time code editing
"""

import asyncio
import json
from pathlib import Path
from typing import Callable, Dict, Optional

try:
    import aiohttp
    import websockets

    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

from config.config_loader import get_config


class VSCodeBridge:
    """Bridge for communicating with VS Code extension"""

    def __init__(self):
        self.config = get_config()
        self.enabled = self.config.get("vscode.bridge_enabled", False)
        self.port = self.config.get("vscode.port", 8080)
        self.auto_connect = self.config.get("vscode.auto_connect", False)

        self.session: Optional[aiohttp.ClientSession] = None
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.connected = False

        if self.enabled and AIOHTTP_AVAILABLE:
            print(f"[VSCode] ✅ Bridge initialized (port: {self.port})")
        elif not AIOHTTP_AVAILABLE:
            print("[VSCode] ⚠️ aiohttp/websockets not available")

    async def connect(self):
        """Connect to VS Code extension"""
        if not self.enabled or not AIOHTTP_AVAILABLE:
            return False

        try:
            self.session = aiohttp.ClientSession()

            # Try WebSocket connection
            ws_url = f"ws://localhost:{self.port}"
            self.websocket = await websockets.connect(ws_url)
            self.connected = True

            print("[VSCode] 🔌 Connected to extension")
            return True

        except Exception as e:
            print(f"[VSCode] ❌ Connection failed: {e}")
            return False

    async def disconnect(self):
        """Disconnect from VS Code extension"""
        if self.websocket:
            await self.websocket.close()
        if self.session:
            await self.session.close()
        self.connected = False
        print("[VSCode] 🔌 Disconnected")

    async def send_command(self, command: str, params: Dict = None) -> Dict:
        """Send a command to VS Code"""
        if not self.connected:
            return {"error": "Not connected to VS Code"}

        try:
            message = {"command": command, "params": params or {}}

            await self.websocket.send(json.dumps(message))
            response = await self.websocket.recv()

            return json.loads(response)

        except Exception as e:
            print(f"[VSCode] ❌ Command error: {e}")
            return {"error": str(e)}

    async def edit_file(self, file_path: str, edits: list) -> Dict:
        """Edit a file in VS Code"""
        return await self.send_command("edit_file", {"file_path": file_path, "edits": edits})

    async def refactor_code(self, file_path: str, pattern: str, replacement: str) -> Dict:
        """Refactor code in VS Code"""
        return await self.send_command(
            "refactor", {"file_path": file_path, "pattern": pattern, "replacement": replacement}
        )

    async def get_cursor_position(self) -> Dict:
        """Get current cursor position in VS Code"""
        return await self.send_command("get_cursor")

    async def set_cursor_position(self, line: int, character: int) -> Dict:
        """Set cursor position in VS Code"""
        return await self.send_command("set_cursor", {"line": line, "character": character})

    async def get_selected_text(self) -> Dict:
        """Get currently selected text in VS Code"""
        return await self.send_command("get_selection")

    async def insert_text(self, text: str) -> Dict:
        """Insert text at cursor position"""
        return await self.send_command("insert_text", {"text": text})

    async def run_code(self, language: str = "python") -> Dict:
        """Run code in VS Code"""
        return await self.send_command("run_code", {"language": language})

    async def get_diagnostics(self) -> Dict:
        """Get diagnostics (errors, warnings) from VS Code"""
        return await self.send_command("get_diagnostics")

    def sync_connect(self) -> bool:
        """Synchronous wrapper for connect"""
        if not self.enabled:
            return False
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return bool(loop.run_until_complete(self.connect()))
        finally:
            loop.close()

    def sync_edit_file(self, file_path: str, old_text: str, new_text: str) -> Dict:
        """Synchronous wrapper for edit_file"""
        if not self.enabled:
            return {"error": "VS Code bridge not enabled"}

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                self.edit_file(file_path, [{"old_text": old_text, "new_text": new_text}])
            )
            return result
        finally:
            loop.close()

    def sync_refactor(self, file_path: str, pattern: str, replacement: str) -> Dict:
        """Synchronous wrapper for refactor"""
        if not self.enabled:
            return {"error": "VS Code bridge not enabled"}

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(self.refactor_code(file_path, pattern, replacement))
            return result
        finally:
            loop.close()

    def sync_run_code(self, language: str = "python") -> Dict:
        """Synchronous wrapper for run_code"""
        if not self.enabled:
            return {"error": "VS Code bridge not enabled"}
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.run_code(language))
        finally:
            loop.close()

    def sync_get_diagnostics(self) -> Dict:
        """Synchronous wrapper for diagnostics"""
        if not self.enabled:
            return {"error": "VS Code bridge not enabled"}
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.get_diagnostics())
        finally:
            loop.close()

    def sync_get_selection(self) -> Dict:
        """Synchronous wrapper for selected text"""
        if not self.enabled:
            return {"error": "VS Code bridge not enabled"}
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.get_selected_text())
        finally:
            loop.close()

    def sync_insert_text(self, text: str) -> Dict:
        """Synchronous wrapper for insert_text"""
        if not self.enabled:
            return {"error": "VS Code bridge not enabled"}
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.insert_text(text))
        finally:
            loop.close()


# Global instance
_vscode_bridge: Optional[VSCodeBridge] = None


def get_vscode_bridge() -> VSCodeBridge:
    """Get the global VS Code bridge instance"""
    global _vscode_bridge
    if _vscode_bridge is None:
        _vscode_bridge = VSCodeBridge()
    return _vscode_bridge
