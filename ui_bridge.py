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
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, unquote, urlparse
from uuid import uuid4

from config.config_loader import get_config
from core.logger import get_logger
from core.metrics_collector import get_metrics_collector
from core.paths import project_path, resolve_project_root
from core.platform_hub import get_platform_hub
from core.performance_flags import get_performance_flags
from core.performance_monitor import get_performance_monitor
from core.performance_tracker import get_performance_tracker
from core.session_manager import get_session_manager
from core.voice_conversation import get_voice_conversation_mode

try:
    if (os.environ.get("MICA_NO_QT") or os.environ.get("JARVIS_NO_QT")):
        raise ImportError("Qt disabled by MICA_NO_QT environment variable")
    from PyQt6.QtCore import QEvent, Qt, QUrl
    from PyQt6.QtGui import QColor
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget

    QT_WEBENGINE_AVAILABLE = True
    QT_WEBENGINE_IMPORT_ERROR: Exception | None = None
except Exception as exc:
    QUrl = None  # type: ignore[assignment]
    QEvent = None  # type: ignore[assignment]
    Qt = None  # type: ignore[assignment]
    QColor = None  # type: ignore[assignment]
    QApplication = None  # type: ignore[assignment]
    QLabel = None  # type: ignore[assignment]
    QMainWindow = object  # type: ignore[assignment]
    QVBoxLayout = None  # type: ignore[assignment]
    QWidget = None  # type: ignore[assignment]
    QWebEngineView = None  # type: ignore[assignment]
    QT_WEBENGINE_AVAILABLE = False
    QT_WEBENGINE_IMPORT_ERROR = exc


logger = get_logger(__name__)


_psutil_module: Any | bool | None = None


def _get_psutil():
    """Import psutil only when runtime/device metrics are requested."""
    global _psutil_module
    if _psutil_module is None:
        try:
            import psutil as psutil_module
        except ImportError:
            psutil_module = False
        _psutil_module = psutil_module
    return _psutil_module if _psutil_module is not False else None


BASE_DIR = resolve_project_root()
UI_DIR = project_path("UI")
UI_DIST_DIR = UI_DIR / "dist"
VITE_BIN = UI_DIR / "node_modules" / "vite" / "bin" / "vite.js"
UPLOAD_DIR = project_path("data", "uploads")
DOCUMENT_INDEX_PATH = project_path("data", "ui_documents.json")


def get_qt_webengine_diagnostic() -> str:
    """Return a concise status message for the desktop WebEngine runtime."""
    if QT_WEBENGINE_AVAILABLE:
        return "Qt WebEngine is available."
    if QT_WEBENGINE_IMPORT_ERROR is None:
        return "Qt WebEngine is not available."
    return (
        "Qt WebEngine is not available "
        f"({type(QT_WEBENGINE_IMPORT_ERROR).__name__}: {QT_WEBENGINE_IMPORT_ERROR})."
    )


def get_qt_webengine_recovery_hint() -> str:
    if (os.environ.get("MICA_NO_QT") or os.environ.get("JARVIS_NO_QT")):
        return "Unset MICA_NO_QT to enable the desktop Qt window."
    return (
        "Install the GUI dependency in the active virtual environment with "
        "`python -m pip install -r requirements.txt` or "
        "`python -m pip install PyQt6-WebEngine==6.11.0`. "
        "For a browser-only UI, set MICA_ALLOW_BROWSER_FALLBACK=1 before starting M.I.C.A."
    )


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


class _MicaMiniHeadWindow(QMainWindow):
    def __init__(self, parent_window: "_MICAWindow"):
        super().__init__()
        self._parent_window = parent_window
        self._drag_offset = None
        self._drag_started = False
        self.setWindowTitle("M.I.C.A Mini")
        self.setFixedSize(118, 118)

        if Qt is not None:
            self.setWindowFlags(
                Qt.WindowType.Tool
                | Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
            )
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.setCursor(Qt.CursorShape.OpenHandCursor)

        if QWidget is None or QVBoxLayout is None or QLabel is None:
            return

        root = QWidget(self)
        root.setObjectName("miniRoot")
        root.setStyleSheet(
            """
            QWidget#miniRoot {
                background: rgba(4, 12, 14, 226);
                border: 2px solid rgba(93, 210, 255, 180);
                border-radius: 55px;
            }
            QLabel#miniFace {
                color: #dff8ff;
                font-size: 34px;
                font-weight: 700;
                letter-spacing: 6px;
                padding-left: 5px;
            }
            QLabel#miniCaption {
                color: rgba(207, 250, 254, 170);
                font-size: 9px;
                letter-spacing: 2px;
            }
            """
        )
        layout = QVBoxLayout(root)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(2)
        face = QLabel("● ●", root)
        face.setObjectName("miniFace")
        face.setAlignment(Qt.AlignmentFlag.AlignCenter if Qt is not None else 0)
        caption = QLabel("M.I.C.A", root)
        caption.setObjectName("miniCaption")
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter if Qt is not None else 0)
        layout.addStretch(1)
        layout.addWidget(face)
        layout.addWidget(caption)
        layout.addStretch(1)
        self.setCentralWidget(root)

    def _event_global_pos(self, event):
        if hasattr(event, "globalPosition"):
            return event.globalPosition().toPoint()
        if hasattr(event, "globalPos"):
            return event.globalPos()
        return None

    def mousePressEvent(self, event):  # noqa: N802
        if Qt is not None and event.button() == Qt.MouseButton.LeftButton:
            global_pos = self._event_global_pos(event)
            if global_pos is not None:
                self._drag_offset = global_pos - self.frameGeometry().topLeft()
                self._drag_started = False
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802
        if self._drag_offset is not None:
            global_pos = self._event_global_pos(event)
            if global_pos is not None:
                self.move(global_pos - self._drag_offset)
                self._drag_started = True
                event.accept()
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802
        if Qt is not None:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        was_dragged = self._drag_started
        self._drag_offset = None
        self._drag_started = False

        if Qt is not None and event.button() == Qt.MouseButton.LeftButton and not was_dragged:
            self.hide()
            self._parent_window.showNormal()
            self._parent_window.raise_()
            self._parent_window.activateWindow()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class _MICAWindow(QMainWindow):
    def __init__(self, ui: "MicaUI", url: str):
        super().__init__()
        self._ui = ui
        self.setWindowTitle("M.I.C.A")
        self.resize(1460, 960)
        self.setMinimumSize(1180, 760)
        
        # Set window flags to prevent flickering and disappearing
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinMaxButtonsHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self._mini_head = _MicaMiniHeadWindow(self)

        if QWebEngineView is None:
            raise RuntimeError("Qt WebEngine is not available")

        self._web = QWebEngineView(self)
        if QColor is not None:
            self._web.page().setBackgroundColor(QColor("#041018"))
        self.setCentralWidget(self._web)
        self._web.setUrl(QUrl(url))

    def changeEvent(self, event):  # noqa: N802
        try:
            if QEvent is not None and event.type() == QEvent.Type.WindowStateChange:
                if self.isMinimized():
                    self._mini_head.show()
                else:
                    self._mini_head.hide()
        finally:
            super().changeEvent(event)

    def closeEvent(self, event):  # noqa: N802
        try:
            with contextlib.suppress(Exception):
                self._mini_head.close()
            self._ui.shutdown()
        finally:
            super().closeEvent(event)


class MicaUI:
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
        self._artifacts = deque(maxlen=24)
        self._on_text_command = None
        self._on_voice_interrupt = None
        self._shutdown_event = threading.Event()
        self._server: Optional[ThreadingHTTPServer] = None
        self._server_thread: Optional[threading.Thread] = None
        self._server_url: Optional[str] = None
        self._vite_process: Optional[subprocess.Popen] = None
        self._app = None
        self._window = None
        self._config = get_config()
        self._session_manager = get_session_manager()
        self._voice_mode = get_voice_conversation_mode()

        # Debouncing and dirty flag for UI state updates
        self._state_dirty = False
        self._last_state_hash = None
        self._last_update_time = 0
        self._debounce_interval = 2.0  # 2 second debounce interval to reduce flickering

        self._ensure_ui_assets()
        self._start_http_server()
        self._log("SYS: UI bridge ready.")

    # ------------------------------------------------------------------
    # Compatibility API used by MicaLive
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

    @property
    def on_voice_interrupt(self):
        return self._on_voice_interrupt

    @on_voice_interrupt.setter
    def on_voice_interrupt(self, cb):
        self._on_voice_interrupt = cb

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

    def show_artifact(
        self,
        *,
        kind: str,
        title: str,
        content: str | None = None,
        language: str | None = None,
        columns: list[str] | None = None,
        rows: list[dict[str, Any]] | None = None,
        progress: float | int | None = None,
        url: str | None = None,
    ) -> str:
        """Publish a structured item into the M.I.C.A-only artifact panel."""
        artifact_id = f"artifact-{uuid4().hex[:10]}"
        item = {
            "id": artifact_id,
            "kind": str(kind or "note"),
            "title": str(title or "Artifact"),
            "content": content,
            "language": language,
            "columns": columns or [],
            "rows": rows or [],
            "progress": progress,
            "url": url,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        with self._lock:
            self._artifacts.appendleft(item)
        self._log(f"SYS: Artifact published: {item['title']}.")
        return artifact_id

    def clear_artifacts(self) -> None:
        with self._lock:
            self._artifacts.clear()

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
        if (os.environ.get("MICA_NO_QT") or os.environ.get("JARVIS_NO_QT")):
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

        if self._server_url and (os.environ.get("MICA_ALLOW_BROWSER_FALLBACK") or os.environ.get("JARVIS_ALLOW_BROWSER_FALLBACK")):
            import webbrowser

            webbrowser.open(self._server_url, new=1, autoraise=True)
            logger.warning(
                "Qt WebEngine is not available. Falling back to the system browser because "
                "MICA_ALLOW_BROWSER_FALLBACK is set."
            )
        else:
            logger.error(
                "%s M.I.C.A cannot open the desktop window. %s The system browser will not "
                "be opened automatically because voice mode depends on the local desktop runtime.",
                get_qt_webengine_diagnostic(),
                get_qt_webengine_recovery_hint(),
            )
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
            artifacts = list(self._artifacts)
        voice_first = bool(self._config.get("ui.voice_first", True))

        session = self._session_manager.get_current_session()
        recent_sessions = self._session_manager.get_recent_sessions(limit=16)

        current_state_dict = {
            "state": state,
            "muted": muted,
            "speaking": state == "SPEAKING",
            "current_file": current_file,
            "voice": self._voice_mode.snapshot(),
            "voice_focus": voice_first,
            "default_view": self._config.get("ui.default_view", "voice"),
            "logs": list(self._logs)[-80:],
            "artifacts": artifacts,
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
        psutil = _get_psutil()
        if psutil is None:
            return {"error": "psutil is not available"}

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
                "background_id": self._config.get("ui.background_id", "lake"),
                "background_url": self._config.get("ui.background_url", "/backgrounds/mica-lake.jpg"),
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

    def _model_route_payload(self, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
        from core.model_policy import get_model_policy

        payload = payload or {}
        text = str(payload.get("text") or payload.get("prompt") or "")
        route = get_model_policy().explain_route(
            text,
            action=str(payload.get("action") or ""),
            risk=str(payload.get("risk") or ""),
            sensitivity=str(payload.get("sensitivity") or ""),
            has_image=bool(payload.get("has_image", False)),
            context_chars=int(payload.get("context_chars") or len(text)),
        )
        return {"route": route}

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

    def _memory_curation_payload(self) -> Dict[str, Any]:
        try:
            from memory.memory_curation import build_curation_report

            return build_curation_report()
        except Exception as exc:
            logger.error("Could not build memory curation payload: %s", exc)
            return {"entries": [], "suggestions": [], "counts": {}, "error": str(exc)}

    def _memory_curation_action(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        from memory.memory_curation import apply_curation_action

        return apply_curation_action(str(payload.get("action") or ""), payload)

    def _knowledge_graph_payload(self, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
        from core.knowledge_graph import build_knowledge_graph
        from memory.memory_manager import load_memory

        payload = payload or {}
        source_filter = payload.get("sources") if isinstance(payload.get("sources"), list) else None
        tag_filter = payload.get("tags") if isinstance(payload.get("tags"), list) else None
        return build_knowledge_graph(
            memory=load_memory(),
            documents=self._documents_payload().get("files", []),
            source_filter=[str(item) for item in source_filter] if source_filter else None,
            tag_filter=[str(item) for item in tag_filter] if tag_filter else None,
            limit=int(payload.get("limit") or 120),
        )

    def _note_composer_payload(self) -> Dict[str, Any]:
        from memory.smart_note_composer import get_smart_note_composer

        return {"drafts": get_smart_note_composer().list_drafts()}

    def _note_composer_action(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        from memory.smart_note_composer import get_smart_note_composer

        composer = get_smart_note_composer()
        action = str(payload.get("action") or "draft")
        if action == "draft":
            draft = composer.create_draft(
                str(payload.get("title") or "Untitled Note"),
                str(payload.get("summary") or payload.get("markdown") or ""),
                sources=[str(item) for item in payload.get("sources", [])] if isinstance(payload.get("sources"), list) else [],
                tags=[str(item) for item in payload.get("tags", [])] if isinstance(payload.get("tags"), list) else [],
                links=[str(item) for item in payload.get("links", [])] if isinstance(payload.get("links"), list) else [],
                target_folder=str(payload.get("target_folder") or "Knowledge/Inbox"),
            )
            return {"status": "drafted", "draft": draft, **self._note_composer_payload()}
        if action == "update":
            draft = composer.update_draft(str(payload.get("draft_id") or ""), payload)
            return {"status": "updated", "draft": draft, **self._note_composer_payload()}
        if action == "approve":
            result = composer.approve_draft(str(payload.get("draft_id") or ""))
            return {**result, **self._note_composer_payload()}
        raise ValueError(f"unknown note composer action: {action}")

    def _automation_payload(self) -> Dict[str, Any]:
        from core.automation_scheduler import get_automation_scheduler

        return get_automation_scheduler().list()

    def _automation_action(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        from core.automation_scheduler import get_automation_scheduler

        scheduler = get_automation_scheduler()
        action = str(payload.get("action") or "create")
        if action == "create":
            item = scheduler.create(
                str(payload.get("name") or payload.get("automation_action") or "Automation"),
                str(payload.get("automation_action") or payload.get("task") or ""),
                str(payload.get("schedule") or "manual"),
                payload.get("parameters") if isinstance(payload.get("parameters"), dict) else {},
            )
            return {"status": "created", "automation": item, "automations": scheduler.list()}
        if action == "enable":
            item = scheduler.set_enabled(str(payload.get("automation_id") or ""), True)
            return {"status": "enabled", "automation": item, "automations": scheduler.list()}
        if action == "disable":
            item = scheduler.set_enabled(str(payload.get("automation_id") or ""), False)
            return {"status": "disabled", "automation": item, "automations": scheduler.list()}
        raise ValueError(f"unknown automation action: {action}")

    def _privacy_payload(self) -> Dict[str, Any]:
        from core.privacy_modes import get_privacy_mode_manager

        return get_privacy_mode_manager().snapshot()

    def _privacy_action(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        from core.privacy_modes import get_privacy_mode_manager

        return get_privacy_mode_manager().set_mode(
            str(payload.get("mode") or "balanced"),
            minutes=int(payload["minutes"]) if payload.get("minutes") else None,
        )

    def _project_workspaces_payload(self) -> Dict[str, Any]:
        from core.project_workspace import get_project_workspace_manager

        return get_project_workspace_manager().snapshot()

    def _project_workspace_action(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        from core.project_workspace import get_project_workspace_manager

        manager = get_project_workspace_manager()
        action = str(payload.get("action") or "create")
        if action == "create":
            workspace = manager.create(
                str(payload.get("name") or "Project"),
                paths=[str(item) for item in payload.get("paths", [])] if isinstance(payload.get("paths"), list) else [],
                tags=[str(item) for item in payload.get("tags", [])] if isinstance(payload.get("tags"), list) else [],
            )
            return {"status": "created", "workspace": workspace, "project_workspaces": manager.snapshot()}
        if action == "activate":
            return {"status": "activated", "project_workspaces": manager.set_active(str(payload.get("workspace_id") or ""))}
        if action == "add_note":
            workspace = manager.add_note(str(payload.get("workspace_id") or ""), str(payload.get("note") or ""))
            return {"status": "noted", "workspace": workspace, "project_workspaces": manager.snapshot()}
        raise ValueError(f"unknown project action: {action}")

    def _feedback_payload(self) -> Dict[str, Any]:
        from core.learning_feedback import get_learning_feedback_store

        return get_learning_feedback_store().list()

    def _feedback_action(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        from core.learning_feedback import get_learning_feedback_store

        store = get_learning_feedback_store()
        record = store.add(
            str(payload.get("rating") or "neutral"),
            str(payload.get("target") or ""),
            comment=str(payload.get("comment") or ""),
            correction=str(payload.get("correction") or ""),
            category=str(payload.get("category") or "general"),
            context=payload.get("context") if isinstance(payload.get("context"), dict) else {},
        )
        return {"status": "stored_for_review", "feedback": record, "learning_feedback": store.list()}

    def _plugin_payload(self) -> Dict[str, Any]:
        from core.plugin_system import get_plugin_manager

        manager = get_plugin_manager()
        return manager.status()

    def _os_payload(self) -> Dict[str, Any]:
        from core.personal_os import get_personal_os_integration

        return get_personal_os_integration().audit()

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
            "ingestion": {
                "queued": len([item for item in existing if item.get("status") == "uploaded"]),
                "chunked": len([item for item in existing if item.get("chunks", 0)]),
                "duplicates": len([item for item in existing if item.get("duplicate")]),
                "errors": [
                    {"id": item.get("id"), "name": item.get("name"), "error": item.get("error")}
                    for item in existing
                    if item.get("error")
                ],
            },
        }

    def _devices_payload(self) -> Dict[str, Any]:
        psutil = _get_psutil()
        if psutil is None:
            return {
                "current": {
                    "id": platform.node() or "local",
                    "name": platform.node() or "Local device",
                    "os": platform.platform(),
                    "python": platform.python_version(),
                    "pid": os.getpid(),
                    "process": "python",
                    "started_at": None,
                    "metrics_available": False,
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
                "metrics_available": True,
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
                existing_checksums = {
                    str(item.get("checksum"))
                    for item in records
                    if item.get("checksum")
                }
                ingestion_record: Dict[str, Any] = {}
                chunks: list[Dict[str, Any]] = []
                try:
                    from core.document_ingestion import build_ingestion_record, write_chunk_artifact

                    ingestion_record, chunks = build_ingestion_record(
                        destination,
                        existing_checksums=existing_checksums,
                    )
                    if chunks:
                        ingestion_record["chunk_path"] = write_chunk_artifact(
                            project_path("data", "document_chunks"),
                            ingestion_record,
                            chunks,
                        )
                except Exception as exc:
                    ingestion_record = {"errors": [str(exc)], "chunks": 0}
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
                    "checksum": ingestion_record.get("checksum"),
                    "chunks": ingestion_record.get("chunks", 0),
                    "chunk_path": ingestion_record.get("chunk_path"),
                    "duplicate": bool(ingestion_record.get("metadata", {}).get("duplicate")),
                }
                if ingestion_record.get("status") == "duplicate":
                    record["status"] = "duplicate"
                if ingestion_record.get("errors"):
                    record["error"] = "; ".join(str(item) for item in ingestion_record.get("errors", []))
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

    def _daily_briefing_payload(self) -> Dict[str, Any]:
        try:
            from core.daily_briefing import get_daily_briefing

            briefing = get_daily_briefing().generate_briefing(
                "morning",
                include_live_sources=False,
            )
            return {
                "status": "ready",
                "generated_at": briefing.get("generated_at"),
                "date": briefing.get("date"),
                "kind": briefing.get("kind", "morning"),
                "time_budget_minutes": briefing.get("time_budget_minutes"),
                "focus": briefing.get("focus", []),
                "items": briefing.get("items", []),
                "summary": get_daily_briefing().render_briefing_text(briefing),
            }
        except Exception as exc:
            logger.debug("Could not build daily briefing payload: %s", exc)
            return {
                "status": "degraded",
                "generated_at": datetime.now().isoformat(),
                "date": datetime.now().date().isoformat(),
                "kind": "morning",
                "time_budget_minutes": 0,
                "focus": [],
                "items": [],
                "summary": "Daily briefing is not available.",
                "error": str(exc),
            }

    def _task_pipelines_payload(self) -> Dict[str, Any]:
        try:
            from agent.task_pipeline import get_task_pipeline_manager

            pipelines = get_task_pipeline_manager().list_pipelines()
            return {
                "pipelines": pipelines,
                "active": [
                    pipeline
                    for pipeline in pipelines
                    if pipeline.get("status") not in {"completed", "cancelled"}
                ],
            }
        except Exception as exc:
            logger.debug("Could not load task pipelines: %s", exc)
            return {"pipelines": [], "active": [], "error": str(exc)}

    def _task_pipeline_action(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        from agent.task_pipeline import get_task_pipeline_manager

        manager = get_task_pipeline_manager()
        action = str(payload.get("action") or "create")
        if action == "create":
            raw_steps = payload.get("steps") or []
            steps = raw_steps if isinstance(raw_steps, list) else []
            pipeline = manager.create_pipeline(str(payload.get("goal") or ""), steps=[str(step) for step in steps])
            return {"status": "created", "pipeline": manager.get_pipeline(pipeline.id), "task_pipelines": self._task_pipelines_payload()}
        pipeline_id = str(payload.get("pipeline_id") or "")
        if action == "advance":
            pipeline = manager.advance(pipeline_id, note=str(payload.get("note") or ""))
        elif action == "pause":
            pipeline = manager.pause(pipeline_id)
        elif action == "resume":
            pipeline = manager.resume(pipeline_id)
        elif action == "verify":
            pipeline = manager.verify_step(
                pipeline_id,
                str(payload.get("step_id") or ""),
                str(payload.get("status") or "passed"),
                str(payload.get("note") or ""),
            )
        else:
            raise ValueError(f"unknown pipeline action: {action}")
        return {"status": action, "pipeline": pipeline, "task_pipelines": self._task_pipelines_payload()}

    def _command_center_payload(self) -> Dict[str, Any]:
        state = self._current_state()
        resources = self._resource_snapshot()
        setup = self._setup_payload()
        cockpit = self._cockpit_payload()
        resume = self._resume_payload()
        documents = self._documents_payload()
        action_history = self._action_history_payload()
        approvals = self._approvals_payload()
        permissions = self._permissions_payload()
        reliability = self._reliability_payload()
        quick_actions = self._quick_actions_payload()
        briefing = self._daily_briefing_payload()
        task_pipelines = self._task_pipelines_payload()
        privacy = self._privacy_payload()
        automations = self._automation_payload()
        projects = self._project_workspaces_payload()
        plugins = self._plugin_payload()
        os_integrations = self._os_payload()

        files = documents.get("files", []) if isinstance(documents.get("files"), list) else []
        indexed_files = [item for item in files if item.get("indexed")]
        tools = permissions.get("tools", []) if isinstance(permissions.get("tools"), list) else []
        enabled_tools = [item for item in tools if item.get("enabled")]
        pending_approvals = approvals.get("pending", []) if isinstance(approvals.get("pending"), list) else []
        performance = resources.get("performance", {}) if isinstance(resources.get("performance"), dict) else {}

        warnings: list[Dict[str, Any]] = []
        if not setup.get("configured"):
            warnings.append(
                {
                    "id": "setup",
                    "title": "Setup unvollstaendig",
                    "subtitle": "API Keys oder lokale Modellkonfiguration pruefen",
                    "status": "blocked",
                    "source": "setup",
                }
            )
        if reliability.get("status") in {"degraded", "blocked"}:
            for idx, recommendation in enumerate(reliability.get("recommendations", [])[:4]):
                warnings.append(
                    {
                        "id": f"reliability-{idx}",
                        "title": str(recommendation)[:90],
                        "status": str(reliability.get("status")),
                        "source": "reliability",
                    }
                )
        calendar_status = cockpit.get("calendar", {}).get("status", {})
        if calendar_status and not calendar_status.get("authenticated"):
            warnings.append(
                {
                    "id": "calendar",
                    "title": "Kalender nicht verbunden",
                    "subtitle": "Tagesuebersicht bleibt ohne Termine",
                    "status": "degraded",
                    "source": "calendar",
                }
            )
        if pending_approvals:
            warnings.append(
                {
                    "id": "approvals",
                    "title": f"{len(pending_approvals)} offene Tool-Freigabe(n)",
                    "subtitle": "M.I.C.A wartet auf Entscheidung",
                    "status": "blocked",
                    "source": "approvals",
                }
            )

        open_questions = list(resume.get("open_ends", [])[:4])
        for idx, approval in enumerate(pending_approvals[:4]):
            open_questions.append(
                {
                    "id": f"approval-{idx}",
                    "title": str(approval.get("summary") or approval.get("action") or "Tool-Freigabe"),
                    "subtitle": str(approval.get("reason") or approval.get("tool_name") or ""),
                    "status": str(approval.get("risk_level") or "pending"),
                    "source": "approvals",
                }
            )

        status_cards = [
            {
                "id": "backend",
                "label": "Backend",
                "value": str(state.get("state") or "online"),
                "status": "ok" if reliability.get("status") == "ok" else str(reliability.get("status") or "degraded"),
                "detail": f"{resources.get('threads', 0)} Threads, {performance.get('current_activity') or 'idle'}",
            },
            {
                "id": "ui",
                "label": "UI",
                "value": "Live",
                "status": "ok",
                "detail": str(state.get("default_view") or "command-center"),
            },
            {
                "id": "knowledge",
                "label": "Knowledge",
                "value": f"{len(indexed_files)}/{len(files)} Dateien",
                "status": "ok" if indexed_files else "degraded",
                "detail": "Indexierte Dokumente fuer lokale Suche",
            },
            {
                "id": "tools",
                "label": "Tools",
                "value": f"{len(enabled_tools)}/{len(tools)} aktiv",
                "status": "ok" if enabled_tools else "degraded",
                "detail": f"{len(pending_approvals)} Freigaben offen",
            },
            {
                "id": "privacy",
                "label": "Privacy",
                "value": str(privacy.get("mode", "balanced")),
                "status": "ok" if privacy.get("mode") in {"balanced", "cloud_allowed"} else "degraded",
                "detail": "Externe Verarbeitung nach Modus",
            },
            {
                "id": "automations",
                "label": "Automationen",
                "value": f"{len(automations.get('items', []))} aktiv",
                "status": "ok",
                "detail": ", ".join(automations.get("allowed_actions", [])[:3]),
            },
        ]

        return {
            "generated_at": datetime.now().isoformat(),
            "status_cards": status_cards,
            "active_tasks": [
                *cockpit.get("tasks", []),
                *[
                    {
                        "id": pipeline.get("id"),
                        "title": pipeline.get("goal", "")[:90],
                        "subtitle": f"{len([step for step in pipeline.get('steps', []) if step.get('status') == 'completed'])}/{len(pipeline.get('steps', []))} Schritte",
                        "status": pipeline.get("status"),
                        "source": "task_pipeline",
                    }
                    for pipeline in task_pipelines.get("active", [])[:4]
                ],
            ],
            "open_questions": open_questions,
            "recent_actions": action_history.get("records", [])[:8],
            "recent_files": resume.get("recent_files", []),
            "warnings": warnings[:8],
            "day_overview": {
                "calendar": cockpit.get("calendar", {}).get("items", []),
                "reminders": cockpit.get("reminders", []),
                "tasks": cockpit.get("tasks", []),
                "next_best_step": cockpit.get("next_best_step"),
                "briefing": briefing,
            },
            "quick_actions": quick_actions.get("items", []),
            "task_pipelines": task_pipelines,
            "privacy": privacy,
            "automations": automations,
            "project_workspaces": projects,
            "plugins": plugins,
            "os_integrations": os_integrations,
        }

    def _trust_level_payload(self) -> Dict[str, Any]:
        level = int(self._config.get("personal_mode.trust_level", 2) or 2)
        level = max(1, min(4, level))
        permission_profile = "safe" if level == 1 else "normal"
        if level >= 4:
            permission_profile = "normal"
        labels = {
            1: "Stufe 1",
            2: "Stufe 2",
            3: "Stufe 3",
            4: "Stufe 4",
        }
        descriptions = {
            1: "M.I.C.A darf automatisch lesen, suchen und zusammenfassen.",
            2: "M.I.C.A darf zusaetzlich Apps oeffnen, finden und sortieren.",
            3: "Dateiaenderungen brauchen deine Bestaetigung.",
            4: "Senden, Loeschen, Kaufen und Posten brauchen immer deine Bestaetigung.",
        }
        return {
            "level": level,
            "label": labels[level],
            "description": descriptions[level],
            "permission_profile": permission_profile,
            "rules": [
                {"action": "Lesen und zusammenfassen", "policy": "automatisch"},
                {"action": "Apps oeffnen, suchen, sortieren", "policy": "automatisch" if level >= 2 else "bestaetigen"},
                {"action": "Dateien aendern", "policy": "bestaetigen"},
                {"action": "Senden, loeschen, kaufen, posten", "policy": "immer bestaetigen"},
            ],
        }

    def _active_mode_payload(self) -> Dict[str, Any]:
        mode = str(self._config.get("personal_mode.active_mode", "focus") or "focus").lower()
        presets = {
            "focus": ("Focus", "Leise arbeiten, nur wichtige Hinweise.", "local_only", 2, "off"),
            "coding": ("Coding", "Projektkontext, Tests, Git und lokale Docs.", "balanced", 3, "subtle"),
            "research": ("Research", "Web, Dateien und Notizen sammeln und strukturieren.", "balanced", 2, "normal"),
            "private": ("Private", "Maximal lokal, externe Calls nur mit Bestaetigung.", "local_only", 1, "off"),
            "gaming": ("Gaming", "Performance, Game-Setup und leise Begleitung.", "balanced", 2, "subtle"),
            "admin": ("Admin", "Systempflege, Logs, Updates und Backups.", "private_with_approval", 4, "normal"),
        }
        label, description, privacy_mode, trust_level, proactive_mode = presets.get(mode, presets["focus"])
        return {
            "id": mode,
            "label": label,
            "description": description,
            "privacy_mode": privacy_mode,
            "trust_level": trust_level,
            "proactive_mode": proactive_mode,
            "status": "active",
        }

    def _personal_mode_payload(self) -> Dict[str, Any]:
        memory = self._memory_payload()
        raw_memory = memory.get("raw", {}) if isinstance(memory.get("raw"), dict) else {}
        identity = raw_memory.get("identity", {}) if isinstance(raw_memory.get("identity"), dict) else {}
        preferences = raw_memory.get("preferences", {}) if isinstance(raw_memory.get("preferences"), dict) else {}

        def memory_value(key: str, default: str) -> str:
            entry = identity.get(key)
            if isinstance(entry, dict):
                return str(entry.get("value") or default)
            return str(entry or default)

        return {
            "enabled": bool(self._config.get("personal_mode.enabled", True)),
            "owner_name": memory_value("name", "You"),
            "profile_id": str(self._config.get("personal_mode.profile_id", "local-owner")),
            "local_first": bool(self._config.get("personal_mode.local_first", True)),
            "glass_design": bool(self._config.get("personal_mode.glass_design", True)),
            "hidden_surfaces": list(
                self._config.get(
                    "personal_mode.hidden_surfaces",
                    ["teams", "marketplace", "publishing", "multi_user"],
                )
                or []
            ),
            "preferred_apps": list(
                self._config.get("personal_mode.preferred_apps", ["VS Code", "Browser", "Obsidian"])
                or []
            ),
            "routines": list(
                self._config.get(
                    "personal_mode.routines",
                    ["Morning brief", "Focus", "Evening review"],
                )
                or []
            ),
            "preferences": preferences,
        }

    def _project_awareness_payload(self) -> Dict[str, Any]:
        projects = self._project_workspaces_payload()
        active_project = projects.get("active")
        resume = self._resume_payload()
        reliability = self._reliability_payload()
        recent_files = resume.get("recent_files", []) if isinstance(resume.get("recent_files"), list) else []
        checks = reliability.get("checks", []) if isinstance(reliability.get("checks"), list) else []
        health = [
            {
                "id": str(check.get("name") or check.get("id") or f"check-{idx}"),
                "label": str(check.get("name") or check.get("message") or "Check"),
                "status": str(check.get("status") or "degraded"),
                "detail": str(check.get("message") or ""),
            }
            for idx, check in enumerate(checks[:4])
            if isinstance(check, dict)
        ]
        todos = [
            item
            for item in self._cockpit_payload().get("tasks", [])
            if isinstance(item, dict)
        ][:4]
        relevant = [
            {
                "id": str(item.get("id") or f"file-{idx}"),
                "title": str(item.get("title") or item.get("path") or "Datei"),
                "subtitle": str(item.get("subtitle") or item.get("source") or "Zuletzt genutzt"),
                "status": str(item.get("status") or "recent"),
                "source": "files",
            }
            for idx, item in enumerate(recent_files[:5])
            if isinstance(item, dict)
        ]
        next_three = (todos + relevant)[:3]
        if not next_three:
            next_three = [
                {
                    "id": "project-activate",
                    "title": "Aktives Projekt setzen",
                    "subtitle": "M.I.C.A kann danach TODOs, Dateien und Status besser buendeln.",
                    "status": "hint",
                    "source": "project",
                }
            ]
        return {
            "active_project": active_project,
            "relevant": relevant,
            "todos": todos,
            "health": health,
            "next_three": next_three,
        }

    def _silent_brain_payload(self) -> Dict[str, Any]:
        command_center = self._command_center_payload()
        warnings = command_center.get("warnings", []) if isinstance(command_center.get("warnings"), list) else []
        open_questions = command_center.get("open_questions", []) if isinstance(command_center.get("open_questions"), list) else []
        active_tasks = command_center.get("active_tasks", []) if isinstance(command_center.get("active_tasks"), list) else []
        project = self._project_awareness_payload()
        critical = [
            item for item in warnings if isinstance(item, dict) and item.get("status") in {"blocked", "error"}
        ][:4]
        hints = [
            item for item in [*warnings, *open_questions, *active_tasks, *project.get("next_three", [])]
            if isinstance(item, dict) and item not in critical
        ][:6]
        checks = [
            {
                "id": "privacy",
                "label": "Privacy",
                "status": str(self._privacy_payload().get("mode", "balanced")),
                "detail": "Personal Mode local-first",
            },
            {
                "id": "trust",
                "label": "Trust",
                "status": self._trust_level_payload()["label"],
                "detail": self._trust_level_payload()["description"],
            },
            {
                "id": "project",
                "label": "Projekt",
                "status": "active" if project.get("active_project") else "none",
                "detail": (project.get("active_project") or {}).get("name", "Kein aktives Projekt"),
            },
        ]
        return {
            "generated_at": datetime.now().isoformat(),
            "critical_count": len(critical),
            "hint_count": len(hints),
            "summary": f"{len(hints)} Hinweise gesammelt" if hints else "Alles ruhig",
            "hints": hints,
            "critical": critical,
            "checks": checks,
        }

    def _command_palette_payload(self) -> Dict[str, Any]:
        modes = [
            {**self._active_mode_payload(), "id": mode, "label": label}
            for mode, label in [
                ("focus", "Focus"),
                ("coding", "Coding"),
                ("research", "Research"),
                ("private", "Private"),
                ("gaming", "Gaming"),
                ("admin", "Admin"),
            ]
        ]
        return {
            "placeholder": "Frag M.I.C.A oder starte einen Modus...",
            "examples": [
                {"id": "focus", "label": "Fokus starten", "command": "fokus starten"},
                {"id": "today", "label": "Heute", "command": "was steht heute an"},
                {"id": "coding", "label": "Coding Setup", "command": "oeffne mein coding setup"},
                {"id": "folder", "label": "Ordner zusammenfassen", "command": "fass aktuellen ordner zusammen"},
                {"id": "health", "label": "Systemcheck", "command": "was ist kaputt im system"},
            ],
            "suggestions": self._quick_actions_payload().get("items", []),
            "modes": modes,
        }

    def _artifact_panel_payload(self) -> Dict[str, Any]:
        state = self._current_state()
        artifacts = state.get("artifacts", [])
        tabs = []
        for kind, label in [("text", "Text"), ("code", "Code"), ("image", "Bild"), ("table", "Tabelle"), ("note", "Notiz"), ("progress", "Fortschritt")]:
            tabs.append(
                {
                    "id": kind,
                    "label": label,
                    "count": len([item for item in artifacts if item.get("kind") == kind]),
                }
            )
        return {
            "open": bool(artifacts),
            "reason": "artifact" if artifacts else "manual",
            "items": artifacts,
            "tabs": tabs,
        }

    def _dashboard_payload(self) -> Dict[str, Any]:
        state = self._current_state()
        return {
            "state": state,
            "artifacts": state.get("artifacts", []),
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
            "command_center": self._command_center_payload(),
            "privacy": self._privacy_payload(),
            "automations": self._automation_payload(),
            "project_workspaces": self._project_workspaces_payload(),
            "learning_feedback": self._feedback_payload(),
            "plugins": self._plugin_payload(),
            "os_integrations": self._os_payload(),
            "personal_mode": self._personal_mode_payload(),
            "active_mode": self._active_mode_payload(),
            "trust_level": self._trust_level_payload(),
            "silent_brain": self._silent_brain_payload(),
            "command_palette": self._command_palette_payload(),
            "artifact_panel": self._artifact_panel_payload(),
            "project_awareness": self._project_awareness_payload(),
        }

    def _knowledge_action(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        from dataclasses import asdict, is_dataclass

        from core.knowledge_manager import get_knowledge_manager

        def encode(value: Any) -> Any:
            if is_dataclass(value):
                return encode(asdict(value))
            if isinstance(value, list):
                return [encode(item) for item in value]
            if isinstance(value, dict):
                return {str(key): encode(item) for key, item in value.items()}
            return value

        manager = get_knowledge_manager()
        action = str(payload.get("action") or "search")
        query = str(payload.get("query") or "")
        limit = int(payload.get("max_results") or payload.get("limit") or 5)
        sources = payload.get("sources")
        if not isinstance(sources, list):
            sources = None

        if action == "search":
            return {
                "action": action,
                "query": query,
                "results": encode(manager.search(query, limit=limit, sources=sources)),
            }
        if action == "context":
            return encode(manager.get_context(
                query,
                limit=limit,
                sources=sources,
                max_chars=int(payload.get("max_chars") or 4000),
            ))
        if action == "index":
            source = {
                "kind": payload.get("kind") or "directory",
                "uri": payload.get("path") or payload.get("uri") or ".",
                "metadata": payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
            }
            return encode(manager.index(source))
        if action == "suggest_notes":
            return encode(manager.suggest_notes(query, limit=limit, sources=sources))
        if action == "write_notes":
            return encode(manager.write_suggested_notes(query, limit=limit, sources=sources))
        if action == "graph":
            plan = manager.suggest_notes(query, limit=limit, sources=sources)
            return {
                "query": query,
                "graph_edges": encode(plan.graph_edges),
                "graph": self._knowledge_graph_payload(
                    {
                        "sources": sources or ["obsidian", "documents", "memory", "wikipedia"],
                        "limit": limit * 20,
                    }
                ),
            }
        if action == "stats":
            return {
                "sources": [getattr(adapter, "name", "unknown") for adapter in manager.adapters],
                "default_search_sources": ["obsidian", "documents"],
                "actions": [
                    "search",
                    "context",
                    "index",
                    "suggest_notes",
                    "write_notes",
                    "graph",
                    "stats",
                ],
            }
        return {"error": f"unknown knowledge action: {action}"}

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
            server_version = "MICAUI/1.0"

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
            name="MICAUIHttpServer",
        )
        self._server_thread.start()
        port = self._server.server_address[1]
        self._server_url = f"http://127.0.0.1:{port}"
        logger.info("UI server listening on %s", self._server_url)

    def _handle_get(self, request: BaseHTTPRequestHandler) -> None:
        parsed_url = urlparse(request.path)
        path = parsed_url.path
        query = parse_qs(parsed_url.query)

        if path == "/api/dashboard":
            return request._send_json(200, self._dashboard_payload())  # type: ignore[attr-defined]
        if path == "/api/cockpit":
            return request._send_json(200, self._cockpit_payload())  # type: ignore[attr-defined]
        if path == "/api/command-center":
            return request._send_json(200, self._command_center_payload())  # type: ignore[attr-defined]
        if path == "/api/personal-mode":
            return request._send_json(200, self._personal_mode_payload())  # type: ignore[attr-defined]
        if path == "/api/silent-brain":
            return request._send_json(200, self._silent_brain_payload())  # type: ignore[attr-defined]
        if path == "/api/artifact-panel":
            return request._send_json(200, self._artifact_panel_payload())  # type: ignore[attr-defined]
        if path == "/api/task-pipelines":
            return request._send_json(200, self._task_pipelines_payload())  # type: ignore[attr-defined]
        if path == "/api/session/resume":
            return request._send_json(200, self._resume_payload())  # type: ignore[attr-defined]
        if path == "/api/documents":
            return request._send_json(200, self._documents_payload())  # type: ignore[attr-defined]
        if path == "/api/setup":
            return request._send_json(200, self._setup_payload())  # type: ignore[attr-defined]
        if path == "/api/models":
            return request._send_json(200, self._models_payload())  # type: ignore[attr-defined]
        if path == "/api/model-route":
            return request._send_json(
                200,
                self._model_route_payload({"text": (query.get("text") or [""])[0]}),
            )  # type: ignore[attr-defined]
        if path == "/api/knowledge/graph":
            return request._send_json(200, self._knowledge_graph_payload())  # type: ignore[attr-defined]
        if path == "/api/memory":
            return request._send_json(200, self._memory_payload())  # type: ignore[attr-defined]
        if path == "/api/memory/curation":
            return request._send_json(200, self._memory_curation_payload())  # type: ignore[attr-defined]
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
        if path == "/api/notes/compose":
            return request._send_json(200, self._note_composer_payload())  # type: ignore[attr-defined]
        if path == "/api/automations":
            return request._send_json(200, self._automation_payload())  # type: ignore[attr-defined]
        if path == "/api/privacy":
            return request._send_json(200, self._privacy_payload())  # type: ignore[attr-defined]
        if path == "/api/project-workspaces":
            return request._send_json(200, self._project_workspaces_payload())  # type: ignore[attr-defined]
        if path == "/api/learning-feedback":
            return request._send_json(200, self._feedback_payload())  # type: ignore[attr-defined]
        if path == "/api/plugins":
            return request._send_json(200, self._plugin_payload())  # type: ignore[attr-defined]
        if path == "/api/os-integrations":
            return request._send_json(200, self._os_payload())  # type: ignore[attr-defined]
        if path == "/api/platform":
            return request._send_json(200, get_platform_hub().snapshot())  # type: ignore[attr-defined]
        if path == "/api/companion/workspace":
            result = get_platform_hub().action(
                "list_workspace_files",
                {"path": (query.get("path") or ["."])[0], "user": (query.get("user") or ["u-admin"])[0]},
            )
            status = 400 if "error" in result and "platform" not in result else 200
            return request._send_json(status, result)  # type: ignore[attr-defined]
        if path == "/api/companion/mobile-workspace":
            result = get_platform_hub().action(
                "get_companion_workspace",
                {"path": (query.get("path") or ["."])[0], "session_id": (query.get("session_id") or [""])[0], "user": (query.get("user") or ["u-admin"])[0]},
            )
            status = 400 if "error" in result and "platform" not in result else 200
            return request._send_json(status, result)  # type: ignore[attr-defined]
        if path == "/api/companion/file":
            try:
                max_bytes = int((query.get("max_bytes") or ["200000"])[0])
            except ValueError:
                max_bytes = 200_000
            result = get_platform_hub().action(
                "read_workspace_file",
                {
                    "path": (query.get("path") or [""])[0],
                    "max_bytes": max_bytes,
                    "user": (query.get("user") or ["u-admin"])[0],
                },
            )
            status = 400 if "error" in result and "platform" not in result else 200
            return request._send_json(status, result)  # type: ignore[attr-defined]
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
        if path.startswith("/api/agents/") and path.endswith("/manifest"):
            agent_id = path.split("/api/agents/", 1)[1].rsplit("/manifest", 1)[0].strip("/")
            manifest = get_platform_hub().get_agent_manifest(agent_id)
            if manifest is None:
                return request._send_json(404, {"error": "agent not found"})  # type: ignore[attr-defined]
            return request._send_json(200, manifest)  # type: ignore[attr-defined]
        if path.startswith("/apps/"):
            agent_id = path.split("/apps/", 1)[1].strip("/")
            html = get_platform_hub().get_agent_web_app(agent_id, embedded=False)
            if html is None:
                return request._send_json(404, {"error": "agent not found"})  # type: ignore[attr-defined]
            return request._send_bytes(200, html.encode("utf-8"), "text/html; charset=utf-8")  # type: ignore[attr-defined]
        if path.startswith("/embed/"):
            agent_id = path.split("/embed/", 1)[1].strip("/")
            html = get_platform_hub().get_agent_web_app(agent_id, embedded=True)
            if html is None:
                return request._send_json(404, {"error": "agent not found"})  # type: ignore[attr-defined]
            return request._send_bytes(200, html.encode("utf-8"), "text/html; charset=utf-8")  # type: ignore[attr-defined]
        if path.startswith("/mcp/"):
            agent_id = path.split("/mcp/", 1)[1].strip("/")
            descriptor = get_platform_hub().get_agent_mcp_descriptor(agent_id)
            if descriptor is None:
                return request._send_json(404, {"error": "agent not found"})  # type: ignore[attr-defined]
            return request._send_json(200, descriptor)  # type: ignore[attr-defined]
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
                    name="MICATextCommand",
                ).start()
            return request._send_json(202, {"status": "queued"})  # type: ignore[attr-defined]

        if path == "/api/mute":
            muted = bool(payload.get("muted", False))
            self.muted = muted
            return request._send_json(200, {"muted": self.muted})  # type: ignore[attr-defined]

        if path == "/api/voice/mode":
            voice = self._voice_mode.configure(
                input_mode=payload.get("input_mode"),
                push_to_talk_active=payload.get("push_to_talk_active"),
                wakeword_enabled=payload.get("wakeword_enabled"),
                wakeword=payload.get("wakeword"),
            )
            if voice.get("input_mode") == "push_to_talk":
                self.muted = not bool(voice.get("push_to_talk_active"))
            else:
                self.muted = False
            self._log(f"SYS: Voice mode set to {voice.get('input_mode')}.")
            return request._send_json(200, {"voice": voice, "muted": self.muted})  # type: ignore[attr-defined]

        if path == "/api/voice/interrupt":
            voice = self._voice_mode.request_interrupt()
            if callable(self._on_voice_interrupt):
                threading.Thread(
                    target=self._on_voice_interrupt,
                    daemon=True,
                    name="MICAVoiceInterrupt",
                ).start()
            self._log("SYS: Voice output interrupted.")
            return request._send_json(200, {"voice": voice})  # type: ignore[attr-defined]

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

        if path == "/api/personal-mode":
            updates = payload if isinstance(payload, dict) else {}
            allowed = {
                "enabled",
                "profile_id",
                "local_first",
                "glass_design",
                "hidden_surfaces",
                "preferred_apps",
                "routines",
                "active_mode",
                "trust_level",
            }
            personal_updates = {
                key: value for key, value in updates.items() if key in allowed
            }
            if personal_updates:
                get_config().update_local_settings({"personal_mode": personal_updates})
            return request._send_json(200, self._personal_mode_payload())  # type: ignore[attr-defined]

        if path == "/api/mode":
            mode = str(payload.get("mode") or payload.get("id") or "focus").lower().strip()
            valid_modes = {"focus", "coding", "research", "private", "gaming", "admin"}
            if mode not in valid_modes:
                return request._send_json(400, {"error": "invalid mode", "modes": sorted(valid_modes)})  # type: ignore[attr-defined]
            mode_payload = {
                "focus": {"privacy": "local_only", "trust": 2, "proactive": "off"},
                "coding": {"privacy": "balanced", "trust": 3, "proactive": "subtle"},
                "research": {"privacy": "balanced", "trust": 2, "proactive": "normal"},
                "private": {"privacy": "local_only", "trust": 1, "proactive": "off"},
                "gaming": {"privacy": "balanced", "trust": 2, "proactive": "subtle"},
                "admin": {"privacy": "private_with_approval", "trust": 4, "proactive": "normal"},
            }[mode]
            get_config().update_local_settings(
                {
                    "personal_mode": {
                        "active_mode": mode,
                        "trust_level": mode_payload["trust"],
                    },
                    "proactive": {"mode": mode_payload["proactive"]},
                }
            )
            with contextlib.suppress(Exception):
                from core.privacy_modes import get_privacy_mode_manager

                get_privacy_mode_manager().set_mode(str(mode_payload["privacy"]))
            return request._send_json(200, self._active_mode_payload())  # type: ignore[attr-defined]

        if path == "/api/trust-level":
            try:
                level = int(payload.get("level", 2))
            except (TypeError, ValueError):
                level = 2
            level = max(1, min(4, level))
            get_config().update_local_settings({"personal_mode": {"trust_level": level}})
            with contextlib.suppress(Exception):
                from core.approval_flow import get_approval_flow

                get_approval_flow().set_permission_level("safe" if level == 1 else "normal")
                get_approval_flow().set_require_confirmation_for_medium(level >= 3)
                get_approval_flow().set_require_confirmation_for_high(True)
            return request._send_json(200, self._trust_level_payload())  # type: ignore[attr-defined]

        if path == "/api/command-palette":
            text = str(payload.get("text", "")).strip()
            lowered = text.lower()
            if lowered in {"fokus starten", "focus", "focus mode"}:
                get_config().update_local_settings({"personal_mode": {"active_mode": "focus"}})
            elif "coding" in lowered or "code" in lowered:
                get_config().update_local_settings({"personal_mode": {"active_mode": "coding"}})
            elif "private" in lowered or "privat" in lowered:
                get_config().update_local_settings({"personal_mode": {"active_mode": "private"}})
            elif "research" in lowered or "recherche" in lowered:
                get_config().update_local_settings({"personal_mode": {"active_mode": "research"}})
            elif "admin" in lowered or "system" in lowered:
                get_config().update_local_settings({"personal_mode": {"active_mode": "admin"}})

            if text and callable(self._on_text_command):
                threading.Thread(
                    target=self._on_text_command,
                    args=(text,),
                    daemon=True,
                    name="MICACommandPalette",
                ).start()
            return request._send_json(
                202,
                {
                    "status": "queued" if text else "empty",
                    "command_palette": self._command_palette_payload(),
                    "artifact_panel": self._artifact_panel_payload(),
                },
            )  # type: ignore[attr-defined]

        if path == "/api/artifacts/clear":
            self.clear_artifacts()
            return request._send_json(200, self._artifact_panel_payload())  # type: ignore[attr-defined]

        if path == "/api/setup":
            return request._send_json(200, self._save_setup_payload(payload))  # type: ignore[attr-defined]

        if path == "/api/model-route":
            return request._send_json(200, self._model_route_payload(payload))  # type: ignore[attr-defined]

        if path == "/api/task-pipelines":
            try:
                result = self._task_pipeline_action(payload)
                return request._send_json(200, result)  # type: ignore[attr-defined]
            except Exception as exc:
                return request._send_json(400, {"error": str(exc), "task_pipelines": self._task_pipelines_payload()})  # type: ignore[attr-defined]

        if path == "/api/notes/compose":
            try:
                return request._send_json(200, self._note_composer_action(payload))  # type: ignore[attr-defined]
            except Exception as exc:
                return request._send_json(400, {"error": str(exc), **self._note_composer_payload()})  # type: ignore[attr-defined]

        if path == "/api/automations":
            try:
                return request._send_json(200, self._automation_action(payload))  # type: ignore[attr-defined]
            except Exception as exc:
                return request._send_json(400, {"error": str(exc), "automations": self._automation_payload()})  # type: ignore[attr-defined]

        if path == "/api/privacy":
            try:
                return request._send_json(200, self._privacy_action(payload))  # type: ignore[attr-defined]
            except Exception as exc:
                return request._send_json(400, {"error": str(exc), "privacy": self._privacy_payload()})  # type: ignore[attr-defined]

        if path == "/api/project-workspaces":
            try:
                return request._send_json(200, self._project_workspace_action(payload))  # type: ignore[attr-defined]
            except Exception as exc:
                return request._send_json(400, {"error": str(exc), "project_workspaces": self._project_workspaces_payload()})  # type: ignore[attr-defined]

        if path == "/api/learning-feedback":
            return request._send_json(200, self._feedback_action(payload))  # type: ignore[attr-defined]

        if path == "/api/memory/upsert":
            result = self._save_memory_entry(payload)
            status = 400 if "error" in result else 200
            return request._send_json(status, result)  # type: ignore[attr-defined]

        if path == "/api/memory/forget":
            result = self._forget_memory_entry(payload)
            status = 400 if "error" in result else 200
            return request._send_json(status, result)  # type: ignore[attr-defined]

        if path == "/api/memory/curation":
            try:
                result = self._memory_curation_action(payload)
                return request._send_json(200, result)  # type: ignore[attr-defined]
            except Exception as exc:
                return request._send_json(400, {"error": str(exc), "curation": self._memory_curation_payload()})  # type: ignore[attr-defined]

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

        if path == "/api/platform/action":
            action = str(payload.get("action", "")).strip()
            action_payload = payload.get("payload", {})
            if not isinstance(action_payload, dict):
                return request._send_json(400, {"error": "platform payload must be an object"})  # type: ignore[attr-defined]
            result = get_platform_hub().action(action, action_payload)
            status = 400 if "error" in result and "platform" not in result else 200
            return request._send_json(status, result)  # type: ignore[attr-defined]

        if path == "/api/knowledge":
            result = self._knowledge_action(payload if isinstance(payload, dict) else {})
            status = 400 if "error" in result else 200
            return request._send_json(status, result)  # type: ignore[attr-defined]

        if path == "/api/companion/terminal":
            result = get_platform_hub().action("run_companion_terminal", payload if isinstance(payload, dict) else {})
            status = 400 if "error" in result and "platform" not in result else 200
            return request._send_json(status, result)  # type: ignore[attr-defined]

        if path == "/api/companion/pair":
            result = get_platform_hub().action("create_companion_pairing", payload if isinstance(payload, dict) else {})
            status = 400 if "error" in result and "platform" not in result else 200
            return request._send_json(status, result)  # type: ignore[attr-defined]

        if path == "/api/companion/session":
            action = str(payload.get("action") or "activate")
            action_name = {
                "activate": "activate_companion_session",
                "heartbeat": "heartbeat_companion_session",
                "revoke": "revoke_companion_session",
            }.get(action, "activate_companion_session")
            result = get_platform_hub().action(action_name, payload if isinstance(payload, dict) else {})
            status = 400 if "error" in result and "platform" not in result else 200
            return request._send_json(status, result)  # type: ignore[attr-defined]

        if path.startswith("/api/agents/") and path.endswith("/invoke"):
            agent_id = path.split("/api/agents/", 1)[1].rsplit("/invoke", 1)[0].strip("/")
            result = get_platform_hub().invoke_agent(agent_id, payload if isinstance(payload, dict) else {})
            status = 404 if "error" in result else 200
            return request._send_json(status, result)  # type: ignore[attr-defined]

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

        if (os.environ.get("MICA_UI_DEV") or os.environ.get("JARVIS_UI_DEV")):
            url = "http://localhost:5173"
            self._start_vite_dev_server()
            self._log(f"SYS: Using Vite dev server at {url}")
        else:
            if not self._server_url:
                raise RuntimeError("UI HTTP server did not start")
            url = self._server_url
            self._log(f"SYS: Using built UI at {url}")

        self._window = _MICAWindow(self, url)

        # Use existing QApplication instance if available (created in main thread)
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
            app.setApplicationName("M.I.C.A")
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


# Backward-compatible aliases for older imports and tests.
JarvisUI = MicaUI
_JarvisMiniHeadWindow = _MicaMiniHeadWindow
_JARVISWindow = _MICAWindow
