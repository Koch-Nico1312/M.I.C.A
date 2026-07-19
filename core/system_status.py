"""Live availability checks for user-facing M.I.C.A services."""

from __future__ import annotations

import json
import tempfile
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from config.config_loader import get_config
from core.paths import project_path


StatusCheck = Callable[[], dict[str, Any]]


def _now() -> str:
    return datetime.now().isoformat()


def _result(
    check_id: str,
    label: str,
    status: str,
    summary: str,
    *,
    detail: str = "",
    latency_ms: int = 0,
) -> dict[str, Any]:
    return {
        "id": check_id,
        "label": label,
        "status": status,
        "summary": summary,
        "detail": detail,
        "latency_ms": latency_ms,
        "checked_at": _now(),
    }


def _timed(check: StatusCheck, check_id: str, label: str) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        result = check()
    except Exception as exc:
        result = _result(
            check_id,
            label,
            "unavailable",
            "Nicht erreichbar",
            detail=f"{type(exc).__name__}: {exc}",
        )
    result["latency_ms"] = max(0, round((time.perf_counter() - started) * 1000))
    return result


def _read_json(url: str, *, headers: dict[str, str] | None = None, timeout: float = 3.0) -> Any:
    request = urllib.request.Request(url, headers=headers or {"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace") or "{}")


def _check_gemini() -> dict[str, Any]:
    config = get_config()
    api_key = str(config.get_api_key("gemini") or "").strip()
    if not api_key:
        return _result("gemini", "Gemini", "unavailable", "API-Schlüssel fehlt", detail="GEMINI_API_KEY ist nicht gesetzt.")
    try:
        payload = _read_json(
            "https://generativelanguage.googleapis.com/v1beta/models",
            headers={"Accept": "application/json", "x-goog-api-key": api_key},
        )
        models = payload.get("models", []) if isinstance(payload, dict) else []
        return _result("gemini", "Gemini", "available", "Verbunden", detail=f"{len(models)} Modelle erreichbar")
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403}:
            detail = "Der konfigurierte API-Schlüssel wurde von Gemini abgelehnt."
        elif exc.code == 429:
            detail = "Gemini ist erreichbar, das aktuelle Kontingent ist jedoch ausgeschöpft."
        else:
            detail = f"Gemini antwortete mit HTTP {exc.code}."
        return _result("gemini", "Gemini", "degraded", "Verbindung eingeschränkt", detail=detail)


def _check_ollama() -> dict[str, Any]:
    config = get_config()
    base_url = str(config.get("ollama.base_url", "http://localhost:11434") or "http://localhost:11434").rstrip("/")
    try:
        payload = _read_json(f"{base_url}/api/tags", timeout=2.0)
        models = payload.get("models", []) if isinstance(payload, dict) else []
        summary = "Verbunden" if models else "Verbunden, keine Modelle installiert"
        return _result("ollama", "Ollama", "available" if models else "degraded", summary, detail=f"{len(models)} lokale Modelle")
    except (urllib.error.URLError, TimeoutError, OSError):
        return _result("ollama", "Ollama", "unavailable", "Nicht erreichbar", detail=f"Kein Dienst unter {base_url}")


def _check_microphone() -> dict[str, Any]:
    try:
        import sounddevice as sd

        default_input = sd.default.device[0] if isinstance(sd.default.device, (list, tuple)) else sd.default.device
        device = sd.query_devices(default_input, "input")
        channels = int(device.get("max_input_channels", 0))
        if channels < 1:
            return _result("microphone", "Mikrofon", "unavailable", "Kein Eingang verfügbar")
        return _result(
            "microphone",
            "Mikrofon",
            "available",
            "Bereit",
            detail=f"{device.get('name', 'Standardmikrofon')} · {channels} Kanal/Kanäle",
        )
    except Exception as exc:
        return _result("microphone", "Mikrofon", "unavailable", "Nicht verfügbar", detail=str(exc))


def _check_browser() -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            executable = Path(playwright.chromium.executable_path)
            if executable.exists():
                return _result("browser", "Browser", "available", "Bereit", detail=str(executable))
            return _result(
                "browser",
                "Browser",
                "degraded",
                "Playwright installiert, Browser fehlt",
                detail="Mit 'python -m playwright install chromium' nachinstallieren.",
            )
    except Exception as exc:
        return _result("browser", "Browser", "unavailable", "Nicht verfügbar", detail=str(exc))


def _check_mcp() -> dict[str, Any]:
    from core.mcp_client import get_mcp_client

    client = get_mcp_client()
    enabled = [server for server in client.servers.values() if server.enabled]
    connected = [server for server in enabled if server.connected]
    tools = client.get_tools()
    if not enabled:
        return _result("mcp", "MCP", "degraded", "Kein Server aktiviert", detail="MCP ist verfügbar, aber noch nicht konfiguriert.")
    if not connected:
        return _result("mcp", "MCP", "degraded", "Server konfiguriert, nicht verbunden", detail=f"{len(enabled)} aktivierte Server")
    return _result("mcp", "MCP", "available", "Verbunden", detail=f"{len(connected)}/{len(enabled)} Server · {len(tools)} Tools")


def _check_database() -> dict[str, Any]:
    from core.platform_hub import get_platform_hub

    hub = get_platform_hub()
    status = hub.state_store.status()
    backend = str(status.get("backend") or "json")
    if backend == "postgres":
        fallback = str(status.get("status") or "") != "ready"
        return _result(
            "database",
            "Datenbank",
            "degraded" if fallback else "available",
            "Fallback aktiv" if fallback else "Postgres verbunden",
            detail=str(status.get("last_error") or status.get("driver") or "Persistenter Plattform-Store"),
        )

    data_dir = project_path("data")
    data_dir.mkdir(parents=True, exist_ok=True)
    probe_path = ""
    with tempfile.NamedTemporaryFile(prefix=".mica-db-probe-", dir=data_dir, delete=False) as probe:
        probe.write(b"ok")
        probe_path = probe.name
    Path(probe_path).unlink(missing_ok=True)
    return _result("database", "Datenbank", "available", "Lokaler Speicher bereit", detail=str(data_dir))


class SystemStatusManager:
    def __init__(self, cache_seconds: float = 20.0):
        self.cache_seconds = cache_seconds
        self._lock = threading.RLock()
        self._cached: dict[str, Any] | None = None
        self._cached_at = 0.0

    def snapshot(self, *, force: bool = False) -> dict[str, Any]:
        with self._lock:
            if not force and self._cached and time.monotonic() - self._cached_at < self.cache_seconds:
                return dict(self._cached)

        checks: list[tuple[str, str, StatusCheck]] = [
            ("gemini", "Gemini", _check_gemini),
            ("ollama", "Ollama", _check_ollama),
            ("microphone", "Mikrofon", _check_microphone),
            ("browser", "Browser", _check_browser),
            ("mcp", "MCP", _check_mcp),
            ("database", "Datenbank", _check_database),
        ]
        with ThreadPoolExecutor(max_workers=len(checks), thread_name_prefix="MICAStatus") as executor:
            futures = [executor.submit(_timed, check, check_id, label) for check_id, label, check in checks]
            results = [future.result() for future in futures]
        counts = {
            status: sum(1 for item in results if item["status"] == status)
            for status in ("available", "degraded", "unavailable")
        }
        overall = "available" if counts["unavailable"] == 0 and counts["degraded"] == 0 else "degraded"
        if counts["available"] == 0:
            overall = "unavailable"
        payload = {"status": overall, "checked_at": _now(), "counts": counts, "services": results}
        with self._lock:
            self._cached = payload
            self._cached_at = time.monotonic()
        return dict(payload)


_manager: SystemStatusManager | None = None
_manager_lock = threading.Lock()


def get_system_status_manager() -> SystemStatusManager:
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = SystemStatusManager()
    return _manager
