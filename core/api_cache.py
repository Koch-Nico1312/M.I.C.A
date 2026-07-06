"""
API Response Cache for M.I.C.A AI Assistant
==========================================
Caches Gemini API responses to reduce redundant calls.
"""

import hashlib
import json
import threading
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from core.logger import get_logger
from core.metrics_collector import get_metrics_collector
from core.performance_flags import get_performance_flags

logger = get_logger(__name__)


class APICache:
    """
    Caches API responses with TTL-based invalidation.
    Uses hash-based keys for prompt matching.
    """

    def __init__(
        self,
        ttl_minutes: int = 10,
        max_size: int = 1000,
        max_bytes: Optional[int] = None,
    ):
        """
        Initialize the API cache.

        Args:
            ttl_minutes: Time-to-live for cache entries in minutes
            max_size: Maximum number of entries in cache
            max_bytes: Optional memory budget for cached response payloads
        """
        self.ttl = timedelta(minutes=ttl_minutes)
        self.max_size = max_size
        self.max_bytes = max_bytes
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._cache_bytes = 0
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

        logger.info(
            "API cache initialized "
            f"(TTL: {ttl_minutes}min, max_size: {max_size}, max_bytes: {max_bytes})"
        )

    def _estimate_response_size(self, response: Dict[str, Any]) -> int:
        """Estimate serialized payload size for byte-budget eviction."""
        try:
            return len(json.dumps(response, ensure_ascii=False, separators=(",", ":")).encode())
        except (TypeError, ValueError):
            return len(str(response).encode())

    def _drop_entry(self, key: str) -> None:
        entry = self._cache.pop(key, None)
        if entry:
            self._cache_bytes = max(0, self._cache_bytes - int(entry.get("size_bytes", 0)))

    def _enforce_limits(self) -> None:
        while self._cache and len(self._cache) > self.max_size:
            evicted_key, evicted_entry = self._cache.popitem(last=False)
            self._cache_bytes = max(
                0, self._cache_bytes - int(evicted_entry.get("size_bytes", 0))
            )
            logger.debug(f"API cache evicted LRU entry: {evicted_key[:16]}...")

        while self.max_bytes and self._cache and self._cache_bytes > self.max_bytes:
            evicted_key, evicted_entry = self._cache.popitem(last=False)
            self._cache_bytes = max(
                0, self._cache_bytes - int(evicted_entry.get("size_bytes", 0))
            )
            logger.debug(f"API cache evicted byte-budget entry: {evicted_key[:16]}...")

    def _generate_key(self, prompt: str, model: str = None, **kwargs) -> str:
        """
        Generate a cache key from prompt and parameters.

        Args:
            prompt: The prompt text
            model: Model name (optional)
            **kwargs: Additional parameters

        Returns:
            Hash string for cache key
        """
        # Create a deterministic string representation
        key_data = {
            "prompt": prompt,
            "model": model,
            "kwargs": sorted(kwargs.items()) if kwargs else [],
        }
        key_string = json.dumps(key_data, sort_keys=True)

        # Hash the key string
        return hashlib.sha256(key_string.encode()).hexdigest()

    def get(self, prompt: str, model: str = None, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Get cached response for a prompt.

        Args:
            prompt: The prompt text
            model: Model name (optional)
            **kwargs: Additional parameters

        Returns:
            Cached response or None if not found/expired
        """
        perf_flags = get_performance_flags()
        if not perf_flags.is_enabled("cache_api_responses"):
            return None

        metrics = get_metrics_collector()
        metrics.start_operation("api_cache_get")

        key = self._generate_key(prompt, model, **kwargs)

        with self._lock:
            if key in self._cache:
                entry = self._cache[key]

                # Check if entry is expired
                if datetime.now() - entry["timestamp"] < self.ttl:
                    self._cache.move_to_end(key)
                    self._hits += 1
                    metrics.end_operation(
                        "api_cache_get",
                        {
                            "hit": True,
                            "age_seconds": (datetime.now() - entry["timestamp"]).total_seconds(),
                        },
                    )
                    logger.debug(f"API cache hit for key: {key[:16]}...")
                    return entry["response"]
                else:
                    # Remove expired entry
                    self._drop_entry(key)
                    logger.debug(f"API cache entry expired: {key[:16]}...")

        self._misses += 1
        metrics.end_operation("api_cache_get", {"hit": False})
        return None

    def set(self, prompt: str, response: Dict[str, Any], model: str = None, **kwargs) -> None:
        """
        Cache a response for a prompt.

        Args:
            prompt: The prompt text
            response: The API response to cache
            model: Model name (optional)
            **kwargs: Additional parameters
        """
        perf_flags = get_performance_flags()
        if not perf_flags.is_enabled("cache_api_responses"):
            return

        metrics = get_metrics_collector()
        metrics.start_operation("api_cache_set")

        key = self._generate_key(prompt, model, **kwargs)
        size_bytes = self._estimate_response_size(response)

        if self.max_bytes and size_bytes > self.max_bytes:
            metrics.end_operation(
                "api_cache_set",
                {
                    "cache_size": len(self._cache),
                    "prompt_length": len(prompt),
                    "skipped": "oversized",
                    "size_bytes": size_bytes,
                },
            )
            logger.debug(f"API cache skipped oversized response: {key[:16]}...")
            return

        with self._lock:
            if key in self._cache:
                self._drop_entry(key)

            self._cache[key] = {
                "response": response,
                "timestamp": datetime.now(),
                "prompt_length": len(prompt),
                "model": model,
                "size_bytes": size_bytes,
            }
            self._cache_bytes += size_bytes
            self._enforce_limits()

        metrics.end_operation(
            "api_cache_set",
            {
                "cache_size": len(self._cache),
                "cache_bytes": self._cache_bytes,
                "prompt_length": len(prompt),
            },
        )
        logger.debug(f"API cache set for key: {key[:16]}...")

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._cache_bytes = 0
            self._hits = 0
            self._misses = 0
        logger.info("API cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0

            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "size_bytes": self._cache_bytes,
                "size_mb": round(self._cache_bytes / (1024 * 1024), 3),
                "max_bytes": self.max_bytes,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate_percent": round(hit_rate, 2),
                "ttl_minutes": self.ttl.total_seconds() / 60,
            }

    def cleanup_expired(self) -> int:
        """
        Remove expired entries from cache.

        Returns:
            Number of entries removed
        """
        metrics = get_metrics_collector()
        metrics.start_operation("api_cache_cleanup")

        with self._lock:
            current_time = datetime.now()
            expired_keys = [
                key
                for key, entry in self._cache.items()
                if current_time - entry["timestamp"] >= self.ttl
            ]

            for key in expired_keys:
                self._drop_entry(key)

        metrics.end_operation("api_cache_cleanup", {"removed": len(expired_keys)})
        if expired_keys:
            logger.info(f"API cache cleanup: removed {len(expired_keys)} expired entries")

        return len(expired_keys)


# Global instance
_api_cache: Optional[APICache] = None
_api_cache_lock = threading.Lock()


def get_api_cache() -> APICache:
    """
    Get the global API cache instance.

    Returns:
        APICache instance
    """
    global _api_cache
    if _api_cache is None:
        with _api_cache_lock:
            if _api_cache is None:
                from config.config_loader import get_config

                config = get_config()
                _api_cache = APICache(
                    ttl_minutes=int(config.get("performance.api_cache_ttl_minutes", 10)),
                    max_size=int(config.get("performance.api_cache_max_size", 1000)),
                    max_bytes=int(config.get("performance.api_cache_max_bytes_mb", 128))
                    * 1024
                    * 1024,
                )
    return _api_cache
