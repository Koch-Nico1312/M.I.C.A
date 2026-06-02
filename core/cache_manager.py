"""
Caching system for JARVIS AI Assistant.

This module provides:
- SQLite-based caching backend
- LLM response caching
- Embedding cache for RAG
- Cache expiration and cleanup
"""

import hashlib
import json
import sqlite3
import time
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.logger import get_logger
from core.paths import project_path

logger = get_logger(__name__)


@dataclass
class CacheEntry:
    """Represents a cache entry."""

    key: str
    value: str
    created_at: float
    expires_at: Optional[float]
    metadata: Optional[Dict[str, Any]] = None


class CacheManager:
    """
    Manages caching with SQLite backend.
    """

    def __init__(self, cache_dir: Optional[Path] = None, default_ttl_hours: float = 24.0):
        """
        Initialize cache manager.

        Args:
            cache_dir: Directory for cache database
            default_ttl_hours: Default time-to-live in hours
        """
        if cache_dir is None:
            cache_dir = project_path("data", "cache")
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.cache_dir / "jarvis_cache.db"
        self.default_ttl = default_ttl_hours * 3600  # Convert to seconds

        self._initialize_db()
        logger.info(f"Cache manager initialized: {self.db_path}")

    def _initialize_db(self):
        """Initialize SQLite database with required tables."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()

            # Main cache table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL,
                    metadata TEXT,
                    access_count INTEGER DEFAULT 0,
                    last_accessed REAL
                )
            """)

            # LLM response cache table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS llm_responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prompt_hash TEXT NOT NULL,
                    model TEXT NOT NULL,
                    response TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL,
                    tokens_used INTEGER,
                    access_count INTEGER DEFAULT 0
                )
            """)

            # Embedding cache table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS embeddings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text_hash TEXT NOT NULL,
                    model TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL,
                    access_count INTEGER DEFAULT 0
                )
            """)

            # Create indexes for performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cache_expires ON cache(expires_at)")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_llm_prompt_hash ON llm_responses(prompt_hash)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_llm_expires ON llm_responses(expires_at)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_embeddings_text_hash ON embeddings(text_hash)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_embeddings_expires ON embeddings(expires_at)"
            )

            conn.commit()

    def _generate_key(self, prefix: str, data: Any) -> str:
        """
        Generate a cache key from data.

        Args:
            prefix: Key prefix
            data: Data to hash

        Returns:
            Cache key string
        """
        if isinstance(data, str):
            data_str = data
        elif isinstance(data, dict):
            data_str = json.dumps(data, sort_keys=True)
        else:
            data_str = str(data)

        hash_obj = hashlib.sha256(data_str.encode())
        return f"{prefix}:{hash_obj.hexdigest()}"

    def set(
        self,
        key: str,
        value: Any,
        ttl_hours: Optional[float] = None,
        metadata: Optional[Dict] = None,
    ) -> bool:
        """
        Store a value in cache.

        Args:
            key: Cache key
            value: Value to store (will be JSON serialized)
            ttl_hours: Time-to-live in hours (uses default if None)
            metadata: Optional metadata dictionary

        Returns:
            True if successful
        """
        try:
            ttl = (ttl_hours * 3600) if ttl_hours else self.default_ttl
            expires_at = time.time() + ttl if ttl > 0 else None

            if isinstance(value, (dict, list)):
                value_str = json.dumps(value)
            else:
                value_str = str(value)

            metadata_str = json.dumps(metadata) if metadata else None

            with closing(sqlite3.connect(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO cache (key, value, created_at, expires_at, metadata, access_count, last_accessed)
                    VALUES (?, ?, ?, ?, ?, 0, ?)
                """,
                    (key, value_str, time.time(), expires_at, metadata_str, time.time()),
                )
                conn.commit()

            logger.debug(f"Cache set: {key}")
            return True

        except Exception as e:
            logger.error(f"Failed to set cache: {e}")
            return False

    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve a value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        try:
            with closing(sqlite3.connect(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT value, expires_at, metadata, access_count 
                    FROM cache 
                    WHERE key = ?
                """,
                    (key,),
                )
                row = cursor.fetchone()

                if not row:
                    return None

                value_str, expires_at, metadata_str, access_count = row

                # Check expiration
                if expires_at and time.time() > expires_at:
                    self.delete(key)
                    return None

                # Update access statistics
                cursor.execute(
                    """
                    UPDATE cache 
                    SET access_count = access_count + 1, last_accessed = ?
                    WHERE key = ?
                """,
                    (time.time(), key),
                )
                conn.commit()

                # Deserialize value
                try:
                    value = json.loads(value_str)
                except json.JSONDecodeError:
                    value = value_str

                # Deserialize metadata
                metadata = json.loads(metadata_str) if metadata_str else None

                logger.debug(f"Cache hit: {key}")
                return value

        except Exception as e:
            logger.error(f"Failed to get cache: {e}")
            return None

    def delete(self, key: str) -> bool:
        """
        Delete a cache entry.

        Args:
            key: Cache key

        Returns:
            True if successful
        """
        try:
            with closing(sqlite3.connect(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM cache WHERE key = ?", (key,))
                conn.commit()
            logger.debug(f"Cache deleted: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete cache: {e}")
            return False

    def clear_expired(self) -> int:
        """
        Clear all expired cache entries.

        Returns:
            Number of entries cleared
        """
        try:
            with closing(sqlite3.connect(self.db_path)) as conn:
                cursor = conn.cursor()

                # Clear expired from main cache
                cursor.execute(
                    "DELETE FROM cache WHERE expires_at IS NOT NULL AND expires_at < ?",
                    (time.time(),),
                )
                cache_count = cursor.rowcount

                # Clear expired LLM responses
                cursor.execute(
                    "DELETE FROM llm_responses WHERE expires_at IS NOT NULL AND expires_at < ?",
                    (time.time(),),
                )
                llm_count = cursor.rowcount

                # Clear expired embeddings
                cursor.execute(
                    "DELETE FROM embeddings WHERE expires_at IS NOT NULL AND expires_at < ?",
                    (time.time(),),
                )
                embed_count = cursor.rowcount

                conn.commit()

                total = cache_count + llm_count + embed_count
                logger.info(f"Cleared {total} expired cache entries")
                return total

        except Exception as e:
            logger.error(f"Failed to clear expired cache: {e}")
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        try:
            with closing(sqlite3.connect(self.db_path)) as conn:
                cursor = conn.cursor()

                # Main cache stats
                cursor.execute("SELECT COUNT(*) FROM cache")
                cache_count = cursor.fetchone()[0]

                cursor.execute(
                    "SELECT COUNT(*) FROM cache WHERE expires_at IS NOT NULL AND expires_at < ?",
                    (time.time(),),
                )
                expired_count = cursor.fetchone()[0]

                cursor.execute("SELECT SUM(access_count) FROM cache")
                total_access = cursor.fetchone()[0] or 0

                # Cache hit rate estimation
                cursor.execute(
                    "SELECT SUM(access_count) FROM cache WHERE last_accessed > ?",
                    (time.time() - 3600,),
                )
                recent_access = cursor.fetchone()[0] or 0

                # LLM response stats
                cursor.execute("SELECT COUNT(*) FROM llm_responses")
                llm_count = cursor.fetchone()[0]

                cursor.execute("SELECT SUM(access_count) FROM llm_responses")
                llm_access = cursor.fetchone()[0] or 0

                # Embedding stats
                cursor.execute("SELECT COUNT(*) FROM embeddings")
                embed_count = cursor.fetchone()[0]

                cursor.execute("SELECT SUM(access_count) FROM embeddings")
                embed_access = cursor.fetchone()[0] or 0

                # Database size
                db_size = self.db_path.stat().st_size if self.db_path.exists() else 0

                return {
                    "main_cache": {
                        "total_entries": cache_count,
                        "expired_entries": expired_count,
                        "total_access": total_access,
                        "recent_access_last_hour": recent_access,
                    },
                    "llm_responses": {"total_entries": llm_count, "total_access": llm_access},
                    "embeddings": {"total_entries": embed_count, "total_access": embed_access},
                    "database_size_bytes": db_size,
                    "database_size_mb": db_size / (1024 * 1024),
                }

        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {}

    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all cache entries matching a pattern.

        Args:
            pattern: Pattern to match (SQL LIKE pattern)

        Returns:
            Number of entries invalidated
        """
        try:
            with closing(sqlite3.connect(self.db_path)) as conn:
                cursor = conn.cursor()

                # Invalidate from main cache
                cursor.execute("DELETE FROM cache WHERE key LIKE ?", (f"%{pattern}%",))
                cache_count = cursor.rowcount

                # Invalidate from LLM responses
                cursor.execute(
                    "DELETE FROM llm_responses WHERE prompt_hash LIKE ?", (f"%{pattern}%",)
                )
                llm_count = cursor.rowcount

                # Invalidate from embeddings
                cursor.execute("DELETE FROM embeddings WHERE text_hash LIKE ?", (f"%{pattern}%",))
                embed_count = cursor.rowcount

                conn.commit()

                total = cache_count + llm_count + embed_count
                logger.info(f"Invalidated {total} cache entries matching pattern: {pattern}")
                return total

        except Exception as e:
            logger.error(f"Failed to invalidate pattern: {e}")
            return 0

    def invalidate_by_prefix(self, prefix: str) -> int:
        """
        Invalidate all cache entries with a specific prefix.

        Args:
            prefix: Key prefix to invalidate

        Returns:
            Number of entries invalidated
        """
        try:
            with closing(sqlite3.connect(self.db_path)) as conn:
                cursor = conn.cursor()

                # Invalidate from main cache
                cursor.execute("DELETE FROM cache WHERE key LIKE ?", (f"{prefix}:%",))
                cache_count = cursor.rowcount

                conn.commit()

                logger.info(f"Invalidated {cache_count} cache entries with prefix: {prefix}")
                return cache_count

        except Exception as e:
            logger.error(f"Failed to invalidate prefix: {e}")
            return 0

    def get_cache_hit_rate(self, hours: int = 24) -> Dict[str, float]:
        """
        Calculate cache hit rate over a time period.

        Args:
            hours: Number of hours to look back

        Returns:
            Dictionary with hit rates for different cache types
        """
        try:
            with closing(sqlite3.connect(self.db_path)) as conn:
                cursor = conn.cursor()

                cutoff = time.time() - (hours * 3600)

                # Main cache hit rate
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM cache 
                    WHERE last_accessed > ?
                """,
                    (cutoff,),
                )
                total_hits = cursor.fetchone()[0] or 0

                cursor.execute(
                    """
                    SELECT COUNT(*) FROM cache 
                    WHERE created_at > ?
                """,
                    (cutoff,),
                )
                total_misses = cursor.fetchone()[0] or 0

                main_hit_rate = (
                    total_hits / (total_hits + total_misses)
                    if (total_hits + total_misses) > 0
                    else 0.0
                )

                # LLM response hit rate
                cursor.execute(
                    """
                    SELECT SUM(access_count) FROM llm_responses 
                    WHERE last_accessed > ?
                """,
                    (cutoff,),
                )
                llm_hits = cursor.fetchone()[0] or 0

                cursor.execute(
                    """
                    SELECT COUNT(*) FROM llm_responses 
                    WHERE created_at > ?
                """,
                    (cutoff,),
                )
                llm_misses = cursor.fetchone()[0] or 0

                llm_hit_rate = (
                    llm_hits / (llm_hits + llm_misses) if (llm_hits + llm_misses) > 0 else 0.0
                )

                return {
                    "main_cache_hit_rate": main_hit_rate,
                    "llm_response_hit_rate": llm_hit_rate,
                    "period_hours": hours,
                }

        except Exception as e:
            logger.error(f"Failed to calculate hit rate: {e}")
            return {}

    def cache_llm_response(
        self,
        prompt: str,
        model: str,
        response: str,
        tokens_used: Optional[int] = None,
        ttl_hours: float = 168.0,
    ) -> bool:
        """
        Cache an LLM response.

        Args:
            prompt: Input prompt
            model: Model name
            response: Model response
            tokens_used: Number of tokens used
            ttl_hours: Time-to-live in hours (default 1 week)

        Returns:
            True if successful
        """
        try:
            prompt_hash = self._generate_key("llm", f"{model}:{prompt}")
            expires_at = time.time() + (ttl_hours * 3600)

            with closing(sqlite3.connect(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO llm_responses 
                    (prompt_hash, model, response, created_at, expires_at, tokens_used, access_count)
                    VALUES (?, ?, ?, ?, ?, ?, 0)
                """,
                    (prompt_hash, model, response, time.time(), expires_at, tokens_used),
                )
                conn.commit()

            logger.debug(f"LLM response cached: {model}")
            return True

        except Exception as e:
            logger.error(f"Failed to cache LLM response: {e}")
            return False

    def get_llm_response(self, prompt: str, model: str) -> Optional[str]:
        """
        Retrieve a cached LLM response.

        Args:
            prompt: Input prompt
            model: Model name

        Returns:
            Cached response or None
        """
        try:
            prompt_hash = self._generate_key("llm", f"{model}:{prompt}")

            with closing(sqlite3.connect(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT response, expires_at, access_count 
                    FROM llm_responses 
                    WHERE prompt_hash = ? AND model = ?
                """,
                    (prompt_hash, model),
                )
                row = cursor.fetchone()

                if not row:
                    return None

                response, expires_at, access_count = row

                # Check expiration
                if expires_at and time.time() > expires_at:
                    return None

                # Update access count
                cursor.execute(
                    """
                    UPDATE llm_responses 
                    SET access_count = access_count + 1 
                    WHERE prompt_hash = ? AND model = ?
                """,
                    (prompt_hash, model),
                )
                conn.commit()

                logger.debug(f"LLM cache hit: {model}")
                return response

        except Exception as e:
            logger.error(f"Failed to get LLM response from cache: {e}")
            return None

    def cache_embedding(
        self, text: str, model: str, embedding: List[float], ttl_hours: float = 720.0
    ) -> bool:
        """
        Cache an embedding.

        Args:
            text: Input text
            model: Embedding model name
            embedding: Embedding vector
            ttl_hours: Time-to-live in hours (default 30 days)

        Returns:
            True if successful
        """
        try:
            text_hash = self._generate_key("embed", f"{model}:{text}")
            expires_at = time.time() + (ttl_hours * 3600)

            # Convert embedding to bytes
            embedding_bytes = json.dumps(embedding).encode()

            with closing(sqlite3.connect(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO embeddings 
                    (text_hash, model, embedding, created_at, expires_at, access_count)
                    VALUES (?, ?, ?, ?, ?, 0)
                """,
                    (text_hash, model, embedding_bytes, time.time(), expires_at),
                )
                conn.commit()

            logger.debug(f"Embedding cached: {model}")
            return True

        except Exception as e:
            logger.error(f"Failed to cache embedding: {e}")
            return False

    def get_embedding(self, text: str, model: str) -> Optional[List[float]]:
        """
        Retrieve a cached embedding.

        Args:
            text: Input text
            model: Embedding model name

        Returns:
            Cached embedding or None
        """
        try:
            text_hash = self._generate_key("embed", f"{model}:{text}")

            with closing(sqlite3.connect(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT embedding, expires_at, access_count 
                    FROM embeddings 
                    WHERE text_hash = ? AND model = ?
                """,
                    (text_hash, model),
                )
                row = cursor.fetchone()

                if not row:
                    return None

                embedding_bytes, expires_at, access_count = row

                # Check expiration
                if expires_at and time.time() > expires_at:
                    return None

                # Update access count
                cursor.execute(
                    """
                    UPDATE embeddings 
                    SET access_count = access_count + 1 
                    WHERE text_hash = ? AND model = ?
                """,
                    (text_hash, model),
                )
                conn.commit()

                # Deserialize embedding
                embedding = json.loads(embedding_bytes.decode())

                logger.debug(f"Embedding cache hit: {model}")
                return embedding

        except Exception as e:
            logger.error(f"Failed to get embedding from cache: {e}")
            return None


# Global instance
_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """Get the global cache manager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager
