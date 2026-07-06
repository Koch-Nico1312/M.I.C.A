"""
Performance benchmarks for integration scenarios
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestFullWorkflowPerformance:
    """Performance benchmarks for full workflows."""

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_mica_response_performance(self, mock_loader, mock_memory, mock_config, benchmark):
        """Benchmark M.I.C.A response time."""
        from main import MicaLive
        
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        mica = MicaLive()
        
        def process_query():
            return mica.process_input("Hello M.I.C.A")
        
        result = benchmark(process_query)
        assert result is not None

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_multiturn_conversation_performance(self, mock_loader, mock_memory, mock_config, benchmark):
        """Benchmark multi-turn conversation."""
        from main import MicaLive
        
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        mica = MicaLive()
        
        def multi_turn():
            mica.process_input("Hello")
            mica.process_input("How are you?")
            mica.process_input("What can you do?")
            return True
        
        result = benchmark(multi_turn)
        assert result is True


class TestMemoryIntegrationPerformance:
    """Performance benchmarks for memory integration."""

    def test_hybrid_retrieval_performance(benchmark):
        """Benchmark hybrid retrieval performance."""
        from memory.hybrid_retrieval import get_hybrid_retrieval
        
        retrieval = get_hybrid_retrieval()
        
        # Add test memories
        for i in range(100):
            retrieval.add_memory(
                content=f"Test memory {i}",
                metadata={"type": "test", "index": i}
            )
        
        def search():
            return retrieval.search("test memory")
        
        result = benchmark(search)
        assert result is not None

    def test_obsidian_sync_performance(benchmark, tmp_path):
        """Benchmark Obsidian vault sync performance."""
        from memory.obsidian_vault import get_obsidian_bridge
        
        # Create test notes
        for i in range(50):
            (tmp_path / f"note{i}.md").write_text(f"# Note {i}\nContent here")
        
        obsidian = get_obsidian_bridge()
        obsidian.vault_path = tmp_path
        
        def sync_vault():
            return obsidian.sync_vault()
        
        result = benchmark(sync_vault)
        assert result is not None


class TestWorkflowExecutionPerformance:
    """Performance benchmarks for workflow execution."""

    def test_parallel_workflow_execution_performance(benchmark):
        """Benchmark parallel workflow execution."""
        from core.workflow_engine import WorkflowEngine
        import asyncio
        
        engine = WorkflowEngine()
        
        async def execute_parallel():
            steps = [
                {"name": f"Step {i}", "action": "test", "parameters": {}}
                for i in range(10)
            ]
            workflow = engine.create_workflow(
                name="Parallel Workflow",
                goal="Test",
                description="Test",
                steps=steps
            )
            return workflow
        
        result = benchmark(asyncio.run, execute_parallel())
        assert result is not None


class TestAPIIntegrationPerformance:
    """Performance benchmarks for API integration."""

    @patch('core.api_cache.requests')
    def test_cached_api_call_performance(self, mock_requests, benchmark):
        """Benchmark cached API call performance."""
        from core.api_cache import APICache
        
        cache = APICache()
        
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": "success"}
        mock_response.status_code = 200
        mock_requests.get.return_value = mock_response
        
        # Cache response
        cache.cache_response("test_endpoint", {"data": "test"}, ttl=300)
        
        def cached_call():
            return cache.get_cached_response("test_endpoint")
        
        result = benchmark(cached_call)
        assert result is not None

    @patch('core.api_cache.requests')
    def test_concurrent_api_requests_performance(self, mock_requests, benchmark):
        """Benchmark concurrent API requests."""
        from core.http_pool import HTTPPool
        import asyncio
        
        pool = HTTPPool()
        
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": "success"}
        mock_response.status_code = 200
        mock_requests.get.return_value = mock_response
        
        async def concurrent_requests():
            tasks = [
                pool.get_async(f"https://api.example.com/test{i}")
                for i in range(10)
            ]
            results = await asyncio.gather(*tasks)
            return results
        
        result = benchmark(asyncio.run, concurrent_requests())
        assert result is not None


class TestVectorOperationsPerformance:
    """Performance benchmarks for vector operations."""

    def test_vector_similarity_performance(benchmark):
        """Benchmark vector similarity search."""
        from core.vector_cache import VectorCache
        
        cache = VectorCache()
        
        # Store vectors
        for i in range(1000):
            cache.store(f"key{i}", [i/1000] * 768)
        
        query = [0.5] * 768
        
        def similarity_search():
            return cache.similarity_search(query, top_k=10)
        
        result = benchmark(similarity_search)
        assert result is not None

    def test_batch_vector_operations_performance(benchmark):
        """Benchmark batch vector operations."""
        from core.vector_cache import VectorCache
        
        cache = VectorCache()
        
        vectors = {
            f"key{i}": [i/100] * 768
            for i in range(100)
        }
        
        def batch_store():
            return cache.batch_store(vectors)
        
        result = benchmark(batch_store)
        assert result is not None


class TestSessionManagementPerformance:
    """Performance benchmarks for session management."""

    def test_multiple_sessions_performance(benchmark):
        """Benchmark managing multiple sessions."""
        from core.session_manager import SessionManager
        
        manager = SessionManager()
        
        def create_multiple_sessions():
            for i in range(50):
                session = manager.create_session()
                manager.add_message(session.session_id, "user", f"Message {i}")
            return True
        
        result = benchmark(create_multiple_sessions)
        assert result is not None

    def test_session_search_performance(benchmark):
        """Benchmark session search operations."""
        from core.session_manager import SessionManager
        
        manager = SessionManager()
        
        # Create sessions with messages
        for i in range(20):
            session = manager.create_session()
            manager.add_message(session.session_id, "user", f"Python {i}")
        
        def search_sessions():
            return manager.search_sessions("Python")
        
        result = benchmark(search_sessions)
        assert result is not None


class TestBackupPerformance:
    """Performance benchmarks for backup operations."""

    def test_backup_creation_performance(benchmark, tmp_path):
        """Benchmark backup creation."""
        from memory.memory_backup import get_backup_manager
        
        backup_path = tmp_path / "backups"
        backup_path.mkdir()
        
        manager = get_backup_manager()
        manager.backup_path = backup_path
        
        test_data = {"data": "x" * 100000}  # Large data
        
        def create_backup():
            return manager.create_backup(test_data)
        
        result = benchmark(create_backup)
        assert result is not None

    def test_backup_restoration_performance(benchmark, tmp_path):
        """Benchmark backup restoration."""
        from memory.memory_backup import get_backup_manager
        
        backup_path = tmp_path / "backups"
        backup_path.mkdir()
        
        manager = get_backup_manager()
        manager.backup_path = backup_path
        
        # Create backup
        test_data = {"data": "x" * 100000}
        backup_id = manager.create_backup(test_data)
        
        def restore_backup():
            return manager.restore_backup(backup_id)
        
        result = benchmark(restore_backup)
        assert result is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--benchmark-only'])
