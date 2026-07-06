"""
Memory Manager for M.I.C.A AI Assistant
=======================================
Manages memory footprint with limits and garbage collection.
"""

import gc
import threading
import weakref
from collections import OrderedDict
from typing import Any, Dict, Optional

from core.logger import get_logger
from core.metrics_collector import get_metrics_collector
from core.performance_flags import get_performance_flags

logger = get_logger(__name__)


class MemoryManager:
    """
    Manages memory footprint with limits and garbage collection.
    """

    def __init__(self, max_memory_mb: int = 512, gc_interval_seconds: int = 60):
        """
        Initialize the memory manager.

        Args:
            max_memory_mb: Maximum memory usage in MB
            gc_interval_seconds: Interval between garbage collection runs
        """
        self.max_memory_mb = max_memory_mb
        self.gc_interval_seconds = gc_interval_seconds
        self._weak_refs: Dict[str, weakref.ref] = {}
        self._cache: OrderedDict = OrderedDict()
        self._max_cache_size = 1000
        self._lock = threading.Lock()
        self._gc_thread: Optional[threading.Thread] = None
        self._stop_gc = threading.Event()

        logger.info(f"Memory manager initialized (max_memory: {max_memory_mb}MB)")

    def track_object(self, key: str, obj: Any) -> None:
        """
        Track an object with a weak reference.

        Args:
            key: Key to identify the object
            obj: Object to track
        """
        perf_flags = get_performance_flags()
        if not perf_flags.is_enabled("reduce_memory_footprint"):
            return

        with self._lock:
            self._weak_refs[key] = weakref.ref(obj)
            logger.debug(f"Tracking object with weak reference: {key}")

    def cache_object(self, key: str, obj: Any) -> None:
        """
        Cache an object with LRU eviction.

        Args:
            key: Key for the object
            obj: Object to cache
        """
        perf_flags = get_performance_flags()
        if not perf_flags.is_enabled("reduce_memory_footprint"):
            return

        metrics = get_metrics_collector()
        metrics.start_operation("memory_cache_set")

        with self._lock:
            # Evict oldest if cache is full
            if len(self._cache) >= self._max_cache_size:
                self._cache.popitem(last=False)
                metrics.record_custom("cache_eviction", 1)

            self._cache[key] = obj

        metrics.end_operation(
            "memory_cache_set", {"cache_size": len(self._cache), "max_size": self._max_cache_size}
        )

    def get_cached(self, key: str) -> Optional[Any]:
        """
        Get a cached object.

        Args:
            key: Key for the object

        Returns:
            Cached object or None if not found
        """
        perf_flags = get_performance_flags()
        if not perf_flags.is_enabled("reduce_memory_footprint"):
            return None

        with self._lock:
            if key in self._cache:
                # Move to end (most recently used)
                obj = self._cache.pop(key)
                self._cache[key] = obj
                return obj

        return None

    def clear_cache(self) -> None:
        """Clear the object cache."""
        with self._lock:
            self._cache.clear()
        logger.info("Memory cache cleared")

    def get_memory_usage_mb(self) -> float:
        """
        Get current memory usage in MB.

        Returns:
            Memory usage in MB
        """
        try:
            import psutil

            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            return 0.0

    def enforce_memory_limit(self) -> bool:
        """
        Enforce memory limit by clearing cache and triggering GC.

        Returns:
            True if memory limit was exceeded and action was taken
        """
        perf_flags = get_performance_flags()
        if not perf_flags.is_enabled("reduce_memory_footprint"):
            return False

        metrics = get_metrics_collector()
        metrics.start_operation("memory_limit_check")

        current_memory = self.get_memory_usage_mb()

        if current_memory > self.max_memory_mb:
            logger.warning(
                f"Memory limit exceeded: {current_memory:.2f}MB > {self.max_memory_mb}MB"
            )

            # Clear cache
            with self._lock:
                cache_size = len(self._cache)
                self._cache.clear()

            # Trigger garbage collection
            gc.collect()

            metrics.end_operation(
                "memory_limit_check",
                {
                    "exceeded": True,
                    "current_memory_mb": current_memory,
                    "cache_cleared": cache_size,
                },
            )

            logger.info(f"Cleared cache and triggered GC (freed {cache_size} objects)")
            return True

        metrics.end_operation(
            "memory_limit_check", {"exceeded": False, "current_memory_mb": current_memory}
        )
        return False

    def start_gc_thread(self) -> None:
        """Start the background garbage collection thread."""
        perf_flags = get_performance_flags()
        if not perf_flags.is_enabled("reduce_memory_footprint"):
            return

        if self._gc_thread is not None and self._gc_thread.is_alive():
            return

        self._stop_gc.clear()
        self._gc_thread = threading.Thread(target=self._gc_loop, daemon=True)
        self._gc_thread.start()
        logger.info("Memory GC thread started")

    def stop_gc_thread(self) -> None:
        """Stop the background garbage collection thread."""
        self._stop_gc.set()
        if self._gc_thread:
            self._gc_thread.join(timeout=5)
        logger.info("Memory GC thread stopped")

    def _gc_loop(self) -> None:
        """Background garbage collection loop."""
        while not self._stop_gc.wait(self.gc_interval_seconds):
            try:
                metrics = get_metrics_collector()
                metrics.start_operation("periodic_gc")

                # Check memory limit
                self.enforce_memory_limit()

                # Periodic GC
                collected = gc.collect()

                metrics.end_operation(
                    "periodic_gc",
                    {"objects_collected": collected, "memory_mb": self.get_memory_usage_mb()},
                )

                logger.debug(f"Periodic GC collected {collected} objects")

            except Exception as e:
                logger.error(f"GC loop error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get memory manager statistics.

        Returns:
            Dictionary with statistics
        """
        with self._lock:
            return {
                "max_memory_mb": self.max_memory_mb,
                "current_memory_mb": self.get_memory_usage_mb(),
                "cache_size": len(self._cache),
                "max_cache_size": self._max_cache_size,
                "weak_refs_count": len(self._weak_refs),
                "gc_thread_running": self._gc_thread is not None and self._gc_thread.is_alive(),
            }


# Global instance
_memory_manager: Optional[MemoryManager] = None
_memory_manager_lock = threading.Lock()


def get_memory_manager() -> MemoryManager:
    """
    Get the global memory manager instance.

    Returns:
        MemoryManager instance
    """
    global _memory_manager
    if _memory_manager is None:
        with _memory_manager_lock:
            if _memory_manager is None:
                from config.config_loader import get_config

                config = get_config()
                _memory_manager = MemoryManager(
                    max_memory_mb=int(config.get("system.max_memory_mb", 512)),
                    gc_interval_seconds=int(
                        config.get("performance.memory_gc_interval_seconds", 60)
                    ),
                )
                _memory_manager._max_cache_size = int(
                    config.get("performance.memory_cache_max_size", 5000)
                )
    return _memory_manager
