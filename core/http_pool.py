"""
HTTP Connection Pool Manager for M.I.C.A AI Assistant
====================================================
Manages aiohttp ClientSession with connection pooling for external APIs.
"""

import asyncio
import threading
from typing import Optional

from core.logger import get_logger
from core.metrics_collector import get_metrics_collector
from core.performance_flags import get_performance_flags

logger = get_logger(__name__)

try:
    import aiohttp

    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False


class HTTPConnectionPool:
    """
    Manages HTTP connection pooling with aiohttp ClientSession.
    """

    def __init__(self, max_connections: int = 10, max_per_host: int = 5):
        """
        Initialize the HTTP connection pool.

        Args:
            max_connections: Maximum total connections
            max_per_host: Maximum connections per host
        """
        self.max_connections = max_connections
        self.max_per_host = max_per_host
        self._session: Optional[aiohttp.ClientSession] = None
        self._lock = threading.Lock()

        logger.info(f"HTTP connection pool initialized (max_connections: {max_connections})")

    def get_session(self) -> Optional[aiohttp.ClientSession]:
        """
        Get or create the aiohttp ClientSession.

        Returns:
            ClientSession or None if aiohttp not available
        """
        if not AIOHTTP_AVAILABLE:
            logger.warning("aiohttp not available, connection pooling disabled")
            return None

        perf_flags = get_performance_flags()
        if not perf_flags.is_enabled("connection_pooling"):
            logger.debug("Connection pooling disabled by feature flag")
            return None

        with self._lock:
            if self._session is None or self._session.closed:
                metrics = get_metrics_collector()
                metrics.start_operation("http_pool_create")

                connector = aiohttp.TCPConnector(
                    limit=self.max_connections,
                    limit_per_host=self.max_per_host,
                    enable_cleanup_closed=True,
                    force_close=False,
                )

                timeout = aiohttp.ClientTimeout(total=30)

                self._session = aiohttp.ClientSession(
                    connector=connector, timeout=timeout, raise_for_status=False
                )

                metrics.end_operation(
                    "http_pool_create",
                    {"max_connections": self.max_connections, "max_per_host": self.max_per_host},
                )
                logger.info("HTTP connection pool session created")

        return self._session

    async def close(self) -> None:
        """Close the HTTP session."""
        with self._lock:
            if self._session is not None and not self._session.closed:
                await self._session.close()
                logger.info("HTTP connection pool session closed")

    def get_stats(self) -> dict:
        """
        Get connection pool statistics.

        Returns:
            Dictionary with pool statistics
        """
        with self._lock:
            if self._session is None or self._session.closed:
                return {
                    "active": False,
                    "max_connections": self.max_connections,
                    "max_per_host": self.max_per_host,
                }

            connector = self._session.connector
            if connector is not None:
                return {
                    "active": True,
                    "max_connections": self.max_connections,
                    "max_per_host": self.max_per_host,
                    "total_connections": (
                        len(connector._conns) if hasattr(connector, "_conns") else 0
                    ),
                }

            return {
                "active": True,
                "max_connections": self.max_connections,
                "max_per_host": self.max_per_host,
            }


# Global instance
_http_pool: Optional[HTTPConnectionPool] = None
_http_pool_lock = threading.Lock()


def get_http_pool() -> HTTPConnectionPool:
    """
    Get the global HTTP connection pool instance.

    Returns:
        HTTPConnectionPool instance
    """
    global _http_pool
    if _http_pool is None:
        with _http_pool_lock:
            if _http_pool is None:
                _http_pool = HTTPConnectionPool()
    return _http_pool


async def close_http_pool() -> None:
    """Close the global HTTP connection pool."""
    global _http_pool
    if _http_pool is not None:
        await _http_pool.close()
