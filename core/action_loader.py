"""
Dynamic Action Loader for JARVIS AI Assistant
============================================
Lazy loads action modules to reduce startup time and memory footprint.
"""

import importlib
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from core.logger import get_logger
from core.metrics_collector import get_metrics_collector
from core.performance_flags import get_performance_flags
from tools import FEATURE_TOOL_DECLARATIONS, TOOL_DECLARATIONS

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
        self.lazy_load = get_performance_flags().is_enabled("lazy_load_actions")
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
            "self_dev_agent": "actions.self_dev_agent",
            "daily_mode": "actions.daily_mode",
            "web_search": "actions.web_search",
            "computer_control": "actions.computer_control",
            "game_updater": "actions.game_updater",
            "gmail_manager": "actions.gmail_manager",
            "calendar_manager": "actions.calendar_manager",
            "contact_manager": "actions.contact_manager",
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
        metrics = get_metrics_collector()

        if self.lazy_load:
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

            module_path = self._action_map.get(action_name, f"actions.{action_name}")

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
                raise
        else:
            # Original behavior: import directly (already imported at top level)
            # This is a fallback when lazy loading is disabled
            try:
                module_path = self._action_map.get(action_name, f"actions.{action_name}")
                module = importlib.import_module(module_path)
                with self._lock:
                    self._action_cache[action_name] = module
                return module
            except ImportError as e:
                logger.error(f"Failed to load action {action_name}: {e}")
                raise

        return None

    def load_actions(self, action_names: list[str] | None = None) -> Dict[str, Any]:
        """
        Load multiple action modules and return the successfully loaded modules.

        This preserves the older public ActionLoader API while still using the
        lazy-loading cache internally.
        """
        if action_names is None:
            action_names = list(self._action_map.keys())

        loaded: Dict[str, Any] = {}
        for action_name in action_names:
            try:
                module = self.load_action(action_name)
            except ImportError:
                logger.warning(f"Skipping unavailable action: {action_name}")
                continue
            if module is not None:
                loaded[action_name] = module
        return loaded

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

    def get_tool_declarations(self) -> list[dict[str, Any]]:
        """
        Return available tool declarations.

        Static declarations are the source of truth for built-in tools; module
        declarations are included when present for plugin-like action modules.
        """
        declarations: list[dict[str, Any]] = []
        seen: set[str] = set()

        for declaration in [*TOOL_DECLARATIONS, *FEATURE_TOOL_DECLARATIONS]:
            name = declaration.get("name")
            if name and name not in seen:
                declarations.append(declaration)
                seen.add(name)

        for action_name in self._action_map:
            try:
                module = self.load_action(action_name)
            except ImportError:
                continue
            declaration = getattr(module, "TOOL_DECLARATION", None)
            if isinstance(declaration, dict):
                name = declaration.get("name")
                if name and name not in seen:
                    declarations.append(declaration)
                    seen.add(name)

        return declarations

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
