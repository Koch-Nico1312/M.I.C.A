"""
Tests for the cache manager.
"""

import json
import tempfile
import time
from pathlib import Path

import pytest

from core.cache_manager import CacheManager, get_cache_manager


@pytest.fixture
def temp_cache_manager():
    """Create a temporary cache manager for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = Path(tmpdir)
        manager = CacheManager(cache_dir=cache_dir, default_ttl_hours=1.0)
        yield manager


def test_cache_manager_initialization(temp_cache_manager):
    """Test that cache manager initializes correctly."""
    assert temp_cache_manager.cache_dir.exists()
    assert temp_cache_manager.db_path.exists()


def test_cache_set_and_get(temp_cache_manager):
    """Test setting and getting cache values."""
    temp_cache_manager.set("test_key", "test_value")
    result = temp_cache_manager.get("test_key")
    assert result == "test_value"


def test_cache_set_dict(temp_cache_manager):
    """Test caching dictionary values."""
    test_dict = {"key": "value", "nested": {"data": 123}}
    temp_cache_manager.set("dict_key", test_dict)
    result = temp_cache_manager.get("dict_key")
    assert result == test_dict


def test_cache_expiration(temp_cache_manager):
    """Test cache expiration."""
    # Set a value with very short TTL
    temp_cache_manager.set("expire_key", "value", ttl_hours=0.0001)  # ~0.36 seconds
    time.sleep(0.5)
    result = temp_cache_manager.get("expire_key")
    assert result is None


def test_cache_delete(temp_cache_manager):
    """Test deleting cache entries."""
    temp_cache_manager.set("delete_key", "value")
    temp_cache_manager.delete("delete_key")
    result = temp_cache_manager.get("delete_key")
    assert result is None


def test_cache_stats(temp_cache_manager):
    """Test getting cache statistics."""
    temp_cache_manager.set("stat_key1", "value1")
    temp_cache_manager.set("stat_key2", "value2")
    stats = temp_cache_manager.get_stats()
    assert "main_cache" in stats
    assert stats["main_cache"]["total_entries"] >= 2


def test_llm_response_caching(temp_cache_manager):
    """Test LLM response caching."""
    prompt = "Test prompt"
    model = "test-model"
    response = "Test response"

    temp_cache_manager.cache_llm_response(prompt, model, response)
    cached = temp_cache_manager.get_llm_response(prompt, model)
    assert cached == response


def test_embedding_caching(temp_cache_manager):
    """Test embedding caching."""
    text = "Test text"
    model = "test-embed-model"
    embedding = [0.1, 0.2, 0.3, 0.4, 0.5]

    temp_cache_manager.cache_embedding(text, model, embedding)
    cached = temp_cache_manager.get_embedding(text, model)
    assert cached == embedding


def test_clear_expired(temp_cache_manager):
    """Test clearing expired cache entries."""
    temp_cache_manager.set("expire_key", "value", ttl_hours=0.0001)
    time.sleep(0.5)
    cleared = temp_cache_manager.clear_expired()
    assert cleared >= 0


def test_global_cache_manager():
    """Test global cache manager instance."""
    manager1 = get_cache_manager()
    manager2 = get_cache_manager()
    assert manager1 is manager2
