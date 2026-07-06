"""
Startup configuration for M.I.C.A AI Assistant.

This module handles configuration loading and initialization constants
used during application startup.
"""

import json
import threading
from datetime import datetime, timedelta

from config.config_loader import get_config
from core.metrics_collector import get_metrics_collector
from core.paths import project_path, resolve_project_root
from core.performance_flags import get_performance_flags

# Base directory and paths
BASE_DIR = resolve_project_root()
API_CONFIG_PATH = project_path("config", "api_keys.json")
PROMPT_PATH = project_path("core", "prompt.txt")

# Default configuration values
DEFAULT_LIVE_MODEL = "models/gemini-2.5-flash-native-audio-preview-12-2025"
DEFAULT_CHANNELS = 1
DEFAULT_SEND_SAMPLE_RATE = 16000
DEFAULT_RECEIVE_SAMPLE_RATE = 24000
DEFAULT_CHUNK_SIZE = 1024
STARTUP_DEFAULTS = {
    # Keep boot predictable and fast unless the user explicitly enables heavier services.
    "performance.enabled": True,
    "performance.resource_monitoring": False,
    "performance.background_tasks_enabled": False,
    "performance.background_workers": 2,
    "performance.preload_critical_actions": False,
    "performance.flags.lazy_load_actions": True,
    "performance.flags.reduce_memory_footprint": False,
    "performance.slow_operation_threshold_ms": 2000,
    "performance.alert_threshold_ms": 5000,
    "security.permission_profile": "normal",
    "security.permission_level": "normal",
    "security.confirmation_medium_risk": False,
    "security.confirmation_high_risk": True,
    "security.disabled_actions": [],
    "security.action_history_enabled": True,
    "security.action_history_max_size": 1000,
}


def get_startup_setting(key: str, default=None):
    """Read startup config with conservative defaults for missing keys."""
    fallback = STARTUP_DEFAULTS.get(key, default)
    return get_config().get(key, fallback)


def get_startup_defaults() -> dict:
    """Return a copy of the effective startup defaults for health/API surfaces."""
    return dict(STARTUP_DEFAULTS)


def get_api_key() -> str:
    """
    Get the Gemini API key from configuration or fallback to api_keys.json.
    
    Returns:
        str: The API key
    """
    config = get_config()
    api_key = str(config.get_api_key("gemini") or "").strip()
    if api_key:
        return api_key

    with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]


# System prompt caching
_system_prompt_cache = {"prompt": None, "timestamp": None, "file_mtime": None}
_system_prompt_cache_ttl = timedelta(minutes=5)
_system_prompt_cache_lock = threading.Lock()


def load_system_prompt() -> str:
    """
    Load the system prompt from file or return default.
    With caching enabled (via feature flag), uses LRU cache with 5-minute TTL.
    
    Returns:
        str: The system prompt content
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
            "You are M.I.C.A (Modular Intern Computer Assistant), a calm, personal, local-first assistant. "
            "Be concise, direct, and always use the provided tools to complete tasks. "
            "Never simulate or guess results — always call the appropriate tool."
        )


def _load_system_prompt_cached() -> str:
    """
    Load system prompt with LRU cache and 5-minute TTL.
    Cache is invalidated if file is modified.
    
    Returns:
        str: The system prompt content
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
            except Exception:
                # Return cached version if available, otherwise default
                if _system_prompt_cache["prompt"]:
                    metrics.end_operation(
                        "load_system_prompt_cached", {"cached": True, "error": True}
                    )
                    return _system_prompt_cache["prompt"]
                metrics.end_operation("load_system_prompt_cached", {"cached": False, "error": True})
                return (
                    "You are M.I.C.A (Modular Intern Computer Assistant), a calm, personal, local-first assistant. "
                    "Be concise, direct, and always use the provided tools to complete tasks. "
                    "Never simulate or guess results — always call the appropriate tool."
                )
        else:
            metrics.end_operation("load_system_prompt_cached", {"cached": True, "refreshed": False})

    return _system_prompt_cache["prompt"]
