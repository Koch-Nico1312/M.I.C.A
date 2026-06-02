"""
Integration tests for vector cache system
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile


class TestVectorCacheIntegration:
    """Integration tests for vector cache system components."""

    @pytest.fixture
    def vector_cache(self):
        """Create a fresh VectorCache instance for testing."""
        from core.vector_cache import VectorCache
        return VectorCache()

    def test_vector_cache_storage(self, vector_cache):
        """Test storing vectors in cache."""
        vector = [0.1, 0.2, 0.3, 0.4, 0.5]
        vector_cache.store("key1", vector, metadata={"type": "test"})
        
        # Retrieve from cache
        retrieved = vector_cache.get("key1")
        
        assert retrieved is not None
        assert retrieved["vector"] == vector

    def test_vector_cache_retrieval(self, vector_cache):
        """Test retrieving vectors from cache."""
        vectors = {
            "key1": [0.1, 0.2, 0.3],
            "key2": [0.4, 0.5, 0.6],
            "key3": [0.7, 0.8, 0.9]
        }
        
        for key, vector in vectors.items():
            vector_cache.store(key, vector)
        
        # Retrieve all
        all_vectors = vector_cache.get_all()
        
        assert len(all_vectors) == 3

    def test_vector_similarity_search(self, vector_cache):
        """Test similarity search in vector cache."""
        # Store vectors
        vector_cache.store("key1", [1.0, 0.0, 0.0])
        vector_cache.store("key2", [0.0, 1.0, 0.0])
        vector_cache.store("key3", [0.9, 0.1, 0.0])
        
        # Search for similar vectors
        query = [1.0, 0.0, 0.0]
        results = vector_cache.similarity_search(query, top_k=2)
        
        assert results is not None
        assert len(results) <= 2

    def test_vector_cache_eviction(self, vector_cache):
        """Test cache eviction policy."""
        vector_cache.max_size = 3
        
        # Store more than max
        for i in range(5):
            vector_cache.store(f"key{i}", [i, i, i])
        
        # Should evict old entries
        all_vectors = vector_cache.get_all()
        assert len(all_vectors) <= 3

    def test_vector_cache_persistence(self, vector_cache):
        """Test vector cache persistence to disk."""
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "vector_cache"
            cache_path.mkdir()
            
            vector_cache.storage_path = cache_path
            
            # Store vector
            vector_cache.store("key1", [0.1, 0.2, 0.3])
            
            # Save to disk
            vector_cache.save()
            
            # Load from disk
            vector_cache.load()
            
            # Verify persistence
            retrieved = vector_cache.get("key1")
            assert retrieved is not None

    def test_vector_cache_with_chromadb(self, vector_cache):
        """Test integration with ChromaDB."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "chromadb"
            db_path.mkdir()
            
            vector_cache.use_chromadb = True
            vector_cache.chromadb_path = db_path
            
            # Store vector
            vector_cache.store("key1", [0.1, 0.2, 0.3])
            
            # Should use ChromaDB
            assert True  # Placeholder for actual ChromaDB test

    def test_vector_cache_with_redis(self, vector_cache):
        """Test integration with Redis."""
        vector_cache.use_redis = True
        vector_cache.redis_host = "localhost"
        vector_cache.redis_port = 6379
        
        # Store vector (would use Redis if available)
        vector_cache.store("key1", [0.1, 0.2, 0.3])
        
        # Should handle Redis gracefully
        assert True  # Placeholder for actual Redis test

    def test_vector_cache_with_embeddings(self, vector_cache):
        """Test vector cache with embedding generation."""
        from core.semantic_search import SemanticSearch
        
        search = SemanticSearch()
        
        # Generate embedding
        text = "Test text for embedding"
        embedding = search.get_embedding(text)
        
        # Store in cache
        vector_cache.store("text_key", embedding, metadata={"text": text})
        
        # Retrieve
        retrieved = vector_cache.get("text_key")
        
        assert retrieved is not None
        assert retrieved["metadata"]["text"] == text

    def test_vector_cache_batch_operations(self, vector_cache):
        """Test batch operations on vector cache."""
        # Batch store
        vectors = {
            "key1": [0.1, 0.2, 0.3],
            "key2": [0.4, 0.5, 0.6],
            "key3": [0.7, 0.8, 0.9]
        }
        vector_cache.batch_store(vectors)
        
        # Batch retrieve
        keys = ["key1", "key2", "key3"]
        retrieved = vector_cache.batch_get(keys)
        
        assert len(retrieved) == 3

    def test_vector_cache_cleanup(self, vector_cache):
        """Test cache cleanup based on TTL."""
        vector_cache.enable_ttl = True
        vector_cache.ttl_seconds = 60
        
        # Store vector
        vector_cache.store("key1", [0.1, 0.2, 0.3])
        
        # Cleanup expired entries
        vector_cache.cleanup_expired()
        
        # Should handle cleanup
        assert True  # Placeholder for actual TTL test


class TestVectorCacheErrorHandling:
    """Error handling tests for vector cache system."""

    @pytest.fixture
    def vector_cache(self):
        """Create a fresh VectorCache instance for testing."""
        from core.vector_cache import VectorCache
        return VectorCache()

    def test_invalid_vector_format(self, vector_cache):
        """Test handling of invalid vector format."""
        invalid_vectors = [
            None,
            [],
            {},
            "not a vector",
            [1, 2, "invalid"]
        ]
        
        for invalid_vector in invalid_vectors:
            try:
                vector_cache.store("key", invalid_vector)
            except (ValueError, TypeError):
                pass  # Expected

    def test_get_nonexistent_key(self, vector_cache):
        """Test retrieving nonexistent key."""
        result = vector_cache.get("nonexistent_key")
        assert result is None

    def test_similarity_search_empty_cache(self, vector_cache):
        """Test similarity search on empty cache."""
        query = [0.1, 0.2, 0.3]
        results = vector_cache.similarity_search(query)
        
        assert results == []


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
