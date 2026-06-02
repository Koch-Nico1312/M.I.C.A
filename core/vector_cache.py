"""
Vector DB Cache for JARVIS AI Assistant
=======================================
Caches ChromaDB query results to reduce redundant vector searches.
"""

import hashlib
import json
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from core.logger import get_logger
from core.metrics_collector import get_metrics_collector
from core.performance_flags import get_performance_flags

logger = get_logger(__name__)

try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class VectorCache:
    """
    Caches vector database query results with TTL-based invalidation.
    Uses Redis if available, otherwise falls back to in-memory cache.
    """

    def __init__(self, ttl_hours: int = 1, max_size: int = 1000):
        """
        Initialize the vector cache.

        Args:
            ttl_hours: Time-to-live for cache entries in hours
            max_size: Maximum number of entries in cache (for in-memory fallback)
        """
        self.ttl = timedelta(hours=ttl_hours)
        self.max_size = max_size
        self._redis_client = None
        self._memory_cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

        # Try to connect to Redis
        if REDIS_AVAILABLE:
            try:
                self._redis_client = redis.Redis(
                    host="localhost", port=6379, db=0, decode_responses=True
                )
                self._redis_client.ping()
                logger.info("Vector cache connected to Redis")
            except Exception as e:
                logger.warning(f"Redis not available, using in-memory cache: {e}")
                self._redis_client = None
        else:
            logger.info("Redis not available, using in-memory cache")

        logger.info(f"Vector cache initialized (TTL: {ttl_hours}h, max_size: {max_size})")

    def _generate_key(self, query: str, top_k: int = 10, **kwargs) -> str:
        """
        Generate a cache key from query parameters.

        Args:
            query: The query text
            top_k: Number of results to return
            **kwargs: Additional parameters

        Returns:
            Hash string for cache key
        """
        key_data = {
            "query": query,
            "top_k": top_k,
            "kwargs": sorted(kwargs.items()) if kwargs else [],
        }
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_string.encode()).hexdigest()

    def get(self, query: str, top_k: int = 10, **kwargs) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached results for a query.

        Args:
            query: The query text
            top_k: Number of results to return
            **kwargs: Additional parameters

        Returns:
            Cached results or None if not found/expired
        """
        perf_flags = get_performance_flags()
        if not perf_flags.is_enabled("vector_db_cache"):
            return None

        metrics = get_metrics_collector()
        metrics.start_operation("vector_cache_get")

        key = self._generate_key(query, top_k, **kwargs)

        if self._redis_client is not None:
            # Use Redis cache
            try:
                cached_data = self._redis_client.get(f"vector:{key}")
                if cached_data:
                    self._hits += 1
                    results = json.loads(cached_data)
                    metrics.end_operation(
                        "vector_cache_get",
                        {"hit": True, "backend": "redis", "results_count": len(results)},
                    )
                    logger.debug(f"Vector cache hit (Redis): {key[:16]}...")
                    return results
            except Exception as e:
                logger.warning(f"Redis cache error: {e}")

        # Use in-memory cache as fallback
        with self._lock:
            if key in self._memory_cache:
                entry = self._memory_cache[key]

                # Check if entry is expired
                if datetime.now() - entry["timestamp"] < self.ttl:
                    self._hits += 1
                    metrics.end_operation(
                        "vector_cache_get",
                        {"hit": True, "backend": "memory", "results_count": len(entry["results"])},
                    )
                    logger.debug(f"Vector cache hit (memory): {key[:16]}...")
                    return entry["results"]
                else:
                    # Remove expired entry
                    del self._memory_cache[key]
                    logger.debug(f"Vector cache entry expired: {key[:16]}...")

        self._misses += 1
        metrics.end_operation("vector_cache_get", {"hit": False})
        return None

    def set(self, query: str, results: List[Dict[str, Any]], top_k: int = 10, **kwargs) -> None:
        """
        Cache results for a query.

        Args:
            query: The query text
            results: The query results to cache
            top_k: Number of results returned
            **kwargs: Additional parameters
        """
        perf_flags = get_performance_flags()
        if not perf_flags.is_enabled("vector_db_cache"):
            return

        metrics = get_metrics_collector()
        metrics.start_operation("vector_cache_set")

        key = self._generate_key(query, top_k, **kwargs)

        if self._redis_client is not None:
            # Use Redis cache
            try:
                self._redis_client.setex(
                    f"vector:{key}", int(self.ttl.total_seconds()), json.dumps(results)
                )
                metrics.end_operation(
                    "vector_cache_set", {"backend": "redis", "results_count": len(results)}
                )
                logger.debug(f"Vector cache set (Redis): {key[:16]}...")
                return
            except Exception as e:
                logger.warning(f"Redis cache error: {e}")

        # Use in-memory cache as fallback
        with self._lock:
            # Evict oldest entries if cache is full
            if len(self._memory_cache) >= self.max_size:
                oldest_key = min(
                    self._memory_cache.keys(), key=lambda k: self._memory_cache[k]["timestamp"]
                )
                del self._memory_cache[oldest_key]
                logger.debug(f"Vector cache evicted oldest entry: {oldest_key[:16]}...")

            self._memory_cache[key] = {
                "results": results,
                "timestamp": datetime.now(),
                "query_length": len(query),
            }

        metrics.end_operation(
            "vector_cache_set",
            {
                "backend": "memory",
                "cache_size": len(self._memory_cache),
                "results_count": len(results),
            },
        )
        logger.debug(f"Vector cache set (memory): {key[:16]}...")

    def clear(self) -> None:
        """Clear all cache entries."""
        if self._redis_client is not None:
            try:
                # Clear all vector cache keys
                for key in self._redis_client.scan_iter(match="vector:*"):
                    self._redis_client.delete(key)
            except Exception as e:
                logger.warning(f"Redis clear error: {e}")

        with self._lock:
            self._memory_cache.clear()
            self._hits = 0
            self._misses = 0
        logger.info("Vector cache cleared")

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
                "backend": "redis" if self._redis_client else "memory",
                "size": len(self._memory_cache) if self._redis_client is None else "unknown",
                "max_size": self.max_size if self._redis_client is None else "unlimited",
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate_percent": round(hit_rate, 2),
                "ttl_hours": self.ttl.total_seconds() / 3600,
            }

    def cleanup_expired(self) -> int:
        """
        Remove expired entries from in-memory cache.

        Returns:
            Number of entries removed
        """
        metrics = get_metrics_collector()
        metrics.start_operation("vector_cache_cleanup")

        with self._lock:
            current_time = datetime.now()
            expired_keys = [
                key
                for key, entry in self._memory_cache.items()
                if current_time - entry["timestamp"] >= self.ttl
            ]

            for key in expired_keys:
                del self._memory_cache[key]

        metrics.end_operation("vector_cache_cleanup", {"removed": len(expired_keys)})
        if expired_keys:
            logger.info(f"Vector cache cleanup: removed {len(expired_keys)} expired entries")

        return len(expired_keys)


# Global instance
_vector_cache: Optional[VectorCache] = None
_vector_cache_lock = threading.Lock()


def get_vector_cache() -> VectorCache:
    """
    Get the global vector cache instance.

    Returns:
        VectorCache instance
    """
    global _vector_cache
    if _vector_cache is None:
        with _vector_cache_lock:
            if _vector_cache is None:
                _vector_cache = VectorCache()
    return _vector_cache
