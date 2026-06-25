import asyncio
import functools
import json
import os
import re
import sys
import threading
import traceback
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from core.action_loader import get_action_loader

# Import tool declarations from tools module
from tools import TOOL_DECLARATIONS, FEATURE_TOOL_DECLARATIONS

# Import startup configuration
from config.startup_config import (
    BASE_DIR,
    DEFAULT_CHANNELS,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_LIVE_MODEL,
    DEFAULT_RECEIVE_SAMPLE_RATE,
    DEFAULT_SEND_SAMPLE_RATE,
    get_api_key,
    load_system_prompt,
)

# Import startup initialization
from startup import (
    initialize_application,
    initialize_performance_system,
    initialize_safety_system,
)

# Initialize logging first
from core.logger import get_logger, setup_logging
from core.memory_manager import get_memory_manager
from core.metrics_collector import get_metrics_collector
from core.paths import project_path, resolve_relative_path
from core.performance_flags import get_performance_flags

os.environ["PYTHONUTF8"] = "1"
for _stream_name in ("stdout", "stderr"):
    try:
        getattr(sys, _stream_name).reconfigure(encoding="utf-8")
    except Exception:
        pass

warnings.filterwarnings(
    "ignore",
    message=r"[\s\S]*google\.generativeai[\s\S]*",
    category=FutureWarning,
)

# Setup logging
setup_logging()
logger = get_logger(__name__)

try:
    import sounddevice as sd
except ImportError:
    sd = None

import google.genai
from google.genai import types

# Lazy loading support for action modules
_action_modules_cache = {}
_action_loader = None

def _get_action_loader():
    """Get the global action loader instance."""
    global _action_loader
    if _action_loader is None:
        _action_loader = get_action_loader()
    return _action_loader

def _get_action_module(action_name: str):
    """Get action module with lazy loading support."""
    global _action_modules_cache
    perf_flags = get_performance_flags()
    
    if perf_flags.is_enabled("lazy_load_actions"):
        loader = _get_action_loader()
        module = loader.load_action(action_name)
        if module:
            _action_modules_cache[action_name] = module
        return module
    else:
        # Direct import for non-lazy mode
        if action_name in _action_modules_cache:
            return _action_modules_cache[action_name]
        
        action_map = {
            "browser_control": "actions.browser_control",
            "calendar_manager": "actions.calendar_manager",
            "code_helper": "actions.code_helper",
            "computer_control": "actions.computer_control",
            "computer_settings": "actions.computer_settings",
            "desktop_control": "actions.desktop",
            "dev_agent": "actions.dev_agent",
            "daily_mode": "actions.daily_mode",
            "file_controller": "actions.file_controller",
            "file_processor": "actions.file_processor",
            "flight_finder": "actions.flight_finder",
            "game_updater": "actions.game_updater",
            "gmail_manager": "actions.gmail_manager",
            "open_app": "actions.open_app",
            "reminder": "actions.reminder",
            "roblox_controller": "actions.roblox_controller",
            "screen_process": "actions.screen_processor",
            "self_dev_agent": "actions.self_dev_agent",
            "send_message": "actions.send_message",
            "spotify_controller": "actions.spotify_controller",
            "weather_report": "actions.weather_report",
            "web_search": "actions.web_search",
            "youtube_video": "actions.youtube_video",
        }
        
        if action_name in action_map:
            import importlib
            module = importlib.import_module(action_map[action_name])
            _action_modules_cache[action_name] = module
            return module
    return None


def __getattr__(name: str):
    """Lazy compatibility exports for action functions used by JarvisLive."""
    aliases = {
        "weather_action": ("weather_report", "weather_action"),
        "web_search_action": ("web_search", "web_search"),
        "screen_process": ("screen_process", "screen_process"),
    }
    action_name, attr_name = aliases.get(name, (name, name))
    module = _get_action_module(action_name)
    if module and hasattr(module, attr_name):
        return getattr(module, attr_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
from config.config_loader import get_config
from core.action_history import get_action_history
from core.approval_flow import get_approval_flow
from core.background_task_manager import get_background_task_manager
from core.cross_device import get_cross_device
from core.daily_briefing import daily_briefing
from core.first_run_wizard import ensure_gemini_api_key
from core.healthcheck import build_runtime_report, format_runtime_report
from core.hud_overlay import get_hud_manager
from core.jarvis_live import JarvisLive
from core.llm_fallback import get_hybrid_llm
from core.local_analyzer import get_local_analyzer
from core.morning_routine import RoutineConfig, RoutineMode, get_morning_routine
from core.multimodal_context import get_multimodal_context
from core.passive_vision import get_passive_vision
from core.performance_monitor import get_performance_monitor
from core.performance_tracker import get_performance_tracker
from core.permission_profiles import (
    PermissionLevel,
    disable_action,
    enable_action,
    get_disabled_actions,
    get_tool_metadata,
)
from core.plugin_system import get_plugin_manager
from core.proactive_suggestions import get_proactive_suggestions
from core.semantic_search import get_semantic_search
from core.session_manager import get_session_manager
from core.setup_flow import get_setup_flow, run_setup_check
from core.voice_emotion import get_emotion_analyzer
from core.vscode_bridge import get_vscode_bridge
from core.workflow_engine import get_workflow_engine
from memory.hybrid_retrieval import get_hybrid_retrieval
from memory.memory_backup import get_backup_manager
from memory.memory_manager import (
    MEMORY_PATH,
    format_memory_for_prompt,
    load_memory,
    update_memory,
)
from memory.obsidian_vault import get_obsidian_bridge
from ui_bridge import JarvisUI

# Lazy loading support for tool declarations
_tool_declarations_cache = None
_tool_declarations_lock = threading.Lock()

# Action loader for lazy loading action modules
_action_loader = None


def get_tool_declarations() -> List[Dict[str, Any]]:
    """
    Get tool declarations with optional lazy loading.
    When lazy_tool_declarations flag is enabled, declarations are cached after first load.
    """
    perf_flags = get_performance_flags()
    metrics = get_metrics_collector()

    if perf_flags.is_enabled("lazy_tool_declarations"):
        return _get_tool_declarations_lazy()

    # Return static declarations if lazy loading is disabled
    return TOOL_DECLARATIONS


# Update references to use the imported functions
_get_api_key = get_api_key
_load_system_prompt = load_system_prompt


def _get_action_loader():
    """Get the global action loader instance."""
    global _action_loader
    if _action_loader is None:
        _action_loader = get_action_loader()
    return _action_loader


def _get_tool_declarations_lazy() -> List[Dict[str, Any]]:
    """
    Lazy load tool declarations with caching.
    """
    global _tool_declarations_cache
    metrics = get_metrics_collector()
    metrics.start_operation("get_tool_declarations_lazy")

    with _tool_declarations_lock:
        if _tool_declarations_cache is not None:
            metrics.end_operation("get_tool_declarations_lazy", {"cached": True})
            return _tool_declarations_cache

        # Load declarations on first access
        _tool_declarations_cache = TOOL_DECLARATIONS.copy()
        metrics.end_operation("get_tool_declarations_lazy", {"cached": False, "loaded": True})
        logger.debug("Tool declarations loaded and cached")

    return _tool_declarations_cache


_CTRL_RE = re.compile(r"<ctrl\d+>", re.IGNORECASE)


# Tool declarations have been moved to tools/tool_declarations.py
# and are imported at the top of this file


def _ensure_audio_backend() -> None:
    if sd is None:
        raise RuntimeError(
            "sounddevice is not installed. Install dependencies with "
            "'pip install -r requirements.txt'."
        )


def _is_invalid_api_key_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return "api key not valid" in text or "invalid api key" in text


def _clean_transcript(text: str) -> str:
    text = _CTRL_RE.sub("", text)
    text = re.sub(r"[\x00-\x08\x0b-\x1f]", "", text)
    return text.strip()


# TOOL_DECLARATIONS and FEATURE_TOOL_DECLARATIONS moved to tools/tool_declarations.py
# JarvisLive class has been moved to core/jarvis_live.py


def main() -> None:
    """Main entry point for JARVIS AI Assistant."""
    # Check if GUI mode should be used (before UI initialization)
    use_gui = "--cli" not in sys.argv
    
    # Create QApplication in main thread BEFORE any Qt operations if using GUI
    if use_gui:
        try:
            from PyQt6.QtWidgets import QApplication
            # Check if QApplication already exists
            if QApplication.instance() is None:
                app = QApplication(sys.argv)
                app.setApplicationName("JARVIS")
        except Exception as e:
            logger.warning(f"Failed to create QApplication: {e}, falling back to CLI mode")
            use_gui = False

    if not ensure_gemini_api_key(use_gui=use_gui):
        logger.error("JARVIS cannot start without a valid Gemini API key.")
        return
    
    # Initialize application and UI (pass use_gui to ensure correct UI type)
    _, ui = initialize_application(use_gui)

    # Load configuration
    config = get_config()

    # Initialize safety and approval system
    approval_flow, action_history = initialize_safety_system()

    # Run setup check on first start (optional)
    setup_flow = get_setup_flow(BASE_DIR)
    try:
        # Only run setup check if config file doesn't exist or is new
        config_file = BASE_DIR / "config.yaml"
        if not config_file.exists() or config_file.stat().st_size < 100:
            logger.info("Running first-time setup check...")
            setup_report = setup_flow.run_all_checks()
            if setup_report.overall_status.value in ["failed", "warning"]:
                logger.warning(
                    "Setup check found issues:\n" + setup_flow.format_report(verbose=True)
                )
            else:
                logger.info("Setup check passed")
    except Exception as e:
        logger.warning(f"Setup check failed: {e}")

    # Initialize performance tracking
    perf_tracker, perf_monitor = initialize_performance_system(_get_action_loader)

    # Initialize workflow engine
    if config.get("workflow.enabled", True):
        workflow_engine = get_workflow_engine()
        max_concurrent = config.get("workflow.max_concurrent_workflows", 2)
        workflow_engine.max_concurrent_workflows = max_concurrent

        # Configure persistence
        if config.get("workflow.persistence_enabled", True):
            persistence_dir = config.get(
                "workflow.persistence_dir",
                str(project_path("data", "workflows")),
            )
            workflow_engine.persistence_dir = resolve_relative_path(persistence_dir)
            workflow_engine.persistence_dir.mkdir(parents=True, exist_ok=True)
            workflow_engine.persistence_file = (
                workflow_engine.persistence_dir / "workflows.json"
            )

        # Start executor
        workflow_engine.start_executor()

        # Auto-cleanup old workflows
        cleanup_hours = config.get("workflow.auto_cleanup_hours", 168)
        workflow_engine.cleanup_old_workflows(max_age_hours=cleanup_hours)

        logger.info("Workflow engine initialized")
    else:
        logger.info("Workflow engine disabled by configuration")

    # Initialize local analyzer
    if config.get("local_analysis.enabled", True):
        local_analyzer = get_local_analyzer()
        cache_size = config.get("local_analysis.max_cache_size", 1000)
        local_analyzer.max_cache_size = cache_size
        logger.info("Local analyzer initialized")
    else:
        logger.info("Local analyzer disabled by configuration")

    # Initialize morning routine
    if config.get("morning_routine.enabled", False):
        mode_str = config.get("morning_routine.mode", "manual")
        mode = RoutineMode(mode_str) if mode_str else RoutineMode.MANUAL

        routine_config = RoutineConfig(
            mode=mode,
            reminder_time=config.get("morning_routine.reminder_time", "08:00"),
            reminder_window_minutes=config.get("morning_routine.reminder_window_minutes", 60),
            photo_directory=config.get("morning_routine.photo_directory") or None,
            auto_analyze=config.get("morning_routine.auto_analyze", True),
            send_reminder_if_missed=config.get("morning_routine.send_reminder_if_missed", True),
            reminder_delay_minutes=config.get("morning_routine.reminder_delay_minutes", 120),
        )

        morning_routine = get_morning_routine(routine_config)
        morning_routine.start_monitoring()

        logger.info(f"Morning routine initialized (mode: {mode.value})")
    else:
        logger.info("Morning routine disabled by configuration")

    # Initialize hybrid retrieval
    if config.get("memory_retrieval.enabled", True):
        hybrid_retrieval = get_hybrid_retrieval()
        hybrid_retrieval.semantic_weight = config.get("memory_retrieval.semantic_weight", 0.4)
        hybrid_retrieval.keyword_weight = config.get("memory_retrieval.keyword_weight", 0.3)
        hybrid_retrieval.time_weight = config.get("memory_retrieval.time_weight", 0.2)
        hybrid_retrieval.confidence_weight = config.get(
            "memory_retrieval.confidence_weight", 0.1
        )
        hybrid_retrieval.max_results = config.get("memory_retrieval.max_results", 10)
        hybrid_retrieval.min_relevance_threshold = config.get(
            "memory_retrieval.min_relevance_threshold", 0.3
        )
        logger.info("Hybrid retrieval initialized")
    else:
        logger.info("Hybrid retrieval disabled by configuration")

    # Initialize multimodal context
    multimodal_context = get_multimodal_context()
    logger.info("Multimodal context processor initialized")

    # Initialize memory backup manager
    backup_manager = get_backup_manager()
    backup_manager.start_automatic_backup()
    logger.info("Memory backup system started")

    # Initialize performance monitoring
    perf_monitor = get_performance_monitor()
    perf_monitor.start_monitoring()
    logger.info("Performance monitoring started")

    # Verify memory integrity
    is_valid, message = backup_manager.verify_memory_integrity()
    if not is_valid:
        logger.warning(f"Memory integrity check failed: {message}")
        logger.info("Attempting emergency recovery...")
        if backup_manager.emergency_recovery():
            logger.info("Emergency recovery successful")
        else:
            logger.error("Emergency recovery failed")

    if use_gui:
        # GUI mode: use threading and mainloop
        def runner():
            ui.wait_for_api_key()
            jarvis = JarvisLive(ui)
            try:
                asyncio.run(jarvis.run())
            except KeyboardInterrupt:
                logger.info("Shutting down...")
            finally:
                # Cleanup
                get_session_manager().finalize_session()
                backup_manager.stop_automatic_backup()
                perf_monitor.stop_monitoring()
                logger.info("Systems shutdown complete")

        threading.Thread(target=runner, daemon=True).start()
        ui.root.mainloop()
    else:
        # CLI mode: run directly
        print()
        print("JARVIS is ready in CLI mode!")
        print("Press Ctrl+C to exit")
        print("=" * 60)
        print()

        jarvis = JarvisLive(ui)
        try:
            asyncio.run(jarvis.run())
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            print()
            print("JARVIS shutting down...")
        finally:
            # Cleanup
            get_session_manager().finalize_session()
            backup_manager.stop_automatic_backup()
            perf_monitor.stop_monitoring()
            logger.info("Systems shutdown complete")
            print("Shutdown complete.")


if __name__ == "__main__":
    main()
