"""
JarvisLive - Main JARVIS AI Assistant class.

This module contains the core JarvisLive class that manages:
- Live audio sessions with Gemini API
- Tool execution and routing
- Audio input/output handling
- Session management
- Integration with various JARVIS subsystems
"""

import asyncio
import contextlib
import functools
import json
import re
import sys
import threading
import time
import traceback
from datetime import datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any, Callable, Optional

import google.genai
from google.genai import types

from config.config_loader import get_config
from core.action_history import ActionStatus, get_action_history
from core.api_cache import get_api_cache
from core.approval_flow import get_approval_flow
from core.cross_device import get_cross_device
from core.healthcheck import build_runtime_report, format_runtime_report
from core.hud_overlay import get_hud_manager
from core.llm_fallback import get_hybrid_llm
from core.logger import get_logger
from core.metrics_collector import get_metrics_collector
from core.passive_vision import get_passive_vision
from core.performance_flags import get_performance_flags
from core.performance_monitor import get_performance_monitor, track_api_call_decorator
from core.plugin_system import get_plugin_manager
from core.proactive_suggestions import get_proactive_suggestions
from core.security import get_api_key_manager
from core.semantic_search import get_semantic_search
from core.session_manager import get_session_manager
from core.voice_emotion import get_emotion_analyzer
from core.vscode_bridge import get_vscode_bridge
from memory.memory_manager import (
    MEMORY_PATH,
    format_memory_for_prompt,
    load_memory,
    update_memory,
)
from memory.brain import get_memory_brain
from memory.obsidian_vault import get_obsidian_bridge
from ui_bridge import JarvisUI

try:
    import sounddevice as sd
except ImportError:
    sd = None

logger = get_logger(__name__)

# Constants
BASE_DIR = Path(__file__).resolve().parent.parent
PROMPT_PATH = BASE_DIR / "core" / "prompt.txt"
DEFAULT_LIVE_MODEL = "models/gemini-2.5-flash-native-audio-preview-12-2025"
DEFAULT_CHANNELS = 1
DEFAULT_SEND_SAMPLE_RATE = 16000
DEFAULT_RECEIVE_SAMPLE_RATE = 24000
DEFAULT_CHUNK_SIZE = 1024

_CTRL_RE = re.compile(r"<ctrl\d+>", re.IGNORECASE)


def _load_system_prompt() -> str:
    """
    Load the system prompt from file or return default.
    With caching enabled (via feature flag), uses LRU cache with 5-minute TTL.
    """
    perf_flags = get_performance_flags()
    metrics = get_metrics_collector()

    if perf_flags.is_enabled("cache_system_prompt"):
        return _load_system_prompt_cached()

    # Original implementation without caching
    metrics.start_operation("load_system_prompt_uncached")
    try:
        result = PROMPT_PATH.read_text(encoding="utf-8")
        metrics.end_operation("load_system_prompt_uncached", {"cached": False})
        return result
    except Exception:
        metrics.end_operation("load_system_prompt_uncached", {"cached": False, "error": True})
        return (
            "You are JARVIS, Tony Stark's AI assistant. "
            "Be concise, direct, and always use the provided tools to complete tasks. "
            "Never simulate or guess results — always call the appropriate tool."
        )


# Cached version with timestamp-based invalidation
_system_prompt_cache = {"prompt": None, "timestamp": None, "file_mtime": None}
_system_prompt_cache_ttl = timedelta(minutes=5)
_system_prompt_cache_lock = threading.Lock()


def _load_system_prompt_cached() -> str:
    """
    Load system prompt with LRU cache and 5-minute TTL.
    Cache is invalidated if file is modified.
    """
    metrics = get_metrics_collector()
    metrics.start_operation("load_system_prompt_cached")

    with _system_prompt_cache_lock:
        current_time = datetime.now()

        # Check if we need to refresh cache
        needs_refresh = False

        if _system_prompt_cache["prompt"] is None:
            needs_refresh = True
        elif current_time - _system_prompt_cache["timestamp"] > _system_prompt_cache_ttl:
            needs_refresh = True
        elif PROMPT_PATH.exists():
            current_mtime = PROMPT_PATH.stat().st_mtime
            if _system_prompt_cache["file_mtime"] != current_mtime:
                needs_refresh = True

        if needs_refresh:
            try:
                prompt = PROMPT_PATH.read_text(encoding="utf-8")
                _system_prompt_cache["prompt"] = prompt
                _system_prompt_cache["timestamp"] = current_time
                _system_prompt_cache["file_mtime"] = (
                    PROMPT_PATH.stat().st_mtime if PROMPT_PATH.exists() else None
                )
                metrics.end_operation(
                    "load_system_prompt_cached", {"cached": False, "refreshed": True}
                )
                logger.debug("System prompt cache refreshed")
            except Exception:
                # Return cached version if available, otherwise default
                if _system_prompt_cache["prompt"]:
                    metrics.end_operation(
                        "load_system_prompt_cached", {"cached": True, "error": True}
                    )
                    return _system_prompt_cache["prompt"]
                metrics.end_operation("load_system_prompt_cached", {"cached": False, "error": True})
                return (
                    "You are JARVIS, Tony Stark's AI assistant. "
                    "Be concise, direct, and always use the provided tools to complete tasks. "
                    "Never simulate or guess results — always call the appropriate tool."
                )
        else:
            metrics.end_operation("load_system_prompt_cached", {"cached": True, "refreshed": False})

    return _system_prompt_cache["prompt"]


def _clean_transcript(text: str) -> str:
    """Clean transcript text by removing control characters."""
    text = _CTRL_RE.sub("", text)
    text = re.sub(r"[\x00-\x08\x0b-\x1f]", "", text)
    return text.strip()


def _ensure_audio_backend() -> None:
    """Ensure sounddevice is available."""
    if sd is None:
        raise RuntimeError(
            "sounddevice is not installed. Install dependencies with "
            "'pip install -r requirements.txt'."
        )


def _is_invalid_api_key_error(exc: Exception) -> bool:
    """Check if exception is due to invalid API key."""
    text = str(exc).lower()
    return "api key not valid" in text or "invalid api key" in text


def _get_api_key() -> str:
    """Get API key from config or encrypted storage."""
    config = get_config()
    api_key = str(config.get_api_key("gemini") or "").strip()
    if api_key:
        return api_key

    # Try encrypted storage
    try:
        key_manager = get_api_key_manager()
        encrypted_key = key_manager.get_key("gemini")
        if encrypted_key:
            return encrypted_key
    except Exception:
        pass

    # Fallback to file
    api_config_path = BASE_DIR / "config" / "api_keys.json"
    with open(api_config_path, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]


# Import tool declarations from main
TOOL_DECLARATIONS = []
FEATURE_TOOL_DECLARATIONS = []


class JarvisLive:
    """
    Main JARVIS AI Assistant class managing live sessions and tool execution.

    This class handles:
    - Gemini Live API connections
    - Audio input/output streaming
    - Tool execution and routing
    - Session management and context
    - Integration with all JARVIS subsystems
    """

    def __init__(self, ui: JarvisUI) -> None:
        """
        Initialize JarvisLive instance.

        Args:
            ui: JarvisUI instance for user interface
        """
        self.ui = ui
        self.session: Optional[Any] = None
        self.audio_in_queue: Optional[asyncio.Queue] = None
        self.out_queue: Optional[asyncio.Queue] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._is_speaking = False
        self._speaking_lock = threading.Lock()
        self.ui.on_text_command = self._on_text_command
        self._turn_done_event: Optional[asyncio.Event] = None
        self._refresh_requested = False
        self._refresh_reason = ""
        self._context_signature = self._get_context_signature()

        # Initialize subsystems
        self.config = get_config()
        self.plugin_manager = get_plugin_manager()
        self.plugin_manager.load_all_plugins()
        self.hybrid_llm = get_hybrid_llm()
        self.passive_vision = get_passive_vision()
        self.semantic_search = get_semantic_search()
        self.hud = get_hud_manager()
        self.proactive = get_proactive_suggestions()
        self.emotion = get_emotion_analyzer()
        self.vscode = get_vscode_bridge()
        self.cross_device = get_cross_device()
        self.obsidian_bridge = get_obsidian_bridge()
        self.memory_brain = get_memory_brain()
        self.session_context = get_session_manager()
        self.session_context.start_session(force=True)
        self.conversation_started = False

        # Performance monitoring
        self.perf_monitor = get_performance_monitor()

        # Approval flow for risky actions
        self.approval_flow = get_approval_flow()
        # Set permission level from config or default to normal
        perm_level = self.config.get("security.permission_level", "normal")
        self.approval_flow.set_permission_level(perm_level)

        # Action history for tracking and undo
        self.action_history = get_action_history()

        self._refresh_runtime_config()
        self._tool_declarations = self._build_tool_declarations()
        self._auto_start_services()

        logger.info("JarvisLive initialized")

    def _refresh_runtime_config(self) -> None:
        """Refresh runtime configuration from config file."""
        self.live_model = self.config.get("models.live", DEFAULT_LIVE_MODEL)
        self.voice_name = self.config.get("models.voice_name", "Charon")
        self.context_window = int(self.config.get("models.context_window", 1000000))
        self.channels = int(self.config.get("audio.channels", DEFAULT_CHANNELS))
        self.send_sample_rate = int(
            self.config.get("audio.send_sample_rate", DEFAULT_SEND_SAMPLE_RATE)
        )
        self.receive_sample_rate = int(
            self.config.get("audio.receive_sample_rate", DEFAULT_RECEIVE_SAMPLE_RATE)
        )
        self.chunk_size = int(self.config.get("audio.chunk_size", DEFAULT_CHUNK_SIZE))

    def _patch_live_websocket_keepalive(self) -> None:
        """Relax the Gemini Live websocket heartbeat slightly."""
        try:
            import google.genai.live as live_module

            if getattr(live_module.ws_connect, "_jarvis_keepalive_patched", False):
                return

            ping_interval = self.config.get("audio.websocket_ping_interval", None)
            ping_timeout = self.config.get("audio.websocket_ping_timeout", None)
            close_timeout = int(self.config.get("audio.websocket_close_timeout", 30))

            if ping_interval in ("", "none", "None"):
                ping_interval = None
            elif ping_interval is not None:
                ping_interval = int(ping_interval)

            if ping_timeout in ("", "none", "None"):
                ping_timeout = None
            elif ping_timeout is not None:
                ping_timeout = int(ping_timeout)

            live_module.ws_connect = partial(
                live_module.ws_connect,
                ping_interval=ping_interval,
                ping_timeout=ping_timeout,
                close_timeout=close_timeout,
            )
            setattr(live_module.ws_connect, "_jarvis_keepalive_patched", True)
            logger.info(
                "Patched Gemini Live websocket keepalive "
                f"(ping_interval={ping_interval}, ping_timeout={ping_timeout}, "
                f"close_timeout={close_timeout}s)"
            )
        except Exception as e:
            logger.warning(f"Could not patch Gemini Live websocket keepalive: {e}")

    def _build_idle_audio_frame(self, duration_ms: int = 20) -> dict[str, Any]:
        """Build a tiny silent PCM frame for idle keepalive traffic."""
        samples = max(1, int(self.send_sample_rate * duration_ms / 1000))
        payload = b"\x00" * (samples * self.channels * 2)
        return {
            "data": payload,
            "mime_type": f"audio/pcm;rate={self.send_sample_rate}",
        }

    def _log_stream_state(self, label: str) -> None:
        """Emit a compact snapshot of the realtime stream state."""
        out_q = self.out_queue.qsize() if self.out_queue is not None else -1
        in_q = self.audio_in_queue.qsize() if self.audio_in_queue is not None else -1
        logger.info(
            "[LiveDiag] %s | out_queue=%s in_queue=%s speaking=%s muted=%s connected=%s",
            label,
            out_q,
            in_q,
            self._is_speaking,
            self.ui.muted,
            self.session is not None,
        )

    async def _monitor_runtime_health(self) -> None:
        """Periodically log low-noise runtime diagnostics."""
        last_tick = asyncio.get_event_loop().time()
        while True:
            await asyncio.sleep(30)
            now = asyncio.get_event_loop().time()
            lag = now - last_tick - 30
            last_tick = now
            if lag > 1.0:
                logger.warning("[LiveDiag] Event loop lag detected: %.2fs", lag)
            self._log_stream_state("heartbeat")

    async def _shutdown_runtime_tasks(self, tasks: dict[str, asyncio.Task[Any]]) -> None:
        """Cancel runtime tasks and wait for them to finish."""
        for task in tasks.values():
            task.cancel()
        for name, task in tasks.items():
            with contextlib.suppress(asyncio.CancelledError):
                await task
            if task.cancelled():
                continue
            try:
                exc = task.exception()
            except asyncio.CancelledError:
                continue
            if exc is not None:
                logger.debug("Task %s finished during shutdown with: %r", name, exc)

    def _log_task_failure(self, name: str, task: asyncio.Task[Any]) -> None:
        """Log a task failure with as much detail as possible."""
        exc = task.exception()
        if exc is None:
            logger.warning("Runtime task %s stopped without an exception", name)
            return
        logger.error("Runtime task %s failed: %r", name, exc)
        if getattr(exc, "exceptions", None):
            for idx, sub_exc in enumerate(exc.exceptions, start=1):
                logger.error("  sub-exception %s: %r", idx, sub_exc)
        traceback.print_exception(type(exc), exc, exc.__traceback__)

    def _build_tool_declarations(self) -> list[dict[str, Any]]:
        """
        Build tool declarations for Gemini Live API.

        Returns:
            List of tool declarations including core, feature, and plugin tools
        """
        # Import tool declarations from main module
        from main import FEATURE_TOOL_DECLARATIONS, TOOL_DECLARATIONS

        declarations = list(TOOL_DECLARATIONS)
        declarations.extend(FEATURE_TOOL_DECLARATIONS)
        declarations.extend(self.plugin_manager.get_tool_declarations())

        # Load MCP tools if enabled
        if self.config.get("security.mcp_enabled", True):
            try:
                from core.mcp_client import get_mcp_client, get_mcp_tools

                mcp_client = get_mcp_client()
                mcp_client.connect_all_enabled()
                mcp_tools = get_mcp_tools()

                # Format MCP tools to match Gemini Live tool declaration schema
                for tool in mcp_tools:
                    declarations.append(
                        {
                            "name": tool["name"],
                            "description": tool["description"],
                            "parameters": tool["parameters"],
                        }
                    )
                logger.info(f"[MCP] Registered {len(mcp_tools)} tools into tool declarations.")
            except Exception as me:
                logger.warning(f"[MCP] Failed to load/register MCP tools: {me}")

        return declarations

    def _auto_start_services(self) -> None:
        """Auto-start enabled services."""
        if self.hud.initialize():
            self.hud.set_status("JARVIS booting")

        if self.passive_vision.enabled:
            self.passive_vision.start()

        if self.proactive.enabled:
            self.proactive.set_speak_callback(self.speak)
            self.proactive.start()

        if self.config.get("briefing.enabled", False):
            from core.daily_briefing import get_daily_briefing

            briefing = get_daily_briefing()
            briefing.set_speak_callback(self.speak)
            briefing.start_scheduler()

        if self.config.get("rag.enabled", False) and self.semantic_search.enabled:
            auto_paths = self.config.get("rag.auto_index_paths", ["./docs"])
            stats = self.semantic_search.get_stats()
            if stats.get("total_documents", 0) == 0:
                for raw_path in auto_paths:
                    path = Path(raw_path)
                    if not path.is_absolute():
                        path = BASE_DIR / path
                    if path.exists():
                        self.semantic_search.index_directory(path)

        if self.config.get("vscode.bridge_enabled", False) and self.config.get(
            "vscode.auto_connect", False
        ):
            self.vscode.sync_connect()

    def _note_user_input(self, text: str) -> None:
        """Note user input and start Obsidian conversation if enabled."""
        if text and self.config.get("obsidian.enabled", False) and not self.conversation_started:
            self.start_obsidian_conversation(text)

    def _get_context_signature(self) -> tuple[Optional[float], Optional[float]]:
        """
        Get signature of context files for change detection.

        Returns:
            Tuple of (prompt_mtime, memory_mtime)
        """
        prompt_mtime = PROMPT_PATH.stat().st_mtime if PROMPT_PATH.exists() else None
        memory_mtime = MEMORY_PATH.stat().st_mtime if MEMORY_PATH.exists() else None
        return prompt_mtime, memory_mtime

    def _request_session_refresh(self, reason: str) -> None:
        """
        Request session context refresh.

        We keep this as a soft marker only. Hard-closing the websocket here
        interrupted conversations and caused frequent context resets.

        Args:
            reason: Reason for refresh
        """
        self._refresh_requested = True
        self._refresh_reason = reason
        self._context_signature = self._get_context_signature()

    async def _apply_pending_refresh(self) -> None:
        """Apply pending session refresh if requested.

        This no longer closes the live session. It only logs that the context
        changed so the current conversation can continue uninterrupted.
        """
        if not self._refresh_requested or not self.session:
            return
        reason = self._refresh_reason or "Context updated."
        self._refresh_requested = False
        self._refresh_reason = ""
        self.ui.write_log(f"SYS: Context updated. {reason}")
        logger.info(f"Deferred session refresh: {reason}")

    def _handle_passive_vision(self, args: dict[str, Any]) -> str:
        """Handle passive vision tool calls."""
        action = args.get("action", "status")
        if action == "start":
            return (
                "Passive vision started."
                if self.passive_vision.start()
                else "Passive vision is unavailable."
            )
        if action == "stop":
            self.passive_vision.stop()
            return "Passive vision stopped."
        if action == "save":
            self.passive_vision.save_memory_to_disk()
            return "Passive vision memory saved."
        if action == "recent":
            minutes = int(args.get("minutes", 5) or 5)
            recent = self.passive_vision.memory.get_recent(minutes=minutes)
            if not recent:
                return f"No visual memory entries found in the last {minutes} minutes."
            lines = [f"Recent visual memory entries: {len(recent)}"]
            for entry in recent[:5]:
                lines.append(
                    f"- {entry['timestamp']}: {entry['ocr_text'] or '[no text extracted]'}"
                )
            return "\n".join(lines)
        if action == "query":
            question = args.get("question", "")
            return self.passive_vision.query_memory(question)

        status = "running" if self.passive_vision.running else "stopped"
        return (
            f"Passive vision is {status}. "
            f"Enabled={self.passive_vision.enabled}, interval={self.passive_vision.interval}s."
        )

    def _handle_semantic_search(self, args: dict[str, Any]) -> str:
        """Handle semantic search tool calls."""
        action = args.get("action", "stats")
        if action == "index_directory":
            raw_path = args.get("path") or "."
            path = Path(raw_path)
            if not path.is_absolute():
                path = BASE_DIR / path
            self.semantic_search.index_directory(path)
            return f"Semantic search indexed directory: {path}"
        if action == "search":
            query = args.get("query", "")
            max_results = int(args.get("max_results", 5) or 5)
            results = self.semantic_search.search(query, n_results=max_results)
            if not results:
                return "No semantic search results found."
            lines = [f"Found {len(results)} semantic matches:"]
            for item in results:
                meta = item.get("metadata", {})
                lines.append(
                    f"- {meta.get('file_name', 'unknown')}: {item.get('document', '')[:180]}"
                )
            return "\n".join(lines)
        if action == "ask":
            return self.semantic_search.ask(
                args.get("query", ""),
                n_results=int(args.get("max_results", 3) or 3),
            )
        if action == "clear":
            self.semantic_search.clear_index()
            return "Semantic search index cleared."
        return json.dumps(self.semantic_search.get_stats(), indent=2)

    def _handle_proactive_suggestions(self, args: dict[str, Any]) -> str:
        """Handle proactive suggestions tool calls."""
        action = args.get("action", "list")
        if action == "clear":
            self.proactive.clear_suggestions()
            return "Proactive suggestions cleared."
        if action == "dismiss":
            self.proactive.dismiss_suggestion(int(args.get("index", 0) or 0))
            return "Suggestion dismissed."

        suggestions = self.proactive.get_suggestions()
        if not suggestions:
            return "There are no proactive suggestions right now."
        lines = [f"Proactive suggestions: {len(suggestions)}"]
        for idx, item in enumerate(suggestions):
            lines.append(f"{idx}. [{item['priority']}] {item['text']}")
        return "\n".join(lines)

    def _handle_cross_device(self, args: dict[str, Any]) -> str:
        """Handle cross-device tool calls."""
        action = args.get("action", "status")
        platform = args.get("platform", "both")
        if action == "send_summary":
            ok = self.cross_device.sync_send_summary(args.get("message", ""), platform)
            return "Summary sent." if ok else "Failed to send summary."
        if action == "send_reminder":
            ok = self.cross_device.sync_send_reminder(args.get("message", ""), platform)
            return "Reminder sent." if ok else "Failed to send reminder."
        if action == "send_task_completion":
            ok = self.cross_device.sync_send_task_completion(
                args.get("task", "Task"),
                args.get("result", "Completed"),
                platform,
            )
            return "Task completion sent." if ok else "Failed to send task completion."
        if action == "send_file":
            ok = self.cross_device.sync_send_file(
                args.get("file_path", ""),
                args.get("caption", ""),
                platform,
            )
            return "File sent." if ok else "Failed to send file."
        return (
            "Cross-device status: "
            f"telegram={'on' if self.cross_device.telegram_bot else 'off'}, "
            f"discord={'on' if self.cross_device.discord_bot else 'off'}."
        )

    def _handle_vscode_bridge(self, args: dict[str, Any]) -> str:
        """Handle VS Code bridge tool calls."""
        action = args.get("action", "diagnostics")
        if action == "connect":
            return (
                "VS Code bridge connected."
                if self.vscode.sync_connect()
                else "VS Code bridge unavailable."
            )
        if action == "diagnostics":
            return json.dumps(self.vscode.sync_get_diagnostics(), indent=2)
        if action == "get_selection":
            return json.dumps(self.vscode.sync_get_selection(), indent=2)
        if action == "insert_text":
            return json.dumps(self.vscode.sync_insert_text(args.get("text", "")), indent=2)
        if action == "run_code":
            return json.dumps(self.vscode.sync_run_code(args.get("language", "python")), indent=2)
        if action == "edit_file":
            return json.dumps(
                self.vscode.sync_edit_file(
                    args.get("file_path", ""),
                    args.get("old_text", ""),
                    args.get("new_text", ""),
                ),
                indent=2,
            )
        if action == "refactor":
            return json.dumps(
                self.vscode.sync_refactor(
                    args.get("file_path", ""),
                    args.get("pattern", ""),
                    args.get("replacement", ""),
                ),
                indent=2,
            )
        return f"Unknown VS Code bridge action: {action}"

    def _run_system_diagnostics(self, verbose: bool = False) -> str:
        """Run system diagnostics and return report."""
        report = build_runtime_report(
            base_dir=BASE_DIR,
            config=self.config,
            plugin_manager=self.plugin_manager,
            tool_declarations=self._tool_declarations,
        )
        return format_runtime_report(report, verbose=verbose)

    def _on_text_command(self, text: str) -> None:
        """Handle text command from UI."""
        if not self._loop or not self.session:
            return
        if self._get_context_signature() != self._context_signature:
            self.ui.write_log(
                "SYS: prompt.txt or long_term.json changed. Restart JARVIS or wait for a reconnect to load the new context."
            )
            self._context_signature = self._get_context_signature()
        self._note_user_input(text)
        self.session_context.record_user_message(text)

        memory_reply = self.memory_brain.handle_memory_query(text)
        if memory_reply:
            self.session_context.record_jarvis_response(memory_reply)
            self.ui.write_log(f"Jarvis: {memory_reply}")
            return

        forgotten, forget_reply = self.memory_brain.handle_forget_request(text)
        if forgotten:
            self.session_context.record_jarvis_response(forget_reply)
            self.ui.write_log(f"Jarvis: {forget_reply}")
            return

        handled, candidates = self.memory_brain.handle_direct_request(text, source="ui")
        if handled:
            ack = "Ich habe mir das gemerkt."
            if candidates:
                primary = candidates[0]
                ack = f"Ich habe mir das gemerkt: {primary.value}."
            self.session_context.record_jarvis_response(ack)
            self.ui.write_log(f"Jarvis: {ack}")
            return

        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(turns={"parts": [{"text": text}]}, turn_complete=True),
            self._loop,
        )

    def set_speaking(self, value: bool) -> None:
        """
        Set speaking state.

        Args:
            value: Speaking state
        """
        with self._speaking_lock:
            self._is_speaking = value
        if value:
            self.ui.set_state("SPEAKING")
            logger.debug("Speaking state set to True")
        else:
            # Always set to LISTENING when not speaking, regardless of mute state
            self.ui.set_state("LISTENING")
            logger.debug("Speaking state set to False")

    def speak(self, text: str) -> None:
        """
        Send text to be spoken by JARVIS.

        Args:
            text: Text to speak
        """
        if not self._loop or not self.session:
            return
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(turns={"parts": [{"text": text}]}, turn_complete=True),
            self._loop,
        )

    def speak_error(self, tool_name: str, error: str) -> None:
        """
        Speak error message.

        Args:
            tool_name: Name of the tool that failed
            error: Error message
        """
        short = str(error)[:120]
        self.ui.write_log(f"ERR: {tool_name} — {short}")
        self.speak(f"Sir, {tool_name} encountered an error. {short}")

    def start_obsidian_conversation(self, user_input: str) -> None:
        """
        Start tracking a new conversation for Obsidian.

        Args:
            user_input: Initial user input
        """
        try:
            self.obsidian_bridge.start_conversation(user_input)
            self.conversation_started = True
            logger.info("[Obsidian] Conversation tracking started")
        except Exception as e:
            logger.warning(f"[Obsidian] Could not start tracking: {e}")

    def end_obsidian_conversation(self, summary: Optional[str] = None) -> None:
        """
        End conversation tracking and save to Obsidian.

        Args:
            summary: Optional conversation summary
        """
        if not self.conversation_started:
            return

        try:
            note_title = self.obsidian_bridge.end_conversation(summary)
            if note_title:
                logger.info(f"[Obsidian] Saved conversation: {note_title}")
                self.speak(f"Conversation saved to Obsidian, sir.")
            self.conversation_started = False
        except Exception as e:
            logger.warning(f"[Obsidian] Could not save conversation: {e}")

    def track_obsidian_action(self, action: str) -> None:
        """
        Track an action taken during conversation.

        Args:
            action: Action description
        """
        if self.conversation_started:
            self.obsidian_bridge.add_action(action)

    def track_obsidian_response(self, response: str) -> None:
        """
        Track an AI response during conversation.

        Args:
            response: AI response text
        """
        if self.conversation_started:
            self.obsidian_bridge.add_ai_response(response)

    def _build_config(self) -> types.LiveConnectConfig:
        """
        Build Gemini Live connection configuration.

        Returns:
            LiveConnectConfig with system instruction and tools
        """
        memory = load_memory()
        mem_str = format_memory_for_prompt(memory)
        sys_prompt = _load_system_prompt()

        now = datetime.now()
        time_str = now.strftime("%A, %B %d, %Y — %I:%M %p")
        time_ctx = (
            f"[CURRENT DATE & TIME]\n"
            f"Right now it is: {time_str}\n"
            f"Use this to calculate exact times for reminders.\n\n"
        )

        parts = [time_ctx]
        if mem_str:
            parts.append(mem_str)

        # Add session context summary if available
        context_summary = self.session_context.build_context_summary()
        if context_summary:
            parts.append(context_summary)

        parts.append(sys_prompt)

        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            input_audio_transcription={},
            system_instruction="\n".join(parts),
            tools=[{"function_declarations": self._tool_declarations}],
            session_resumption=types.SessionResumptionConfig(),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=self.voice_name)
                )
            ),
            generation_config=types.GenerationConfig(
                temperature=0.7,
                max_output_tokens=8192,
            ),
        )

    async def _execute_tool(self, fc) -> types.FunctionResponse:
        """
        Execute a tool call from Gemini Live.

        Args:
            fc: Function call from Gemini

        Returns:
            FunctionResponse with result
        """
        name = fc.name
        args = dict(fc.args or {})

        logger.info(f"Tool execution: {name} with args {args}")
        self.ui.set_state("THINKING")
        self.hud.set_status("Working")
        self.hud.set_action(name)

        # Check approval for risky actions
        # Extract the specific action from args for permission checking
        action = args.get("action", name)
        is_allowed, approval_message = self.approval_flow.check_and_request_approval(
            tool_name=name, action=action, parameters=args
        )

        if not is_allowed:
            logger.warning(f"Action blocked or denied: {name} - {approval_message}")
            self.ui.write_log(f"SEC: {approval_message}")
            return types.FunctionResponse(
                id=fc.id, name=name, response={"result": f"Action not allowed: {approval_message}"}
            )

        # Import tool functions dynamically to avoid circular imports
        from main import (
            browser_control,
            code_helper,
            computer_control,
            computer_settings,
            desktop_control,
            dev_agent,
            daily_mode,
            file_controller,
            file_processor,
            flight_finder,
            game_updater,
            gmail_manager,
            open_app,
            reminder,
            roblox_controller,
            screen_process,
            self_dev_agent,
            send_message,
            weather_action,
            web_search_action,
            youtube_video,
        )

        if name == "save_memory":
            category = args.get("category", "notes")
            key = args.get("key", "")
            value = args.get("value", "")
            if key and value:
                update_memory(
                    {
                        category: {
                            key: {
                                "value": value,
                                "source": "tool_call",
                                "confidence": "high",
                                "tags": ["save_memory", "tool_call"],
                            }
                        }
                    }
                )
                logger.info(f"Memory saved: {category}/{key} = {value}")
                # Keep the current live session alive. The saved memory will be
                # available in the next natural reconnect, but we don't force a
                # reconnect here because it breaks conversations.
            self.proactive.track_action(name, success=True)
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
            return types.FunctionResponse(
                id=fc.id, name=name, response={"result": "ok", "silent": True}
            )

        if name == "memory_brain":
            action = str(args.get("action", "query")).lower()
            query = str(args.get("query", "")).strip()
            limit = int(args.get("limit", 6) or 6)

            if action in {"query", "summary", "status"}:
                result = self.memory_brain.describe_memory(query=query or None, limit=limit)
            elif action == "forget":
                handled, reply = self.memory_brain.handle_forget_request(f"vergiss {query}")
                result = reply if handled else "I could not process that memory request."
            else:
                result = f"Unknown memory_brain action: {action}"

            self.proactive.track_action(name, success=True)
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
            return types.FunctionResponse(
                id=fc.id, name=name, response={"result": result, "silent": False}
            )

        loop = asyncio.get_event_loop()
        result = "Done."

        # Track action for Obsidian
        if self.conversation_started:
            self.track_obsidian_action(f"{name}: {args}")

        # Track performance
        start_perf = time.perf_counter()
        tool_action = str(action or name)

        try:
            if name == "open_app":
                r = await loop.run_in_executor(
                    None, lambda: open_app(parameters=args, response=None, player=self.ui)
                )
                result = r or f"Opened {args.get('app_name')}."

            elif name == "weather_report":
                r = await loop.run_in_executor(
                    None, lambda: weather_action(parameters=args, player=self.ui)
                )
                result = r or "Weather delivered."

            elif name == "browser_control":
                r = await loop.run_in_executor(
                    None, lambda: browser_control(parameters=args, player=self.ui)
                )
                result = r or "Done."

            elif name == "file_controller":
                r = await loop.run_in_executor(
                    None, lambda: file_controller(parameters=args, player=self.ui)
                )
                result = r or "Done."

            elif name == "send_message":
                r = await loop.run_in_executor(
                    None,
                    lambda: send_message(
                        parameters=args, response=None, player=self.ui, session_memory=None
                    ),
                )
                result = r or f"Message sent to {args.get('receiver')}."

            elif name == "reminder":
                r = await loop.run_in_executor(
                    None, lambda: reminder(parameters=args, response=None, player=self.ui)
                )
                result = r or "Reminder set."

            elif name == "youtube_video":
                r = await loop.run_in_executor(
                    None, lambda: youtube_video(parameters=args, response=None, player=self.ui)
                )
                result = r or "Done."

            elif name == "screen_process":
                threading.Thread(
                    target=screen_process,
                    kwargs={
                        "parameters": args,
                        "response": None,
                        "player": self.ui,
                        "session_memory": None,
                    },
                    daemon=True,
                ).start()
                result = "Vision module activated. Stay completely silent — vision module will speak directly."

            elif name == "computer_settings":
                r = await loop.run_in_executor(
                    None, lambda: computer_settings(parameters=args, response=None, player=self.ui)
                )
                result = r or "Done."

            elif name == "desktop_control":
                r = await loop.run_in_executor(
                    None, lambda: desktop_control(parameters=args, player=self.ui)
                )
                result = r or "Done."

            elif name == "code_helper":
                r = await loop.run_in_executor(
                    None, lambda: code_helper(parameters=args, player=self.ui, speak=self.speak)
                )
                result = r or "Done."

            elif name == "dev_agent":
                r = await loop.run_in_executor(
                    None, lambda: dev_agent(parameters=args, player=self.ui, speak=self.speak)
                )
                result = r or "Done."

            elif name == "self_dev_agent":
                r = await loop.run_in_executor(
                    None, lambda: self_dev_agent(parameters=args, player=self.ui, speak=self.speak)
                )
                result = r or "Done."

            elif name == "daily_mode":
                r = await loop.run_in_executor(
                    None, lambda: daily_mode(parameters=args, player=self.ui, speak=self.speak)
                )
                result = r or "Done."

            elif name == "agent_task":
                from agent.task_queue import TaskPriority, get_queue

                priority_map = {
                    "low": TaskPriority.LOW,
                    "normal": TaskPriority.NORMAL,
                    "high": TaskPriority.HIGH,
                }
                priority = priority_map.get(
                    args.get("priority", "normal").lower(), TaskPriority.NORMAL
                )
                task_id = get_queue().submit(
                    goal=args.get("goal", ""), priority=priority, speak=self.speak
                )
                result = f"Task started (ID: {task_id})."

            elif name == "web_search":
                r = await loop.run_in_executor(
                    None, lambda: web_search_action(parameters=args, player=self.ui)
                )
                result = r or "Done."

            elif name == "file_processor":
                if not args.get("file_path") and self.ui.current_file:
                    args["file_path"] = self.ui.current_file
                r = await loop.run_in_executor(
                    None, lambda: file_processor(parameters=args, player=self.ui, speak=self.speak)
                )
                result = r or "Done."

            elif name == "computer_control":
                r = await loop.run_in_executor(
                    None, lambda: computer_control(parameters=args, player=self.ui)
                )
                result = r or "Done."

            elif name == "game_updater":
                r = await loop.run_in_executor(
                    None, lambda: game_updater(parameters=args, player=self.ui, speak=self.speak)
                )
                result = r or "Done."

            elif name == "flight_finder":
                r = await loop.run_in_executor(
                    None, lambda: flight_finder(parameters=args, player=self.ui)
                )
                result = r or "Done."

            elif name == "gmail_manager":
                r = await loop.run_in_executor(
                    None,
                    lambda: gmail_manager(
                        parameters=args,
                        response=None,
                        player=self.ui,
                        speak=self.speak,
                        session_memory=None,
                    ),
                )
                result = r or "Done."

            elif name == "calendar_manager":
                r = await loop.run_in_executor(
                    None,
                    lambda: calendar_manager(
                        parameters=args,
                        response=None,
                        player=self.ui,
                        speak=self.speak,
                        session_memory=None,
                    ),
                )
                result = r or "Done."

            elif name == "daily_briefing":
                r = await loop.run_in_executor(
                    None,
                    lambda: daily_briefing(
                        parameters=args,
                        response=None,
                        player=self.ui,
                        speak=self.speak,
                        session_memory=None,
                    ),
                )
                result = r or "Done."

            elif name == "spotify_controller":
                r = await loop.run_in_executor(
                    None,
                    lambda: spotify_controller(
                        parameters=args,
                        response=None,
                        player=self.ui,
                        speak=self.speak,
                        session_memory=None,
                    ),
                )
                result = r or "Done."

            elif name == "obsidian_manager":
                result = self._handle_obsidian_manager(args)

            elif name == "passive_vision":
                result = self._handle_passive_vision(args)

            elif name == "semantic_search":
                result = self._handle_semantic_search(args)

            elif name == "proactive_suggestions":
                result = self._handle_proactive_suggestions(args)

            elif name == "cross_device":
                result = self._handle_cross_device(args)

            elif name == "vscode_bridge":
                result = self._handle_vscode_bridge(args)

            elif name == "roblox_controller":
                result = roblox_controller(parameters=args, player=self.ui, speak=self.speak)

            elif name == "system_diagnostics":
                result = self._run_system_diagnostics(verbose=bool(args.get("verbose", False)))

            elif name == "shutdown_jarvis":
                self.end_obsidian_conversation("Session ended by user request")
                self.ui.write_log("SYS: Shutdown requested.")
                self.speak("Goodbye, sir.")

                def _shutdown():
                    import os
                    import time

                    time.sleep(1)
                    os._exit(0)

                threading.Thread(target=_shutdown, daemon=True).start()

            elif self.plugin_manager.get_tool(name):
                r = await loop.run_in_executor(
                    None,
                    lambda: self.plugin_manager.execute_tool(
                        name,
                        args,
                        player=self.ui,
                        speak=self.speak,
                    ),
                )
                result = r or "Done."

            else:
                result = f"Unknown tool: {name}"

            # Track performance
            duration_ms = (time.perf_counter() - start_perf) * 1000
            if self.config.get("performance.track_tool_executions", True):
                try:
                    self.perf_monitor.track_tool_execution(
                        tool_name=name,
                        action=tool_action,
                        duration_ms=duration_ms,
                        success=True,
                        parameters=args,
                        result_size=len(str(result).encode("utf-8")),
                    )
                except Exception as perf_error:
                    logger.debug("Tool execution metrics skipped: %s", perf_error)
            if self.config.get("performance.track_latency", True):
                try:
                    self.perf_monitor.track_latency(
                        operation_type="tool_execution",
                        total_duration_ms=duration_ms,
                        processing_time_ms=duration_ms,
                        success=True,
                    )
                except Exception as perf_error:
                    logger.debug("Latency metrics skipped: %s", perf_error)
            self.perf_monitor.track_api_call(
                endpoint=f"tool_{name}", duration_ms=duration_ms, success=True
            )

            self.proactive.track_action(name, success=True)

            # Record tool execution for session context
            self.session_context.record_tool_execution(name, args, str(result)[:300])

            # Record in action history
            self.action_history.record_action(
                tool_name=name,
                action=tool_action,
                parameters=args,
                result=str(result)[:500],
                status=ActionStatus.SUCCESS,
            )

        except Exception as e:
            duration_ms = (time.perf_counter() - start_perf) * 1000
            if self.config.get("performance.track_tool_executions", True):
                try:
                    self.perf_monitor.track_tool_execution(
                        tool_name=name,
                        action=tool_action,
                        duration_ms=duration_ms,
                        success=False,
                        error=str(e),
                        parameters=args,
                        result_size=len(str(e).encode("utf-8")),
                    )
                except Exception as perf_error:
                    logger.debug("Tool execution metrics skipped: %s", perf_error)
            if self.config.get("performance.track_latency", True):
                try:
                    self.perf_monitor.track_latency(
                        operation_type="tool_execution",
                        total_duration_ms=duration_ms,
                        processing_time_ms=duration_ms,
                        success=False,
                        error=str(e),
                    )
                except Exception as perf_error:
                    logger.debug("Latency metrics skipped: %s", perf_error)
            self.perf_monitor.track_api_call(
                endpoint=f"tool_{name}", duration_ms=duration_ms, success=False, error=str(e)
            )
            result = f"Tool '{name}' failed: {e}"
            logger.error(f"Tool execution failed: {name} - {e}")
            traceback.print_exc()
            self.proactive.track_action(name, success=False)
            self.speak_error(name, e)

            # Record failed action in history
            self.action_history.record_action(
                tool_name=name,
                action=tool_action,
                parameters=args,
                result=str(e)[:500],
                status=ActionStatus.FAILED,
            )

        if not self.ui.muted:
            self.ui.set_state("LISTENING")
        self.hud.set_status("Listening")
        self.hud.set_action("")

        logger.info(f"Tool result: {name} → {str(result)[:80]}")
        return types.FunctionResponse(id=fc.id, name=name, response={"result": result})

    def _handle_obsidian_manager(self, args: dict[str, Any]) -> str:
        """Handle Obsidian manager tool calls."""
        action = args.get("action")

        if action == "start_tracking":
            user_input = args.get("user_input", "New conversation")
            self.start_obsidian_conversation(user_input)
            return "Conversation tracking started."

        elif action == "end_tracking":
            summary = args.get("summary", None)
            self.end_obsidian_conversation(summary)
            return "Conversation tracking ended and saved."

        elif action == "search_notes":
            query = args.get("query", "")
            results = self.obsidian_bridge.vault.search_notes(query)
            if results:
                result = f"Found {len(results)} notes:\n\n"
                for note in results:
                    result += f"- {note['title']}: {note['path']}\n"
            else:
                result = "No notes found."
            return result

        elif action == "create_person_note":
            name = args.get("name")
            information = args.get("information", {})
            if name:
                self.obsidian_bridge.vault.create_person_note(name, information)
                return f"Person note created for {name}."
            else:
                return "Name required for person note."

        elif action == "create_project_note":
            project_name = args.get("name")
            details = args.get("information", {})
            if project_name:
                self.obsidian_bridge.vault.create_project_note(project_name, details)
                return f"Project note created for {project_name}."
            else:
                return "Project name required."

        elif action == "get_all_notes":
            notes = self.obsidian_bridge.vault.get_all_notes()
            result = f"Total notes: {len(notes)}\n\n"
            for note in notes:
                result += f"- {note['title']} ({note['tags']})\n"
            return result

        else:
            return f"Unknown action: {action}"

    async def _send_realtime(self) -> None:
        """Send realtime audio data to Gemini Live."""
        last_send_time = asyncio.get_event_loop().time()
        keepalive_interval = int(self.config.get("audio.keepalive_interval", 15))
        idle_keepalive_hits = 0
        logger.debug(
            "[LiveDiag] Realtime sender started (keepalive_interval=%ss)",
            keepalive_interval,
        )

        while True:
            try:
                # Wait for audio data with timeout for keepalive
                try:
                    queue_size = self.out_queue.qsize() if self.out_queue else -1
                    logger.debug("[LiveDiag] Waiting for audio chunk (out_queue=%s)", queue_size)
                    msg = await asyncio.wait_for(self.out_queue.get(), timeout=keepalive_interval)
                    send_started = asyncio.get_event_loop().time()
                    await self.session.send_realtime_input(media=msg)
                    send_duration = asyncio.get_event_loop().time() - send_started
                    if send_duration > 0.5:
                        logger.warning(
                            "[LiveDiag] Audio send was slow: %.2fs (out_queue=%s)",
                            send_duration,
                            self.out_queue.qsize() if self.out_queue else -1,
                        )
                    last_send_time = asyncio.get_event_loop().time()
                    idle_keepalive_hits = 0
                except asyncio.TimeoutError:
                    # Send keepalive if no data for keepalive_interval seconds
                    current_time = asyncio.get_event_loop().time()
                    if current_time - last_send_time >= keepalive_interval:
                        # Empty text is easy to ignore server-side. A tiny silent
                        # audio chunk keeps the live stream active without
                        # pretending that the assistant heard real speech.
                        await self.session.send_realtime_input(media=self._build_idle_audio_frame())
                        last_send_time = current_time
                        idle_keepalive_hits += 1
                        logger.debug("Sent keepalive ping (silent audio)")
                        if idle_keepalive_hits >= 3:
                            self._log_stream_state("idle-keepalive")
            except Exception as e:
                logger.error(f"Error sending realtime input: {e}")
                # If connection is closed, break the loop to allow reconnection
                if "ConnectionClosed" in str(e) or "closed" in str(e).lower():
                    self._log_stream_state("send-closed")
                    break
                raise

    async def _listen_audio(self) -> None:
        """Listen to audio input from microphone."""
        logger.info("Microphone started")
        _ensure_audio_backend()
        loop = asyncio.get_event_loop()

        def callback(indata, frames, time_info, status):
            with self._speaking_lock:
                jarvis_speaking = self._is_speaking
            if not jarvis_speaking and not self.ui.muted:
                data = indata.tobytes()

                def safe_put():
                    try:
                        self.out_queue.put_nowait({"data": data, "mime_type": "audio/pcm"})
                    except Exception:
                        pass

                loop.call_soon_threadsafe(safe_put)

        try:
            with sd.InputStream(
                samplerate=self.send_sample_rate,
                channels=self.channels,
                dtype="int16",
                blocksize=self.chunk_size,
                callback=callback,
            ):
                logger.info("Microphone stream open")
                while True:
                    await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Microphone error: {e}")
            raise

    async def _receive_audio(self) -> None:
        """Receive audio and tool responses from Gemini Live."""
        logger.info("Audio receiver started")
        out_buf, in_buf = [], []
        messages_seen = 0

        try:
            while True:
                async for response in self.session.receive():
                    messages_seen += 1
                    if messages_seen % 20 == 0:
                        self._log_stream_state(f"receive-{messages_seen}")

                    if response.data:
                        if self._turn_done_event and self._turn_done_event.is_set():
                            self._turn_done_event.clear()
                        self.audio_in_queue.put_nowait(response.data)

                    if response.server_content:
                        sc = response.server_content

                        if sc.output_transcription and sc.output_transcription.text:
                            txt = _clean_transcript(sc.output_transcription.text)
                            if txt:
                                out_buf.append(txt)

                        if sc.input_transcription and sc.input_transcription.text:
                            txt = _clean_transcript(sc.input_transcription.text)
                            if txt:
                                in_buf.append(txt)

                        if sc.turn_complete:
                            if self._turn_done_event:
                                self._turn_done_event.set()
                                logger.debug("Turn complete event set")

                            full_in = " ".join(in_buf).strip()
                            if full_in:
                                self._note_user_input(full_in)
                                self.ui.write_log(f"You: {full_in}")
                                self.session_context.record_user_message(full_in)
                                self.memory_brain.observe(full_in, source="conversation")
                            in_buf = []

                            full_out = " ".join(out_buf).strip()
                            if full_out:
                                self.ui.write_log(f"Jarvis: {full_out}")
                                self.track_obsidian_response(full_out)
                                self.session_context.record_jarvis_response(full_out)
                            out_buf = []

                    if response.tool_call:
                        fn_responses = []
                        for fc in response.tool_call.function_calls:
                            logger.info(f"Tool call: {fc.name}")
                            fr = await self._execute_tool(fc)
                            fn_responses.append(fr)
                        await self.session.send_tool_response(function_responses=fn_responses)
                        await self._apply_pending_refresh()

                # Normal end of a turn. Gemini closes receive() after turn_complete,
                # so keep the receiver alive by starting the next turn wait loop.
                logger.debug("Gemini receive() completed a turn; waiting for the next one.")
        except Exception as e:
            logger.error(f"Audio receiver error: {e}")
            traceback.print_exc()
            raise

    async def _play_audio(self) -> None:
        """Play audio output from Gemini Live."""
        logger.info("Audio player started")
        _ensure_audio_backend()

        stream = sd.RawOutputStream(
            samplerate=self.receive_sample_rate,
            channels=self.channels,
            dtype="int16",
            blocksize=self.chunk_size,
        )
        stream.start()

        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(self.audio_in_queue.get(), timeout=0.1)
                except asyncio.TimeoutError:
                    if (
                        self._turn_done_event
                        and self._turn_done_event.is_set()
                        and self.audio_in_queue.empty()
                    ):
                        logger.debug("Turn done event set, queue empty, setting speaking to False")
                        self.set_speaking(False)
                        self._turn_done_event.clear()
                    continue
                self.set_speaking(True)
                await asyncio.to_thread(stream.write, chunk)
        except Exception as e:
            logger.error(f"Audio player error: {e}")
            raise
        finally:
            self.set_speaking(False)
            stream.stop()
            stream.close()

    async def run(self) -> None:
        """Main run loop for JarvisLive."""
        self._refresh_runtime_config()
        self._patch_live_websocket_keepalive()
        client = google.genai.Client(
            api_key=_get_api_key(), http_options={"api_version": "v1beta", "timeout": 600}
        )

        while True:
            try:
                logger.info("Connecting to Gemini Live...")
                self.ui.set_state("THINKING")
                config = self._build_config()

                async with client.aio.live.connect(model=self.live_model, config=config) as session:
                    self.session = session
                    self._loop = asyncio.get_event_loop()
                    self.audio_in_queue = asyncio.Queue()
                    self.out_queue = asyncio.Queue(maxsize=0)
                    self._turn_done_event = asyncio.Event()
                    self._context_signature = self._get_context_signature()

                    logger.info("Connected to Gemini Live")
                    self.ui.set_state("LISTENING")
                    self.ui.write_log("SYS: JARVIS online.")
                    self._log_stream_state("connected")

                    tasks = {
                        "monitor": asyncio.create_task(self._monitor_runtime_health()),
                        "send": asyncio.create_task(self._send_realtime()),
                        "mic": asyncio.create_task(self._listen_audio()),
                        "receive": asyncio.create_task(self._receive_audio()),
                        "play": asyncio.create_task(self._play_audio()),
                    }
                    try:
                        done, pending = await asyncio.wait(
                            tasks.values(),
                            return_when=asyncio.FIRST_COMPLETED,
                        )

                        for task in done:
                            if not task.cancelled() and task.exception() is not None:
                                failed_name = next(
                                    (
                                        name
                                        for name, candidate in tasks.items()
                                        if candidate is task
                                    ),
                                    "unknown",
                                )
                                self._log_task_failure(failed_name, task)
                                raise task.exception()

                        if done and not any(
                            task.exception() for task in done if not task.cancelled()
                        ):
                            completed_name = next(
                                (name for name, candidate in tasks.items() if candidate in done),
                                "unknown",
                            )
                            logger.warning("Runtime task %s completed unexpectedly", completed_name)
                            raise RuntimeError(
                                f"Runtime task {completed_name} completed unexpectedly"
                            )

                        if pending:
                            logger.warning(
                                "One or more runtime tasks stopped without an explicit error; reconnecting."
                            )
                            for task in pending:
                                stopped_name = next(
                                    (
                                        name
                                        for name, candidate in tasks.items()
                                        if candidate is task
                                    ),
                                    "unknown",
                                )
                                logger.warning("Task %s stopped unexpectedly", stopped_name)
                            raise RuntimeError("Runtime task stopped unexpectedly")
                    finally:
                        await self._shutdown_runtime_tasks(tasks)

            except Exception as e:
                logger.error(f"Connection error: {e}")
                traceback.print_exc()
                self.session_context.mark_reconnect()
                if _is_invalid_api_key_error(e):
                    self.set_speaking(False)
                    self.ui.set_state("API KEY ERROR")
                    self.ui.write_log(
                        "SYS: Gemini API key is invalid. Update config/api_keys.json or the .env file with a valid key, then restart JARVIS."
                    )
                    return
                if self.hybrid_llm.should_use_fallback(e):
                    self.ui.write_log(
                        "SYS: Gemini connection failed. Local Ollama fallback is available for supported text workflows."
                    )
            self.set_speaking(False)
            self.ui.set_state("THINKING")
            logger.info("Reconnecting in 2s...")
            await asyncio.sleep(2)
