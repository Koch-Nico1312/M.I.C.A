"""
Dynamic Action Loader for JARVIS AI Assistant
============================================
Lazy loads action modules to reduce startup time and memory footprint.
"""

import importlib
import threading
from typing import Any, Callable, Dict, Optional

from core.logger import get_logger
from core.metrics_collector import get_metrics_collector
from core.performance_flags import get_performance_flags

logger = get_logger(__name__)


class ActionLoader:
    """
    Dynamically loads action modules on demand.
    Caches loaded modules to avoid repeated imports.
    """

    def __init__(self):
        """Initialize the action loader."""
        self._action_cache: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._action_map = {
            "file_processor": "actions.file_processor",
            "flight_finder": "actions.flight_finder",
            "open_app": "actions.open_app",
            "weather_report": "actions.weather_report",
            "send_message": "actions.send_message",
            "reminder": "actions.reminder",
            "computer_settings": "actions.computer_settings",
            "screen_process": "actions.screen_processor",
            "youtube_video": "actions.youtube_video",
            "desktop_control": "actions.desktop",
            "browser_control": "actions.browser_control",
            "file_controller": "actions.file_controller",
            "code_helper": "actions.code_helper",
            "dev_agent": "actions.dev_agent",
            "web_search": "actions.web_search",
            "computer_control": "actions.computer_control",
            "game_updater": "actions.game_updater",
            "gmail_manager": "actions.gmail_manager",
            "calendar_manager": "actions.calendar_manager",
            "roblox_controller": "actions.roblox_controller",
            "spotify_controller": "actions.spotify_controller",
            "daily_briefing": "core.daily_briefing",
        }

        logger.info("Action loader initialized")

    def load_action(self, action_name: str) -> Optional[Any]:
        """
        Load an action module dynamically.

        Args:
            action_name: Name of the action to load

        Returns:
            Action module or None if not found
        """
        perf_flags = get_performance_flags()
        metrics = get_metrics_collector()

        if perf_flags.is_enabled("lazy_load_actions"):
            # Check cache first
            with self._lock:
                if action_name in self._action_cache:
                    metrics.start_operation("action_cache_hit")
                    metrics.end_operation("action_cache_hit", {"action": action_name})
                    logger.debug(f"Action cache hit: {action_name}")
                    return self._action_cache[action_name]

            # Load module dynamically
            metrics.start_operation("action_load")

            if action_name not in self._action_map:
                logger.warning(f"Unknown action: {action_name}")
                metrics.end_operation("action_load", {"action": action_name, "found": False})
                return None

            module_path = self._action_map[action_name]

            try:
                module = importlib.import_module(module_path)

                # Cache the loaded module
                with self._lock:
                    self._action_cache[action_name] = module

                metrics.end_operation(
                    "action_load", {"action": action_name, "module": module_path, "cached": True}
                )
                logger.debug(f"Loaded action: {action_name} from {module_path}")
                return module

            except ImportError as e:
                logger.error(f"Failed to load action {action_name}: {e}")
                metrics.end_operation("action_load", {"action": action_name, "error": str(e)})
                return None
        else:
            # Original behavior: import directly (already imported at top level)
            # This is a fallback when lazy loading is disabled
            try:
                module_path = self._action_map.get(action_name)
                if module_path:
                    module = importlib.import_module(module_path)
                    return module
            except ImportError as e:
                logger.error(f"Failed to load action {action_name}: {e}")
                return None

        return None

    def preload_actions(self, action_names: list = None) -> None:
        """
        Preload specific actions into cache.

        Args:
            action_names: List of action names to preload (None = preload all)
        """
        if action_names is None:
            action_names = list(self._action_map.keys())

        perf_flags = get_performance_flags()
        if not perf_flags.is_enabled("lazy_load_actions"):
            logger.info("Lazy loading disabled, skipping preload")
            return

        metrics = get_metrics_collector()
        metrics.start_operation("action_preload")

        loaded_count = 0
        for action_name in action_names:
            if self.load_action(action_name) is not None:
                loaded_count += 1

        metrics.end_operation(
            "action_preload", {"requested": len(action_names), "loaded": loaded_count}
        )
        logger.info(f"Preloaded {loaded_count}/{len(action_names)} actions")

    def clear_cache(self) -> None:
        """Clear the action cache."""
        with self._lock:
            self._action_cache.clear()
        logger.info("Action cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        with self._lock:
            return {
                "cache_size": len(self._action_cache),
                "total_actions": len(self._action_map),
                "cached_actions": list(self._action_cache.keys()),
            }


# Global instance
_action_loader: Optional[ActionLoader] = None
_action_loader_lock = threading.Lock()


def get_action_loader() -> ActionLoader:
    """
    Get the global action loader instance.

    Returns:
        ActionLoader instance
    """
    global _action_loader
    if _action_loader is None:
        with _action_loader_lock:
            if _action_loader is None:
                _action_loader = ActionLoader()
    return _action_loader
