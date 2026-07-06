"""
Performance Feature Flags for M.I.C.A AI Assistant
==================================================
Manages feature flags for gradual rollout of performance optimizations.
"""

from typing import Any, Dict

from config.config_loader import get_config


class PerformanceFlags:
    """
    Manages performance optimization feature flags.
    All flags are configurable via config.yaml under performance.flags section.
    """

    def __init__(self):
        self._config = get_config()
        self._flags = self._load_flags()

    def _load_flags(self) -> Dict[str, bool]:
        """Load feature flags from configuration."""
        flags_config = self._config.get("performance.flags", {})

        # Default flags (all disabled by default for safe rollout)
        default_flags = {
            # Phase 1: Quick Wins
            "cache_system_prompt": False,
            "lazy_tool_declarations": False,
            "optimized_audio_chunks": False,
            "cache_api_responses": False,
            "preload_embedding_model": False,
            "debounce_ui_updates": False,
            "async_logging": False,
            # Phase 2: Medium-Impact
            "lazy_load_actions": False,
            "connection_pooling": False,
            "aggressive_compression": False,
            "db_connection_pooling": False,
            "vector_db_cache": False,
            "batch_screen_processing": False,
            "event_file_watching": False,
            # Phase 3: Complex Changes
            "reduce_memory_footprint": False,
            "parallel_tool_execution": False,
            "async_workflow_engine": False,
            "precompute_queries": False,
            "response_streaming": False,
            "async_ui_server": False,
        }

        # Merge with config
        for flag_name, default_value in default_flags.items():
            if flag_name in flags_config:
                default_flags[flag_name] = bool(flags_config[flag_name])

        return default_flags

    def is_enabled(self, flag_name: str) -> bool:
        """
        Check if a performance flag is enabled.

        Args:
            flag_name: Name of the flag to check

        Returns:
            True if flag is enabled, False otherwise
        """
        return self._flags.get(flag_name, False)

    def enable(self, flag_name: str) -> None:
        """
        Enable a performance flag.

        Args:
            flag_name: Name of the flag to enable
        """
        if flag_name in self._flags:
            self._flags[flag_name] = True
        else:
            raise ValueError(f"Unknown performance flag: {flag_name}")

    def disable(self, flag_name: str) -> None:
        """
        Disable a performance flag.

        Args:
            flag_name: Name of the flag to disable
        """
        if flag_name in self._flags:
            self._flags[flag_name] = False
        else:
            raise ValueError(f"Unknown performance flag: {flag_name}")

    def get_all_flags(self) -> Dict[str, bool]:
        """
        Get all performance flags and their current state.

        Returns:
            Dictionary of all flags
        """
        return self._flags.copy()

    def reload(self) -> None:
        """Reload flags from configuration."""
        self._config = get_config()
        self._flags = self._load_flags()


# Global instance
_performance_flags: PerformanceFlags = None


def get_performance_flags() -> PerformanceFlags:
    """
    Get the global performance flags instance.

    Returns:
        PerformanceFlags instance
    """
    global _performance_flags
    if _performance_flags is None:
        _performance_flags = PerformanceFlags()
    return _performance_flags
