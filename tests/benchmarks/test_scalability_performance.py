"""
Performance benchmarks for scalability testing
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestMemoryScalability:
    """Performance benchmarks for memory scalability."""

    def test_memory_1k_operations_performance(benchmark):
        """Benchmark memory with 1K operations."""
        from memory.memory_manager import MemoryManager
        
        memory = MemoryManager()
        
        def memory_1k_ops():
            for i in range(1000):
                memory.update_memory(f"key{i}", {"value": i})
            return True
        
        result = benchmark(memory_1k_ops)
        assert result is not None

    def test_memory_10k_operations_performance(benchmark):
        """Benchmark memory with 10K operations."""
        from memory.memory_manager import MemoryManager
        
        memory = MemoryManager()
        
        def memory_10k_ops():
            for i in range(10000):
                memory.update_memory(f"key{i}", {"value": i})
            return True
        
        result = benchmark(memory_10k_ops)
        assert result is not None


class TestVectorScalability:
    """Performance benchmarks for vector scalability."""

    def test_vector_1k_search_performance(benchmark):
        """Benchmark vector search with 1K vectors."""
        from core.vector_cache import VectorCache
        
        cache = VectorCache()
        
        # Store 1K vectors
        for i in range(1000):
            cache.store(f"key{i}", [i/1000] * 768)
        
        query = [0.5] * 768
        
        def search_1k():
            return cache.similarity_search(query, top_k=10)
        
        result = benchmark(search_1k)
        assert result is not None

    def test_vector_10k_search_performance(benchmark):
        """Benchmark vector search with 10K vectors."""
        from core.vector_cache import VectorCache
        
        cache = VectorCache()
        
        # Store 10K vectors
        for i in range(10000):
            cache.store(f"key{i}", [i/10000] * 768)
        
        query = [0.5] * 768
        
        def search_10k():
            return cache.similarity_search(query, top_k=10)
        
        result = benchmark(search_10k)
        assert result is not None


class TestSessionScalability:
    """Performance benchmarks for session scalability."""

    def test_session_100_management_performance(benchmark):
        """Benchmark managing 100 sessions."""
        from core.session_manager import SessionManager
        
        manager = SessionManager()
        
        def manage_100_sessions():
            for i in range(100):
                session = manager.create_session()
                manager.add_message(session.session_id, "user", f"Message {i}")
            return True
        
        result = benchmark(manage_100_sessions)
        assert result is not None

    def test_session_1000_management_performance(benchmark):
        """Benchmark managing 1000 sessions."""
        from core.session_manager import SessionManager
        
        manager = SessionManager()
        
        def manage_1000_sessions():
            for i in range(1000):
                session = manager.create_session()
                manager.add_message(session.session_id, "user", f"Message {i}")
            return True
        
        result = benchmark(manage_1000_sessions)
        assert result is not None


class TestWorkflowScalability:
    """Performance benchmarks for workflow scalability."""

    def test_workflow_100_steps_performance(benchmark):
        """Benchmark workflow with 100 steps."""
        from core.workflow_engine import WorkflowEngine
        
        engine = WorkflowEngine()
        
        steps = [
            {"name": f"Step {i}", "action": "test", "parameters": {}}
            for i in range(100)
        ]
        
        def create_100_step_workflow():
            return engine.create_workflow(
                name="Large Workflow",
                goal="Test",
                description="Test",
                steps=steps
            )
        
        result = benchmark(create_100_step_workflow)
        assert result is not None


class TestAPIScalability:
    """Performance benchmarks for API scalability."""

    @patch('core.api_cache.requests')
    def test_api_100_requests_performance(self, mock_requests, benchmark):
        """Benchmark 100 API requests."""
        from core.http_pool import HTTPPool
        
        pool = HTTPPool()
        
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": "success"}
        mock_response.status_code = 200
        mock_requests.get.return_value = mock_response
        
        def api_100_requests():
            for i in range(100):
                pool.get(f"https://api.example.com/endpoint{i}")
            return True
        
        result = benchmark(api_100_requests)
        assert result is not None


class TestCacheScalability:
    """Performance benchmarks for cache scalability."""

    def test_cache_1000_entries_performance(benchmark):
        """Benchmark cache with 1000 entries."""
        from core.api_cache import APICache
        
        cache = APICache()
        
        def cache_1000_entries():
            for i in range(1000):
                cache.cache_response(f"endpoint{i}", {"data": f"value{i}"}, ttl=300)
            return True
        
        result = benchmark(cache_1000_entries)
        assert result is not None

    def test_cache_10000_entries_performance(benchmark):
        """Benchmark cache with 10000 entries."""
        from core.api_cache import APICache
        
        cache = APICache()
        
        def cache_10000_entries():
            for i in range(10000):
                cache.cache_response(f"endpoint{i}", {"data": f"value{i}"}, ttl=300)
            return True
        
        result = benchmark(cache_10000_entries)
        assert result is not None


class TestBackupScalability:
    """Performance benchmarks for backup scalability."""

    def test_backup_large_data_performance(benchmark, tmp_path):
        """Benchmark backing up large data."""
        from memory.memory_backup import get_backup_manager
        
        backup_path = tmp_path / "backups"
        backup_path.mkdir()
        
        manager = get_backup_manager()
        manager.backup_path = backup_path
        
        # Create large data (10MB)
        large_data = {"data": "x" * 10000000}
        
        def backup_large_data():
            return manager.create_backup(large_data)
        
        result = benchmark(backup_large_data)
        assert result is not None


class TestObsidianScalability:
    """Performance benchmarks for Obsidian scalability."""

    def test_obsidian_1000_notes_performance(benchmark, tmp_path):
        """Benchmark Obsidian with 1000 notes."""
        from memory.obsidian_vault import get_obsidian_bridge
        
        # Create 1000 notes
        for i in range(1000):
            (tmp_path / f"note{i}.md").write_text(f"# Note {i}\nContent here")
        
        obsidian = get_obsidian_bridge()
        obsidian.vault_path = tmp_path
        
        def sync_1000_notes():
            return obsidian.sync_vault()
        
        result = benchmark(sync_1000_notes)
        assert result is not None


class TestToolScalability:
    """Performance benchmarks for tool scalability."""

    def test_tool_100_registration_performance(benchmark):
        """Benchmark registering 100 tools."""
        from core.tool_executor import ToolExecutor
        
        executor = ToolExecutor()
        
        def register_100_tools():
            for i in range(100):
                def make_tool(idx):
                    def tool_func():
                        return f"result{idx}"
                    return tool_func
                
                executor.register_tool(
                    f"tool{i}",
                    make_tool(i),
                    f"Tool {i}",
                    {}
                )
            return True
        
        result = benchmark(register_100_tools)
        assert result is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--benchmark-only'])
