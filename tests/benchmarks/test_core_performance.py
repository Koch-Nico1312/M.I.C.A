"""
Performance benchmarks for core modules
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock


class TestActionLoaderPerformance:
    """Performance benchmarks for ActionLoader."""

    @pytest.fixture
    def action_loader(self):
        """Create a fresh ActionLoader instance for benchmarking."""
        from core.action_loader import ActionLoader
        return ActionLoader()

    def test_tool_declarations_loading_performance(self, action_loader, benchmark):
        """Benchmark tool declarations loading."""
        result = benchmark(action_loader.get_tool_declarations)
        assert result is not None

    def test_action_loading_performance(self, action_loader, benchmark):
        """Benchmark individual action loading."""
        def load_action():
            return action_loader.load_action("web_search")
        
        result = benchmark(load_action)
        assert result is not None


class TestMemoryManagerPerformance:
    """Performance benchmarks for MemoryManager."""

    @pytest.fixture
    def memory_manager(self):
        """Create a fresh MemoryManager instance for benchmarking."""
        from memory.memory_manager import MemoryManager
        return MemoryManager()

    def test_memory_write_performance(self, memory_manager, benchmark):
        """Benchmark memory write operations."""
        def write_memory():
            test_data = {"key": "value" * 100}
            return memory_manager.update_memory("test", test_data)
        
        result = benchmark(write_memory)
        assert result is not None

    def test_memory_read_performance(self, memory_manager, benchmark):
        """Benchmark memory read operations."""
        # First write
        memory_manager.update_memory("test", {"data": "test"})
        
        def read_memory():
            return memory_manager.load_memory("test")
        
        result = benchmark(read_memory)
        assert result is not None


class TestWorkflowEnginePerformance:
    """Performance benchmarks for WorkflowEngine."""

    @pytest.fixture
    def workflow_engine(self):
        """Create a fresh WorkflowEngine instance for benchmarking."""
        from core.workflow_engine import WorkflowEngine
        return WorkflowEngine()

    def test_workflow_creation_performance(self, workflow_engine, benchmark):
        """Benchmark workflow creation."""
        def create_workflow():
            steps = [
                {"name": f"Step {i}", "action": "test", "parameters": {}}
                for i in range(10)
            ]
            return workflow_engine.create_workflow(
                name="Test Workflow",
                goal="Test",
                description="Test",
                steps=steps
            )
        
        result = benchmark(create_workflow)
        assert result is not None

    def test_workflow_submission_performance(self, workflow_engine, benchmark):
        """Benchmark workflow submission."""
        workflow = workflow_engine.create_workflow(
            name="Test",
            goal="Test",
            description="Test",
            steps=[{"name": "Step 1", "action": "test", "parameters": {}}]
        )
        
        def submit_workflow():
            return workflow_engine.submit_workflow(workflow)
        
        result = benchmark(submit_workflow)
        assert result is not None


class TestSemanticSearchPerformance:
    """Performance benchmarks for SemanticSearch."""

    @pytest.fixture
    def semantic_search(self):
        """Create a fresh SemanticSearch instance for benchmarking."""
        from core.semantic_search import SemanticSearch
        return SemanticSearch()

    def test_embedding_generation_performance(self, semantic_search, benchmark):
        """Benchmark embedding generation."""
        # Mock embedding model
        semantic_search.embedding_model = Mock()
        semantic_search.embedding_model.encode.return_value = [0.1] * 768
        
        def generate_embedding():
            return semantic_search.get_embedding("Test text for embedding generation")
        
        result = benchmark(generate_embedding)
        assert result is not None

    def test_search_performance(self, semantic_search, benchmark):
        """Benchmark search operations."""
        # Mock search
        semantic_search.search = Mock(return_value=[])
        
        def search():
            return semantic_search.search("test query")
        
        result = benchmark(search)
        assert result is not None


class TestAudioHandlerPerformance:
    """Performance benchmarks for AudioHandler."""

    @pytest.fixture
    def audio_handler(self):
        """Create a fresh AudioHandler instance for benchmarking."""
        from core.audio_handler import AudioHandler
        return AudioHandler()

    def test_audio_processing_performance(self, audio_handler, benchmark):
        """Benchmark audio processing."""
        audio_data = np.random.rand(16000).astype(np.float32)
        
        def process_audio():
            return audio_handler.process_chunk(audio_data)
        
        result = benchmark(process_audio)
        assert result is not None


class TestLLMPerformance:
    """Performance benchmarks for LLM operations."""

    @pytest.fixture
    def llm(self):
        """Create a fresh LLM instance for benchmarking."""
        from core.llm_fallback import LLMFallback
        return LLMFallback()

    def test_response_generation_performance(self, llm, benchmark):
        """Benchmark LLM response generation."""
        # Mock generation
        llm._generate_primary = Mock(return_value="Test response")
        
        def generate_response():
            return llm.generate("Test prompt")
        
        result = benchmark(generate_response)
        assert result is not None


class TestCachePerformance:
    """Performance benchmarks for caching systems."""

    @pytest.fixture
    def api_cache(self):
        """Create a fresh APICache instance for benchmarking."""
        from core.api_cache import APICache
        return APICache()

    def test_cache_write_performance(self, api_cache, benchmark):
        """Benchmark cache write operations."""
        def cache_write():
            return api_cache.cache_response("test_endpoint", {"data": "test"}, ttl=300)
        
        result = benchmark(cache_write)
        assert result is not None

    def test_cache_read_performance(self, api_cache, benchmark):
        """Benchmark cache read operations."""
        # First write
        api_cache.cache_response("test_endpoint", {"data": "test"}, ttl=300)
        
        def cache_read():
            return api_cache.get_cached_response("test_endpoint")
        
        result = benchmark(cache_read)
        assert result is not None


class TestVectorCachePerformance:
    """Performance benchmarks for vector cache."""

    @pytest.fixture
    def vector_cache(self):
        """Create a fresh VectorCache instance for benchmarking."""
        from core.vector_cache import VectorCache
        return VectorCache()

    def test_vector_storage_performance(self, vector_cache, benchmark):
        """Benchmark vector storage."""
        vector = [0.1] * 768
        
        def store_vector():
            return vector_cache.store("test_key", vector)
        
        result = benchmark(store_vector)
        assert result is not None

    def test_similarity_search_performance(self, vector_cache, benchmark):
        """Benchmark similarity search."""
        # Store vectors
        for i in range(100):
            vector_cache.store(f"key{i}", [i/100] * 768)
        
        query = [0.5] * 768
        
        def search():
            return vector_cache.similarity_search(query, top_k=10)
        
        result = benchmark(search)
        assert result is not None


class TestSessionManagerPerformance:
    """Performance benchmarks for SessionManager."""

    @pytest.fixture
    def session_manager(self):
        """Create a fresh SessionManager instance for benchmarking."""
        from core.session_manager import SessionManager
        return SessionManager()

    def test_session_creation_performance(self, session_manager, benchmark):
        """Benchmark session creation."""
        def create_session():
            return session_manager.create_session()
        
        result = benchmark(create_session)
        assert result is not None

    def test_message_addition_performance(self, session_manager, benchmark):
        """Benchmark message addition."""
        session = session_manager.create_session()
        
        def add_message():
            return session_manager.add_message(session.session_id, "user", "Test message")
        
        result = benchmark(add_message)
        assert result is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--benchmark-only'])
