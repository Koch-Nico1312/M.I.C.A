from __future__ import annotations

import asyncio
import contextlib
import json
import mimetypes
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import unquote, urlparse
from uuid import uuid4

import psutil

from config.config_loader import get_config
from core.logger import get_logger
from core.metrics_collector import get_metrics_collector
from core.paths import project_path, resolve_project_root
from core.performance_flags import get_performance_flags
from core.performance_monitor import get_performance_monitor
from core.performance_tracker import get_performance_tracker
from core.session_manager import get_session_manager

try:
    if os.environ.get("JARVIS_NO_QT"):
        raise ImportError("Qt disabled by JARVIS_NO_QT environment variable")
    from PyQt6.QtCore import QUrl
    from PyQt6.QtGui import QColor
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWidgets import QApplication, QMainWindow

    QT_WEBENGINE_AVAILABLE = True
except Exception:
    QUrl = None  # type: ignore[assignment]
    QColor = None  # type: ignore[assignment]
    QApplication = None  # type: ignore[assignment]
    QMainWindow = object  # type: ignore[assignment]
    QWebEngineView = None  # type: ignore[assignment]
    QT_WEBENGINE_AVAILABLE = False


logger = get_logger(__name__)


BASE_DIR = resolve_project_root()
UI_DIR = project_path("UI")
UI_DIST_DIR = UI_DIR / "dist"
VITE_BIN = UI_DIR / "node_modules" / "vite" / "bin" / "vite.js"
UPLOAD_DIR = project_path("data", "uploads")
DOCUMENT_INDEX_PATH = project_path("data", "ui_documents.json")


class _MultipartUpload:
    def __init__(self, filename: str, data: bytes):
        self.filename = filename
        self.file = BytesIO(data)


def _find_node_executable() -> Optional[str]:
    node = shutil.which("node")
    if node:
        return node

    for candidate in (
        Path(r"C:\Program Files\nodejs\node.exe"),
        Path(r"C:\Program Files (x86)\nodejs\node.exe"),
    ):
        if candidate.exists():
            return str(candidate)

    return None


class _JARVISWindow(QMainWindow):
    def __init__(self, ui: "JarvisUI", url: str):
        super().__init__()
        self._ui = ui
        self.setWindowTitle("J.A.R.V.I.S")
        self.resize(1460, 960)
        self.setMinimumSize(1180, 760)
        
        # Set window flags to prevent flickering and disappearing
        from PyQt6.QtCore import Qt
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinMaxButtonsHint |
            Qt.WindowType.WindowCloseButtonHint
        )

        if QWebEngineView is None:
            raise RuntimeError("Qt WebEngine is not available")

        self._web = QWebEngineView(self)
        if QColor is not None:
            self._web.page().setBackgroundColor(QColor("#041018"))
        self.setCentralWidget(self._web)
        self._web.setUrl(QUrl(url))

    def closeEvent(self, event):  # noqa: N802
        try:
            self._ui.shutdown()
        finally:
            super().closeEvent(event)


class JarvisUI:
    """
    Small Python bridge that launches the React UI in a dedicated window and
    exposes the runtime state for the frontend.
    """

    def __init__(self, face_path: str, size=None):
        self.face_path = Path(face_path)
        self.size = size
        self.root = self

        self._lock = threading.RLock()
        self._muted = False
        self._current_file: Optional[str] = None
        self._state = "LISTENING"
        self._logs = deque(maxlen=500)
        self._on_text_command = None
        self._shutdown_event = threading.Event()
        self._server: Optional[ThreadingHTTPServer] = None
        self._server_thread: Optional[threading.Thread] = None
        self._server_url: Optional[str] = None
        self._vite_process: Optional[subprocess.Popen] = None
        self._app = None
        self._window = None
        self._config = get_config()
        self._session_manager = get_session_manager()

        # Debouncing and dirty flag for UI state updates
        self._state_dirty = False
        self._last_state_hash = None
        self._last_update_time = 0
        self._debounce_interval = 2.0  # 2 second debounce interval to reduce flickering

        self._ensure_ui_assets()
        self._start_http_server()
        self._log("SYS: UI bridge ready.")

    # ------------------------------------------------------------------
    # Compatibility API used by JarvisLive
    # ------------------------------------------------------------------
    @property
    def muted(self) -> bool:
        with self._lock:
            return self._muted

    @muted.setter
    def muted(self, value: bool) -> None:
        with self._lock:
            self._muted = bool(value)
        self._log(f"SYS: Microphone {'muted' if value else 'active'}.")

    @property
    def current_file(self) -> str | None:
        with self._lock:
            return self._current_file

    @current_file.setter
    def current_file(self, value: str | None) -> None:
        with self._lock:
            self._current_file = value

    @property
    def on_text_command(self):
        return self._on_text_command

    @on_text_command.setter
    def on_text_command(self, cb):
        self._on_text_command = cb

    def set_state(self, state: str):
        perf_flags = get_performance_flags()
        metrics = get_metrics_collector()

        with self._lock:
            old_state = self._state
            self._state = state
            self._state_dirty = True

        if perf_flags.is_enabled("debounce_ui_updates"):
            metrics.start_operation("ui_state_change")
            metrics.end_operation(
                "ui_state_change", {"old_state": old_state, "new_state": state, "dirty": True}
            )

        self._log(f"SYS: State changed to {state}.")

    def write_log(self, text: str):
        self._log(text)

    def wait_for_api_key(self):
        api_key = str(self._config.get_api_key("gemini") or "").strip()
        if api_key:
            return

        api_file = BASE_DIR / "config" / "api_keys.json"
        if api_file.exists():
            try:
                data = json.loads(api_file.read_text(encoding="utf-8"))
                if str(data.get("gemini_api_key", "")).strip():
                    return
            except Exception:
                pass

        logger.warning(
            "No Gemini API key found. The UI will start, but live voice mode may fail until a key is configured."
        )

    def start_speaking(self):
        self.set_state("SPEAKING")

    def stop_speaking(self):
        if not self.muted:
            self.set_state("LISTENING")

    def protocol(self, *_args, **_kwargs):
        """Compatibility shim for the old Tk-style root API."""
        return None

    def mainloop(self):
        if os.environ.get("JARVIS_NO_QT"):
            logger.info("Running in server-only mode (Qt disabled)")
            try:
                while not self._shutdown_event.wait(0.25):
                    pass
            except KeyboardInterrupt:
                pass
            finally:
                self.shutdown()
            return

        if QT_WEBENGINE_AVAILABLE:
            self._run_qt_window()
            return

        if self._server_url:
            webbrowser.open(self._server_url, new=1, autoraise=True)
        logger.warning("Qt WebEngine is not available. Falling back to the system browser.")
        try:
            while not self._shutdown_event.wait(0.25):
                pass
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()

    def shutdown(self):
        if self._shutdown_event.is_set():
            return

        self._shutdown_event.set()

        with contextlib.suppress(Exception):
            if self._server is not None:
                self._server.shutdown()
                self._server.server_close()
        self._server = None

        with contextlib.suppress(Exception):
            if self._app is not None:
                app = QApplication.instance() if QApplication else None
                if app is not None:
                    app.quit()

    # ------------------------------------------------------------------
    # UI state endpoints
    # ------------------------------------------------------------------
    def _log(self, text: str) -> None:
        entry = {
            "timestamp": time.time(),
            "text": str(text).strip(),
        }
        with self._lock:
            self._logs.append(entry)

    def _current_state(self) -> Dict[str, Any]:
        perf_flags = get_performance_flags()
        metrics = get_metrics_collector()

        with self._lock:
            state = self._state
            muted = self._muted
            current_file = self._current_file
        voice_first = bool(self._config.get("ui.voice_first", True))

        session = self._session_manager.get_current_session()
        recent_sessions = self._session_manager.get_recent_sessions(limit=16)

        current_state_dict = {
            "state": state,
            "muted": muted,
            "speaking": state == "SPEAKING",
            "current_file": current_file,
            "voice_focus": voice_first,
            "default_view": self._config.get("ui.default_view", "voice"),
            "logs": list(self._logs)[-80:],
            "session": session,
            "recent_sessions": recent_sessions,
        }

        # Debouncing logic
        if perf_flags.is_enabled("debounce_ui_updates"):
            import hashlib
            import json
            import time

            # Calculate hash of current state
            state_str = json.dumps(current_state_dict, sort_keys=True)
            state_hash = hashlib.md5(state_str.encode()).hexdigest()
            current_time = time.time()

            # Check if state has changed and debounce interval has passed
            if state_hash == self._last_state_hash:
                # State hasn't changed, skip update
                metrics.start_operation("ui_state_skipped")
                metrics.end_operation("ui_state_skipped", {"reason": "unchanged"})
                return current_state_dict

            if current_time - self._last_update_time < self._debounce_interval:
                # Debounce interval hasn't passed, skip update
                metrics.start_operation("ui_state_skipped")
                metrics.end_operation("ui_state_skipped", {"reason": "debounce"})
                return current_state_dict

            # Update state hash and timestamp
            self._last_state_hash = state_hash
            self._last_update_time = current_time
            self._state_dirty = False

            metrics.start_operation("ui_state_update")
            metrics.end_operation("ui_state_update", {"hash": state_hash[:16]})

        return current_state_dict

    def _resource_snapshot(self) -> Dict[str, Any]:
        cpu = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()
        disk_root = Path("C:\\") if Path("C:\\").exists() else Path("/")
        disk = psutil.disk_usage(str(disk_root))
        proc = psutil.Process()

        perf_monitor = get_performance_monitor()
        perf_tracker = get_performance_tracker()
        perf_summary = perf_tracker.get_performance_summary()

        try:
            recent_resource_stats = perf_monitor.get_resource_stats(minutes=15)
        except Exception as exc:
            recent_resource_stats = {"error": str(exc)}

        return {
            "cpu_percent": round(cpu, 1),
            "memory_percent": round(memory.percent, 1),
            "memory_mb": round(memory.used / (1024 * 1024), 1),
            "disk_percent": round(disk.percent, 1),
            "threads": proc.num_threads(),
            "processes": len(psutil.pids()),
            "uptime_seconds": int(time.time() - psutil.boot_time()),
            "performance": perf_summary,
            "resource_trend": recent_resource_stats,
        }

    def _settings_payload(self) -> Dict[str, Any]:
        return {
            "ui": {
                "default_view": self._config.get("ui.default_view", "home"),
                "voice_first": bool(self._config.get("ui.voice_first", True)),
            },
            "calendar": {
                "enabled": bool(self._config.get("calendar.enabled", True)),
                "credentials_path": str(
                    self._config.get(
                        "calendar.credentials_path",
                        str(project_path("config", "gmail_credentials.json")),
                    )
                ),
                "token_path": str(
                    self._config.get(
                        "calendar.token_path",
                        str(project_path("config", "calendar_token.json")),
                    )
                ),
            },
            "model_router": {
                "preferred_profile": str(
                    self._config.get("model_router.preferred_profile", "fast")
                ),
                "model_scope": str(self._config.get("model_router.model_scope", "linked")),
                "cost_mode": str(self._config.get("model_router.cost_mode", "balanced")),
            },
        }

    def _setup_payload(self) -> Dict[str, Any]:
        api_file = BASE_DIR / "config" / "api_keys.json"
        example_file = BASE_DIR / "config" / "api_keys.example.json"
        keys: Dict[str, Any] = {}
        if api_file.exists():
            with contextlib.suppress(Exception):
                keys = json.loads(api_file.read_text(encoding="utf-8"))

        return {
            "configured": bool(str(self._config.get_api_key("gemini") or "").strip()),
            "api_keys_path": str(api_file),
            "example_path": str(example_file),
            "has_gemini_key": bool(str(keys.get("gemini_api_key", "")).strip()),
            "has_openai_key": bool(str(keys.get("openai_api_key", "")).strip()),
            "ollama_base_url": str(
                keys.get("ollama_base_url")
                or self._config.get("ollama.base_url", "http://localhost:11434")
            ),
            "settings": self._settings_payload(),
        }

    def _models_payload(self) -> Dict[str, Any]:
        try:
            from core.model_registry import get_model_registry

            registry = get_model_registry()
            registry.reload()
            models = [self._model_profile_payload(model) for model in registry.models.values()]
        except Exception as exc:
            logger.debug("Could not load model registry: %s", exc)
            models = []

        linked = [model for model in models if model["linked"]]
        configured_scope = str(self._config.get("model_router.model_scope", "linked"))
        visible = models if configured_scope == "all" else linked
        return {
            "scope": configured_scope,
            "preferred_profile": str(self._config.get("model_router.preferred_profile", "fast")),
            "models": visible,
            "all_models": models,
            "linked_models": linked,
        }

    def _model_profile_payload(self, model: Any) -> Dict[str, Any]:
        provider = str(getattr(model, "provider", ""))
        linked = bool(getattr(model, "enabled", False))
        if provider == "gemini":
            linked = linked and bool(str(self._config.get_api_key("gemini") or "").strip())
        elif provider == "ollama":
            linked = linked or bool(self._config.get("ollama.enabled", False))
        elif provider == "openai":
            linked = linked and bool(str(self._config.get_api_key("openai") or "").strip())

        return {
            "name": str(getattr(model, "name", "")),
            "model_id": str(getattr(model, "model_id", "")),
            "provider": provider,
            "capabilities": list(getattr(model, "capabilities", ()) or ()),
            "context_window": int(getattr(model, "context_window", 0) or 0),
            "cost_tier": str(getattr(model, "cost_tier", "")),
            "latency_tier": str(getattr(model, "latency_tier", "")),
            "enabled": bool(getattr(model, "enabled", False)),
            "linked": linked,
        }

    def _memory_payload(self) -> Dict[str, Any]:
        try:
            from memory.memory_manager import DEFAULT_MEMORY_CATEGORIES, MEMORY_PATH, load_memory

            memory = load_memory()
            entries: list[Dict[str, Any]] = []
            for category in DEFAULT_MEMORY_CATEGORIES:
                items = memory.get(category, {})
                if not isinstance(items, dict):
                    continue
                for key, entry in items.items():
                    if isinstance(entry, dict):
                        row = dict(entry)
                        value = row.pop("value", "")
                    else:
                        row = {}
                        value = entry
                    entries.append(
                        {
                            "id": f"{category}:{key}",
                            "category": category,
                            "key": key,
                            "value": value,
                            "metadata": row,
                            "updated": row.get("updated"),
                            "created": row.get("created"),
                            "tags": row.get("tags", []),
                        }
                    )
            entries.sort(key=lambda item: str(item.get("updated") or ""), reverse=True)
            return {
                "categories": list(DEFAULT_MEMORY_CATEGORIES),
                "entries": entries,
                "raw": memory,
                "path": str(MEMORY_PATH),
            }
        except Exception as exc:
            logger.error("Could not load memory payload: %s", exc)
            return {"categories": [], "entries": [], "raw": {}, "error": str(exc)}

    def _save_setup_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        from memory.config_manager import save_setup_config

        model_router = payload.get("model_router", {}) if isinstance(payload, dict) else {}
        save_setup_config(
            gemini_api_key=str(payload.get("gemini_api_key", "")).strip(),
            openai_api_key=str(payload.get("openai_api_key", "")).strip(),
            ollama_base_url=str(payload.get("ollama_base_url", "")).strip(),
            preferred_model=str(model_router.get("preferred_profile") or "fast"),
            model_scope=str(model_router.get("model_scope") or "linked"),
        )
        if payload.get("ollama_enabled") is not None or payload.get("ollama_model"):
            get_config().update_local_settings(
                {
                    "ollama": {
                        "enabled": bool(payload.get("ollama_enabled")),
                        "model": str(payload.get("ollama_model") or "llama3.1"),
                        "base_url": str(
                            payload.get("ollama_base_url") or "http://localhost:11434"
                        ),
                    }
                }
            )
        with contextlib.suppress(Exception):
            from core.model_registry import get_model_registry

            get_model_registry().reload()
        return {"status": "saved", "setup": self._setup_payload(), "models": self._models_payload()}

    def _save_memory_entry(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        from memory.memory_manager import DEFAULT_MEMORY_CATEGORIES, remember_structured

        category = str(payload.get("category", "notes")).strip()
        key = str(payload.get("key", "")).strip()
        value = str(payload.get("value", "")).strip()
        tags_raw = payload.get("tags", [])
        tags = tags_raw if isinstance(tags_raw, list) else str(tags_raw).split(",")
        if category not in DEFAULT_MEMORY_CATEGORIES:
            return {"error": "unknown category", "memory": self._memory_payload()}
        if not key or not value:
            return {"error": "key and value are required", "memory": self._memory_payload()}
        remember_structured(category, key, value, tags=[str(tag).strip() for tag in tags if str(tag).strip()])
        return {"status": "saved", "memory": self._memory_payload()}

    def _forget_memory_entry(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        from memory.memory_manager import forget

        category = str(payload.get("category", "notes")).strip()
        key = str(payload.get("key", "")).strip()
        if not key:
            return {"error": "key is required", "memory": self._memory_payload()}
        return {"status": forget(key, category), "memory": self._memory_payload()}

    def _calendar_payload(self) -> Dict[str, Any]:
        calendar_cfg = self._settings_payload()["calendar"]
        credentials = Path(calendar_cfg["credentials_path"])
        token = Path(calendar_cfg["token_path"])
        if not credentials.is_absolute():
            credentials = BASE_DIR / credentials
        if not token.is_absolute():
            token = BASE_DIR / token

        return {
            "enabled": calendar_cfg["enabled"],
            "configured": credentials.exists(),
            "authenticated": token.exists(),
            "credentials_path": str(credentials),
            "token_path": str(token),
        }

    @staticmethod
    def _size_label(size: int) -> str:
        units = ("B", "KB", "MB", "GB")
        value = float(max(0, size))
        unit = units[0]
        for unit in units:
            if value < 1024 or unit == units[-1]:
                break
            value /= 1024
        precision = 0 if unit == "B" else 1
        return f"{value:.{precision}f} {unit}"

    @staticmethod
    def _safe_upload_name(name: str) -> str:
        candidate = Path(str(name or "upload")).name
        candidate = re.sub(r"[^A-Za-z0-9._ -]+", "_", candidate).strip(" .")
        return candidate or f"upload-{uuid4().hex[:8]}"

    @staticmethod
    def _document_type(path: Path) -> str:
        suffix = path.suffix.lstrip(".").upper()
        return suffix or "FILE"

    def _load_document_records(self) -> list[Dict[str, Any]]:
        if not DOCUMENT_INDEX_PATH.exists():
            return []
        try:
            data = json.loads(DOCUMENT_INDEX_PATH.read_text(encoding="utf-8"))
            records = data.get("files", [])
            return records if isinstance(records, list) else []
        except Exception as exc:
            logger.debug("Could not read UI document index: %s", exc)
            return []

    def _save_document_records(self, records: list[Dict[str, Any]]) -> None:
        DOCUMENT_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        DOCUMENT_INDEX_PATH.write_text(
            json.dumps({"files": records[:200], "updated_at": datetime.now().isoformat()}, indent=2),
            encoding="utf-8",
        )

    def _documents_payload(self) -> Dict[str, Any]:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        records = self._load_document_records()
        existing: list[Dict[str, Any]] = []
        for record in records:
            path = Path(str(record.get("path", "")))
            if path.exists():
                existing.append(record)
        return {
            "files": existing,
            "upload_dir": str(UPLOAD_DIR),
        }

    def _devices_payload(self) -> Dict[str, Any]:
        proc = psutil.Process()
        return {
            "current": {
                "id": platform.node() or "local",
                "name": platform.node() or "Local device",
                "os": platform.platform(),
                "python": platform.python_version(),
                "pid": os.getpid(),
                "process": proc.name(),
                "started_at": datetime.fromtimestamp(proc.create_time()).isoformat(),
            },
            "items": [
                {
                    "id": platform.node() or "local",
                    "name": platform.node() or "Local device",
                    "status": "online",
                    "kind": "desktop",
                    "last_seen": datetime.now().isoformat(),
                }
            ],
        }

    def _action_history_payload(self) -> Dict[str, Any]:
        try:
            from core.action_history import get_action_history

            history = get_action_history()
            records = [record.to_dict() for record in history.get_history(limit=40)]
            undoable = [record.to_dict() for record in history.get_undoable_actions()[-20:]][::-1]
            return {
                "records": records,
                "undoable": undoable,
                "stats": history.get_stats(),
            }
        except Exception as exc:
            logger.debug("Could not load action history: %s", exc)
            return {"records": [], "undoable": [], "stats": {}, "error": str(exc)}

    def _approvals_payload(self) -> Dict[str, Any]:
        try:
            from core.approval_flow import get_approval_flow

            flow = get_approval_flow()
            return {
                "permission_level": flow.get_permission_level(),
                "pending": [request.to_dict() for request in flow.get_pending_requests()],
            }
        except Exception as exc:
            logger.debug("Could not load approvals: %s", exc)
            return {"permission_level": "normal", "pending": [], "error": str(exc)}

    def _permissions_payload(self) -> Dict[str, Any]:
        try:
            from core.permission_profiles import get_all_tool_metadata, get_disabled_actions

            tools = []
            for metadata in get_all_tool_metadata().values():
                tools.append(
                    {
                        "name": metadata.name,
                        "description": metadata.description,
                        "risk_level": metadata.risk_level,
                        "requires_confirmation": metadata.requires_confirmation,
                        "requires_permission": metadata.requires_permission,
                        "reversible": metadata.reversible,
                        "tags": sorted(metadata.tags),
                        "enabled": metadata.enabled
                        and metadata.name.lower() not in get_disabled_actions(),
                    }
                )
            tools.sort(key=lambda item: (item["risk_level"], item["name"]))
            return {"tools": tools, "disabled_actions": sorted(get_disabled_actions())}
        except Exception as exc:
            logger.debug("Could not load permissions: %s", exc)
            return {"tools": [], "disabled_actions": [], "error": str(exc)}

    def _reliability_payload(self) -> Dict[str, Any]:
        try:
            from core.reliability import build_reliability_report

            return build_reliability_report()
        except Exception as exc:
            logger.debug("Could not load reliability report: %s", exc)
            return {
                "status": "blocked",
                "counts": {"ok": 0, "degraded": 0, "blocked": 1},
                "checks": [],
                "recommendations": [str(exc)],
                "error": str(exc),
            }

    def _quick_actions_payload(self) -> Dict[str, Any]:
        return {
            "items": [
                {"id": "new_session", "label": "Neue Sitzung", "command": "/session new"},
                {"id": "healthcheck", "label": "Healthcheck", "command": "run healthcheck"},
                {"id": "open_uploads", "label": "Uploads pruefen", "command": "show uploaded documents"},
                {"id": "summarize_day", "label": "Tag zusammenfassen", "command": "summarize today"},
            ]
        }

    def _analyze_upload(self, path: Path) -> str | None:
        if path.suffix.lower() not in {".txt", ".md", ".csv", ".json", ".py", ".ts", ".tsx"}:
            return None
        try:
            text = path.read_text(encoding="utf-8", errors="ignore").strip()
        except Exception:
            return None
        if not text:
            return "Leere Datei"
        first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
        return first_line[:240] if first_line else f"{len(text)} Zeichen"

    def _index_uploads(self) -> tuple[bool, str | None]:
        try:
            from core.semantic_search import SemanticSearch

            search = SemanticSearch(index_path=project_path("data", "vector_db"))
            search.index_directory(UPLOAD_DIR)
            return True, None
        except Exception as exc:
            logger.debug("Document indexing unavailable: %s", exc)
            return False, str(exc)

    def _save_uploaded_files(
        self,
        fields: list[Any],
        *,
        analyze: bool,
        should_index: bool,
    ) -> Dict[str, Any]:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        records = self._load_document_records()
        errors: list[Dict[str, str]] = []
        saved: list[Dict[str, Any]] = []
        now = datetime.now().isoformat()

        for field in fields:
            filename = self._safe_upload_name(getattr(field, "filename", "") or "")
            destination = UPLOAD_DIR / filename
            if destination.exists():
                destination = UPLOAD_DIR / f"{destination.stem}-{uuid4().hex[:6]}{destination.suffix}"

            try:
                with destination.open("wb") as handle:
                    shutil.copyfileobj(field.file, handle)
                size = destination.stat().st_size
                record = {
                    "id": uuid4().hex,
                    "name": destination.name,
                    "type": self._document_type(destination),
                    "size": size,
                    "size_label": self._size_label(size),
                    "uploaded_at": now,
                    "path": str(destination),
                    "analysis": self._analyze_upload(destination) if analyze else None,
                    "indexed": False,
                    "status": "uploaded",
                    "error": None,
                }
                saved.append(record)
                records.insert(0, record)
                self._log(f"UPLOAD: {destination.name}")
            except Exception as exc:
                errors.append({"name": filename, "error": str(exc)})

        indexed = False
        index_error: str | None = None
        if should_index and saved:
            indexed, index_error = self._index_uploads()
            for record in saved:
                record["indexed"] = indexed
                record["status"] = "indexed" if indexed else "uploaded"
                if index_error and not indexed:
                    record["error"] = index_error
            for record in records:
                if any(record.get("id") == item.get("id") for item in saved):
                    record["indexed"] = indexed
                    record["status"] = "indexed" if indexed else "uploaded"
                    if index_error and not indexed:
                        record["error"] = index_error

        self._save_document_records(records)
        return {
            "status": "uploaded" if saved else "empty",
            "files": self._documents_payload()["files"],
            "errors": errors,
            "indexed": indexed,
        }

    def _resume_payload(self) -> Dict[str, Any]:
        current = self._session_manager.get_current_session()
        recent = self._session_manager.get_recent_sessions(limit=8)
        session = current or (recent[0] if recent else None)
        messages = session.get("messages", []) if isinstance(session, dict) else []
        last_message = messages[-1] if messages else None
        recent_files = [
            {
                "id": record.get("id", ""),
                "title": record.get("name", "Datei"),
                "subtitle": record.get("analysis") or record.get("size_label"),
                "status": "indexiert" if record.get("indexed") else "bereit",
                "source": "documents",
            }
            for record in self._documents_payload()["files"][:5]
        ]

        summary = ""
        if isinstance(session, dict):
            summary = str(session.get("summary") or session.get("preview") or "").strip()
            if not summary and last_message:
                summary = str(last_message.get("content", ""))[:240]

        return {
            "last_activity": {
                "id": str(last_message.get("id", "last")) if last_message else "session",
                "title": str(last_message.get("content", ""))[:90] if last_message else (session or {}).get("title", ""),
                "subtitle": (session or {}).get("title", ""),
                "time": str(last_message.get("timestamp", "")) if last_message else (session or {}).get("updated_at"),
                "source": "session",
            }
            if session
            else None,
            "open_ends": self._open_end_items(session),
            "recent_files": recent_files,
            "summary": summary,
            "session": session,
        }

    def _open_end_items(self, session: Dict[str, Any] | None) -> list[Dict[str, Any]]:
        if not session:
            return []
        messages = session.get("messages", []) if isinstance(session, dict) else []
        items: list[Dict[str, Any]] = []
        markers = ("?", "todo", "offen", "next", "näch", "naech", "weiter", "fix", "implement")
        for message in reversed(messages[-20:]):
            content = str(message.get("content", "")).strip()
            if content and any(marker in content.lower() for marker in markers):
                items.append(
                    {
                        "id": str(message.get("id", uuid4().hex)),
                        "title": content[:90],
                        "subtitle": str(message.get("role", "session")),
                        "time": str(message.get("timestamp", "")),
                        "source": "session",
                    }
                )
            if len(items) >= 4:
                break
        return items

    def _cockpit_payload(self) -> Dict[str, Any]:
        calendar_status = self._calendar_payload()
        resume = self._resume_payload()
        state = self._current_state()
        logs = state.get("logs", [])[-8:]
        recent_activities = [
            {
                "id": f"log-{idx}",
                "title": str(entry.get("text", ""))[:90],
                "time": datetime.fromtimestamp(float(entry.get("timestamp", time.time()))).strftime("%H:%M"),
                "source": "log",
            }
            for idx, entry in enumerate(reversed(logs))
            if entry.get("text")
        ]
        tasks = []
        performance = self._resource_snapshot().get("performance", {})
        active_tasks = performance.get("active_tasks")
        if active_tasks:
            tasks.append(
                {
                    "id": "active-tasks",
                    "title": f"{active_tasks} aktive Aufgabe(n)",
                    "subtitle": str(performance.get("current_activity") or ""),
                    "status": "aktiv",
                    "source": "performance",
                }
            )

        next_best_step = None
        if resume["open_ends"]:
            first = resume["open_ends"][0]
            next_best_step = {
                "title": first["title"],
                "reason": "Aus der letzten offenen Sitzung",
                "action": "Resume",
            }
        elif resume["recent_files"]:
            first = resume["recent_files"][0]
            next_best_step = {
                "title": f"{first['title']} pruefen",
                "reason": "Zuletzt importierte Datei",
                "action": "Dokumente",
            }
        else:
            next_best_step = {
                "title": "Neuen Fokus setzen",
                "reason": "Keine offenen lokalen Daten gefunden",
                "action": "Start",
            }

        return {
            "calendar": {
                "items": [],
                "status": calendar_status,
            },
            "weather": {
                "summary": "Keine Wetterdaten",
                "temperature": None,
                "condition": None,
                "location": None,
            },
            "mail": {
                "open_count": 0,
                "items": [],
            },
            "reminders": [],
            "tasks": tasks,
            "recent_activities": recent_activities,
            "next_best_step": next_best_step,
        }

    def _dashboard_payload(self) -> Dict[str, Any]:
        return {
            "state": self._current_state(),
            "resources": self._resource_snapshot(),
            "settings": self._settings_payload(),
            "calendar": self._calendar_payload(),
            "current_session": self._session_manager.get_current_session(),
            "recent_sessions": self._session_manager.get_recent_sessions(limit=12),
            "cockpit": self._cockpit_payload(),
            "resume": self._resume_payload(),
            "documents": self._documents_payload(),
            "setup": self._setup_payload(),
            "models": self._models_payload(),
            "memory": self._memory_payload(),
            "devices": self._devices_payload(),
            "action_history": self._action_history_payload(),
            "approvals": self._approvals_payload(),
            "permissions": self._permissions_payload(),
            "reliability": self._reliability_payload(),
            "quick_actions": self._quick_actions_payload(),
        }

    def _recent_chats_payload(self) -> Dict[str, Any]:
        return {
            "sessions": self._session_manager.get_recent_sessions(limit=30),
            "current_session_id": (self._session_manager.get_current_session() or {}).get("id"),
        }

    # ------------------------------------------------------------------
    # HTTP server
    # ------------------------------------------------------------------
    def _ensure_ui_assets(self) -> None:
        index_html = UI_DIST_DIR / "index.html"
        if index_html.exists():
            return

        if not UI_DIR.exists():
            raise RuntimeError("UI/ directory is missing")

        logger.info("Building React UI bundle...")
        if not VITE_BIN.exists():
            raise RuntimeError("UI build toolchain is missing. Run 'npm install' in UI/ first.")

        node_executable = _find_node_executable()
        if not node_executable:
            raise RuntimeError(
                "Node.js is not available. Install Node.js or add it to PATH, "
                "then run 'npm install' in UI/."
            )

        result = subprocess.run(
            [node_executable, str(VITE_BIN), "build", "--configLoader", "native"],
            cwd=str(UI_DIR),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.error(result.stdout)
            logger.error(result.stderr)
            raise RuntimeError("UI build failed. Run 'npm install' and 'npm run build' in UI/.")

    def _start_http_server(self) -> None:
        ui = self
        perf_flags = get_performance_flags()

        class Handler(BaseHTTPRequestHandler):
            server_version = "JarvisUI/1.0"

            def log_message(self, format, *args):  # noqa: A003
                logger.debug("[UI] " + format, *args)

            def _read_json(self) -> Dict[str, Any]:
                length = int(self.headers.get("Content-Length", "0") or "0")
                if length <= 0:
                    return {}
                raw = self.rfile.read(length).decode("utf-8")
                if not raw.strip():
                    return {}
                return json.loads(raw)

            def _read_multipart(self) -> tuple[list[Any], Dict[str, str]]:
                content_type = self.headers.get("Content-Type", "")
                boundary_match = re.search(r'boundary=(?:"([^"]+)"|([^;]+))', content_type)
                if not boundary_match:
                    raise ValueError("missing multipart boundary")

                boundary = (boundary_match.group(1) or boundary_match.group(2)).encode("utf-8")
                length = int(self.headers.get("Content-Length", "0") or "0")
                raw = self.rfile.read(length)
                fields: list[Any] = []
                values: Dict[str, str] = {}

                for part in raw.split(b"--" + boundary):
                    part = part.strip(b"\r\n")
                    if not part or part == b"--":
                        continue
                    if part.endswith(b"--"):
                        part = part[:-2].strip(b"\r\n")
                    header_blob, separator, body = part.partition(b"\r\n\r\n")
                    if not separator:
                        continue

                    headers = header_blob.decode("utf-8", errors="ignore")
                    disposition = next(
                        (
                            line
                            for line in headers.splitlines()
                            if line.lower().startswith("content-disposition:")
                        ),
                        "",
                    )
                    name_match = re.search(r'name="([^"]+)"', disposition)
                    filename_match = re.search(r'filename="([^"]*)"', disposition)
                    if body.endswith(b"\r\n"):
                        body = body[:-2]

                    if filename_match:
                        fields.append(_MultipartUpload(filename_match.group(1), body))
                    elif name_match:
                        values[name_match.group(1)] = body.decode("utf-8", errors="ignore")
                return fields, values

            def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
                blob = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(blob)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(blob)

            def _send_bytes(self, status: int, blob: bytes, content_type: str) -> None:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(blob)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(blob)

            def do_GET(self):  # noqa: N802
                if perf_flags.is_enabled("async_ui_server"):
                    # Run handler in event loop for async I/O
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(ui._handle_get_async(self))
                        loop.close()
                    except Exception as e:
                        logger.error(f"Async GET handler error: {e}")
                        # Fallback to synchronous
                        ui._handle_get(self)
                else:
                    ui._handle_get(self)

            def do_POST(self):  # noqa: N802
                if perf_flags.is_enabled("async_ui_server"):
                    # Run handler in event loop for async I/O
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(ui._handle_post_async(self))
                        loop.close()
                    except Exception as e:
                        logger.error(f"Async POST handler error: {e}")
                        # Fallback to synchronous
                        ui._handle_post(self)
                else:
                    ui._handle_post(self)

        self._server = ThreadingHTTPServer(("127.0.0.1", 8000), Handler)
        self._server.daemon_threads = True
        self._server_thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
            name="JarvisUIHttpServer",
        )
        self._server_thread.start()
        port = self._server.server_address[1]
        self._server_url = f"http://127.0.0.1:{port}"
        logger.info("UI server listening on %s", self._server_url)

    def _handle_get(self, request: BaseHTTPRequestHandler) -> None:
        path = urlparse(request.path).path

        if path == "/api/dashboard":
            return request._send_json(200, self._dashboard_payload())  # type: ignore[attr-defined]
        if path == "/api/cockpit":
            return request._send_json(200, self._cockpit_payload())  # type: ignore[attr-defined]
        if path == "/api/session/resume":
            return request._send_json(200, self._resume_payload())  # type: ignore[attr-defined]
        if path == "/api/documents":
            return request._send_json(200, self._documents_payload())  # type: ignore[attr-defined]
        if path == "/api/setup":
            return request._send_json(200, self._setup_payload())  # type: ignore[attr-defined]
        if path == "/api/models":
            return request._send_json(200, self._models_payload())  # type: ignore[attr-defined]
        if path == "/api/memory":
            return request._send_json(200, self._memory_payload())  # type: ignore[attr-defined]
        if path == "/api/memory/export":
            return request._send_json(200, self._memory_payload())  # type: ignore[attr-defined]
        if path == "/api/actions/history":
            return request._send_json(200, self._action_history_payload())  # type: ignore[attr-defined]
        if path == "/api/approvals":
            return request._send_json(200, self._approvals_payload())  # type: ignore[attr-defined]
        if path == "/api/permissions":
            return request._send_json(200, self._permissions_payload())  # type: ignore[attr-defined]
        if path == "/api/reliability":
            return request._send_json(200, self._reliability_payload())  # type: ignore[attr-defined]
        if path == "/api/devices":
            return request._send_json(200, self._devices_payload())  # type: ignore[attr-defined]
        if path == "/api/state":
            return request._send_json(200, self._current_state())  # type: ignore[attr-defined]
        if path == "/api/resources":
            return request._send_json(200, self._resource_snapshot())  # type: ignore[attr-defined]
        if path == "/api/chats":
            return request._send_json(200, self._recent_chats_payload())  # type: ignore[attr-defined]
        if path.startswith("/api/chats/"):
            session_id = path.split("/api/chats/", 1)[1].strip("/")
            session = self._session_manager.get_session(session_id)
            if not session:
                return request._send_json(404, {"error": "chat not found"})  # type: ignore[attr-defined]
            return request._send_json(200, {"session": session})  # type: ignore[attr-defined]
        if path == "/api/settings":
            return request._send_json(200, self._settings_payload())  # type: ignore[attr-defined]
        if path == "/api/calendar/status":
            return request._send_json(200, self._calendar_payload())  # type: ignore[attr-defined]
        if path == "/api/logs":
            return request._send_json(200, {"logs": list(self._logs)[-150:]})  # type: ignore[attr-defined]

        return self._serve_static(request, path)

    async def _handle_get_async(self, request: BaseHTTPRequestHandler) -> None:
        """Handle GET requests asynchronously."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._handle_get, request)

    def _handle_post(self, request: BaseHTTPRequestHandler) -> None:
        path = urlparse(request.path).path

        if path == "/api/documents/upload":
            try:
                fields, values = request._read_multipart()  # type: ignore[attr-defined]
            except Exception as exc:
                return request._send_json(400, {"error": f"invalid upload: {exc}"})  # type: ignore[attr-defined]

            if not fields:
                return request._send_json(400, {"error": "missing files"})  # type: ignore[attr-defined]

            analyze = str(values.get("analyze", "true")).lower() in {"1", "true", "yes", "on"}
            should_index = str(values.get("index", "false")).lower() in {"1", "true", "yes", "on"}
            return request._send_json(200, self._save_uploaded_files(fields, analyze=analyze, should_index=should_index))  # type: ignore[attr-defined]

        try:
            payload = request._read_json()  # type: ignore[attr-defined]
        except Exception as exc:
            return request._send_json(400, {"error": f"invalid json: {exc}"})  # type: ignore[attr-defined]

        if path == "/api/command":
            text = str(payload.get("text", "")).strip()
            if not text:
                return request._send_json(400, {"error": "missing text"})  # type: ignore[attr-defined]

            if callable(self._on_text_command):
                threading.Thread(
                    target=self._on_text_command,
                    args=(text,),
                    daemon=True,
                    name="JarvisTextCommand",
                ).start()
            return request._send_json(202, {"status": "queued"})  # type: ignore[attr-defined]

        if path == "/api/mute":
            muted = bool(payload.get("muted", False))
            self.muted = muted
            return request._send_json(200, {"muted": self.muted})  # type: ignore[attr-defined]

        if path == "/api/session/new":
            session_id = self._session_manager.start_session(force=True)
            return request._send_json(
                200,
                {
                    "session_id": session_id,
                    "current_session": self._session_manager.get_current_session(),
                },
            )  # type: ignore[attr-defined]

        if path == "/api/session/end":
            session_id = self._session_manager.finalize_session(
                summary=str(payload.get("summary", "")).strip() or None
            )
            return request._send_json(
                200,
                {
                    "session_id": session_id,
                    "current_session": self._session_manager.get_current_session(),
                },
            )  # type: ignore[attr-defined]

        if path == "/api/settings":
            updates = payload if isinstance(payload, dict) else {}
            changed = get_config().update_local_settings(updates)

            if "calendar" in updates:
                with contextlib.suppress(Exception):
                    from actions.calendar_manager import reset_calendar_manager

                    reset_calendar_manager()
            if "model_router" in updates or "ollama" in updates:
                with contextlib.suppress(Exception):
                    from core.model_registry import get_model_registry

                    get_model_registry().reload()

            return request._send_json(
                200,
                {
                    "status": "saved",
                    "settings": self._settings_payload(),
                    "models": self._models_payload(),
                    "raw": changed,
                },
            )  # type: ignore[attr-defined]

        if path == "/api/setup":
            return request._send_json(200, self._save_setup_payload(payload))  # type: ignore[attr-defined]

        if path == "/api/memory/upsert":
            result = self._save_memory_entry(payload)
            status = 400 if "error" in result else 200
            return request._send_json(status, result)  # type: ignore[attr-defined]

        if path == "/api/memory/forget":
            result = self._forget_memory_entry(payload)
            status = 400 if "error" in result else 200
            return request._send_json(status, result)  # type: ignore[attr-defined]

        if path == "/api/approvals/approve":
            from core.approval_flow import get_approval_flow

            get_approval_flow().approve_request(
                str(payload.get("tool_name", "")),
                str(payload.get("action", "")),
            )
            return request._send_json(200, self._approvals_payload())  # type: ignore[attr-defined]

        if path == "/api/approvals/deny":
            from core.approval_flow import get_approval_flow

            get_approval_flow().deny_request(
                str(payload.get("tool_name", "")),
                str(payload.get("action", "")),
            )
            return request._send_json(200, self._approvals_payload())  # type: ignore[attr-defined]

        if path == "/api/permissions/level":
            from core.approval_flow import get_approval_flow

            level = str(payload.get("level", "normal")).lower()
            if level not in {"safe", "normal", "admin"}:
                return request._send_json(400, {"error": "invalid permission level"})  # type: ignore[attr-defined]
            get_approval_flow().set_permission_level(level)
            return request._send_json(200, self._approvals_payload())  # type: ignore[attr-defined]

        if path == "/api/calendar/connect":
            updates = payload if isinstance(payload, dict) else {}
            if updates:
                get_config().update_local_settings({"calendar": updates})

            with contextlib.suppress(Exception):
                from actions.calendar_manager import reset_calendar_manager

                reset_calendar_manager()

            try:
                from actions.calendar_manager import get_calendar_manager

                manager = get_calendar_manager()
                if not manager.enabled:
                    return request._send_json(
                        200,
                        {
                            "status": "disabled",
                            "message": "Calendar integration is disabled.",
                            "calendar": self._calendar_payload(),
                        },
                    )  # type: ignore[attr-defined]

                if manager.service:
                    return request._send_json(
                        200,
                        {
                            "status": "connected",
                            "message": "Google Calendar is connected.",
                            "calendar": self._calendar_payload(),
                        },
                    )  # type: ignore[attr-defined]

                return request._send_json(
                    200,
                    {
                        "status": "pending",
                        "message": "Calendar setup is pending. Check credentials/token paths.",
                        "calendar": self._calendar_payload(),
                    },
                )  # type: ignore[attr-defined]
            except Exception as exc:
                return request._send_json(
                    500,
                    {
                        "status": "error",
                        "message": str(exc),
                        "calendar": self._calendar_payload(),
                    },
                )  # type: ignore[attr-defined]

        return request._send_json(404, {"error": "unknown endpoint"})  # type: ignore[attr-defined]

    async def _handle_post_async(self, request: BaseHTTPRequestHandler) -> None:
        """Handle POST requests asynchronously."""
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._handle_post, request)

    def _serve_static(self, request: BaseHTTPRequestHandler, path: str) -> None:
        if path in {"", "/"}:
            candidate = UI_DIST_DIR / "index.html"
        else:
            candidate = (UI_DIST_DIR / unquote(path.lstrip("/"))).resolve()
            try:
                candidate.relative_to(UI_DIST_DIR.resolve())
            except Exception:
                candidate = UI_DIST_DIR / "index.html"

        if not candidate.exists() or candidate.is_dir():
            candidate = UI_DIST_DIR / "index.html"

        if not candidate.exists():
            return request._send_json(404, {"error": "frontend not built"})  # type: ignore[attr-defined]

        content_type = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
        data = candidate.read_bytes()
        return request._send_bytes(200, data, content_type)  # type: ignore[attr-defined]

    def _start_vite_dev_server(self) -> None:
        """Start the Vite dev server if not already running."""
        vite_dev_url = "http://localhost:5173"
        
        # Check if already running
        try:
            import requests
            response = requests.get(vite_dev_url, timeout=1)
            if response.status_code == 200:
                self._log("SYS: Vite dev server already running at http://localhost:5173")
                return
        except Exception:
            pass
        
        # Start Vite dev server
        self._log("SYS: Starting Vite dev server...")
        
        if not UI_DIR.exists():
            raise RuntimeError("UI/ directory is missing. Please run 'cd UI && npm run dev' to start the UI.")
        
        if not VITE_BIN.exists():
            raise RuntimeError("UI build toolchain is missing. Run 'npm install' in UI/ first.")
        
        node_executable = _find_node_executable()
        if not node_executable:
            raise RuntimeError(
                "Node.js is not available. Install Node.js or add it to PATH, "
                "then run 'npm install' in UI/."
            )
        
        # Start Vite dev server in background
        self._vite_process = subprocess.Popen(
            [node_executable, str(VITE_BIN), "dev"],
            cwd=str(UI_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for server to start
        import time
        max_wait = 30
        for i in range(max_wait):
            try:
                import requests
                response = requests.get(vite_dev_url, timeout=1)
                if response.status_code == 200:
                    self._log("SYS: Vite dev server started successfully")
                    return
            except Exception:
                time.sleep(1)
        
        raise RuntimeError("Failed to start Vite dev server. Please run 'cd UI && npm run dev' manually.")

    def _run_qt_window(self) -> None:
        """Run the Qt window against the stable built UI by default."""
        if QApplication is None or QWebEngineView is None:
            raise RuntimeError("Qt WebEngine is not available")

        if os.environ.get("JARVIS_UI_DEV"):
            url = "http://localhost:5173"
            self._start_vite_dev_server()
            self._log(f"SYS: Using Vite dev server at {url}")
        else:
            if not self._server_url:
                raise RuntimeError("UI HTTP server did not start")
            url = self._server_url
            self._log(f"SYS: Using built UI at {url}")

        self._window = _JARVISWindow(self, url)

        # Use existing QApplication instance if available (created in main thread)
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
            app.setApplicationName("JARVIS")
        self._app = app

        def show_window(_ok: bool = True) -> None:
            if self._window is None:
                return
            self._window.show()
            self._window.activateWindow()
            self._window.raise_()

        self._window._web.loadFinished.connect(show_window)
        app.processEvents()

        try:
            app.exec()
        finally:
            self.shutdown()
            if self._vite_process:
                self._vite_process.terminate()
                self._vite_process.wait(timeout=5)
