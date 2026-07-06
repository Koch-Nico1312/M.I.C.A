from __future__ import annotations

from collections import deque
import threading

from core.platform_hub import PlatformHub


class DummyRequest:
    def __init__(self, path: str):
        self.path = path
        self.status = 0
        self.payload = None
        self.blob = b""
        self.content_type = ""

    def _send_json(self, status: int, payload: dict):
        self.status = status
        self.payload = payload
        return payload

    def _send_bytes(self, status: int, blob: bytes, content_type: str):
        self.status = status
        self.blob = blob
        self.content_type = content_type
        return blob


def make_ui_bridge():
    from ui_bridge import MicaUI

    ui = object.__new__(MicaUI)
    ui._lock = threading.RLock()
    ui._logs = deque(maxlen=20)
    return ui


def test_published_agent_routes_return_html_and_mcp_descriptor(tmp_path, monkeypatch):
    import ui_bridge

    hub = PlatformHub(
        store_path=tmp_path / "platform.json",
        community_plugin_dir=tmp_path / "plugins",
        published_dir=tmp_path / "published",
        browser_companion_dir=tmp_path / "companion",
    )
    monkeypatch.setattr(ui_bridge, "get_platform_hub", lambda: hub)
    ui = make_ui_bridge()

    app_request = DummyRequest("/apps/research-copilot")
    embed_request = DummyRequest("/embed/research-copilot")
    mcp_request = DummyRequest("/mcp/research-copilot")

    ui._handle_get(app_request)
    ui._handle_get(embed_request)
    ui._handle_get(mcp_request)

    assert app_request.status == 200
    assert app_request.content_type == "text/html; charset=utf-8"
    assert b"/api/agents/research-copilot/invoke" in app_request.blob
    assert embed_request.status == 200
    assert b'class="embed"' in embed_request.blob
    assert mcp_request.status == 200
    assert mcp_request.payload["tools"][0]["endpoint"] == "/api/agents/research-copilot/invoke"
