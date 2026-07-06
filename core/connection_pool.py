"""
Connection Pool Manager for M.I.C.A AI Assistant
===============================================
Manages HTTP connection pools for external API calls to improve performance.
"""

import aiohttp
import threading
from typing import Any, Dict, Optional

from core.logger import get_logger
from core.metrics_collector import get_metrics_collector
from core.performance_flags import get_performance_flags

logger = get_logger(__name__)


class ConnectionPoolManager:
    """
    Manages HTTP connection pools for external APIs.
    """

    def __init__(self):
        """Initialize the connection pool manager."""
        self._pools: Dict[str, aiohttp.ClientSession] = {}
        self._lock = threading.Lock()
        self._default_config = {
            "timeout": aiohttp.ClientTimeout(total=30),
            "limit": 100,
            "limit_per_host": 30,
        }

        logger.info("Connection pool manager initialized")

    def get_pool(
        self,
        pool_name: str,
        base_url: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Optional[aiohttp.ClientSession]:
        """
        Get or create a connection pool.

        Args:
            pool_name: Name of the pool
            base_url: Base URL for the pool
            config: Optional configuration overrides

        Returns:
            ClientSession or None if pooling is disabled
        """
        perf_flags = get_performance_flags()
        if not perf_flags.is_enabled("connection_pooling"):
            logger.debug("Connection pooling disabled, returning None")
            return None

        with self._lock:
            if pool_name in self._pools:
                logger.debug(f"Reusing existing pool: {pool_name}")
                return self._pools[pool_name]

            # Create new pool
            pool_config = {**self._default_config, **(config or {})}
            
            try:
                session = aiohttp.ClientSession(**pool_config)
                self._pools[pool_name] = session
                logger.info(f"Created connection pool: {pool_name}")
                return session
            except Exception as e:
                logger.error(f"Failed to create pool {pool_name}: {e}")
                return None

    def close_pool(self, pool_name: str) -> bool:
        """
        Close a specific connection pool.

        Args:
            pool_name: Name of the pool to close

        Returns:
            True if successful
        """
        with self._lock:
            if pool_name in self._pools:
                try:
                    import asyncio
                    loop = asyncio.get_event_loop()
                    loop.run_until_complete(self._pools[pool_name].close())
                    del self._pools[pool_name]
                    logger.info(f"Closed connection pool: {pool_name}")
                    return True
                except Exception as e:
                    logger.error(f"Failed to close pool {pool_name}: {e}")
                    return False
        return False

    def close_all(self) -> None:
        """Close all connection pools."""
        with self._lock:
            pool_names = list(self._pools.keys())
            for pool_name in pool_names:
                self.close_pool(pool_name)
        logger.info("All connection pools closed")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get connection pool statistics.

        Returns:
            Dictionary with pool statistics
        """
        with self._lock:
            return {
                "total_pools": len(self._pools),
                "pool_names": list(self._pools.keys()),
                "pooling_enabled": get_performance_flags().is_enabled("connection_pooling"),
            }


# Global instance
_connection_pool_manager: Optional[ConnectionPoolManager] = None
_connection_pool_lock = threading.Lock()


def get_connection_pool_manager() -> ConnectionPoolManager:
    """
    Get the global connection pool manager instance.

    Returns:
        ConnectionPoolManager instance
    """
    global _connection_pool_manager
    if _connection_pool_manager is None:
        with _connection_pool_lock:
            if _connection_pool_manager is None:
                _connection_pool_manager = ConnectionPoolManager()
    return _connection_pool_manager
