"""
Performance benchmarks for concurrent operations
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock


class TestConcurrentMemoryOperations:
    """Performance benchmarks for concurrent memory operations."""

    def test_concurrent_memory_writes_performance(benchmark):
        """Benchmark concurrent memory write operations."""
        from memory.memory_manager import MemoryManager
        
        memory = MemoryManager()
        
        async def concurrent_writes():
            tasks = [
                memory.update_memory_async(f"key{i}", {"value": i})
                for i in range(50)
            ]
            results = await asyncio.gather(*tasks)
            return results
        
        result = benchmark(asyncio.run, concurrent_writes())
        assert result is not None

    def test_concurrent_memory_reads_performance(benchmark):
        """Benchmark concurrent memory read operations."""
        from memory.memory_manager import MemoryManager
        
        memory = MemoryManager()
        
        # Pre-populate memory
        for i in range(50):
            memory.update_memory(f"key{i}", {"value": i})
        
        async def concurrent_reads():
            tasks = [
                memory.load_memory_async(f"key{i}")
                for i in range(50)
            ]
            results = await asyncio.gather(*tasks)
            return results
        
        result = benchmark(asyncio.run, concurrent_reads())
        assert result is not None


class TestConcurrentAPIRequests:
    """Performance benchmarks for concurrent API requests."""

    @patch('core.api_cache.requests')
    def test_concurrent_api_calls_performance(self, mock_requests, benchmark):
        """Benchmark concurrent API calls."""
        from core.http_pool import HTTPPool
        
        pool = HTTPPool()
        
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": "success"}
        mock_response.status_code = 200
        mock_requests.get.return_value = mock_response
        
        async def concurrent_api_calls():
            tasks = [
                pool.get_async(f"https://api.example.com/endpoint{i}")
                for i in range(20)
            ]
            results = await asyncio.gather(*tasks)
            return results
        
        result = benchmark(asyncio.run, concurrent_api_calls())
        assert result is not None


class TestConcurrentToolExecution:
    """Performance benchmarks for concurrent tool execution."""

    def test_concurrent_tool_execution_performance(benchmark):
        """Benchmark concurrent tool execution."""
        from core.tool_executor import ToolExecutor
        
        executor = ToolExecutor()
        
        # Register tools
        for i in range(20):
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
        
        async def concurrent_tool_execution():
            tasks = [
                executor.execute_tool_async(f"tool{i}", {})
                for i in range(20)
            ]
            results = await asyncio.gather(*tasks)
            return results
        
        result = benchmark(asyncio.run, concurrent_tool_execution())
        assert result is not None


class TestConcurrentWorkflowExecution:
    """Performance benchmarks for concurrent workflow execution."""

    def test_concurrent_workflow_submission_performance(benchmark):
        """Benchmark concurrent workflow submission."""
        from core.workflow_engine import WorkflowEngine
        
        engine = WorkflowEngine()
        
        async def concurrent_workflow_submission():
            tasks = []
            for i in range(10):
                workflow = engine.create_workflow(
                    name=f"Workflow {i}",
                    goal="Test",
                    description="Test",
                    steps=[{"name": "Step 1", "action": "test", "parameters": {}}]
                )
                tasks.append(engine.submit_workflow_async(workflow))
            results = await asyncio.gather(*tasks)
            return results
        
        result = benchmark(asyncio.run, concurrent_workflow_submission())
        assert result is not None


class TestConcurrentSessionOperations:
    """Performance benchmarks for concurrent session operations."""

    def test_concurrent_session_creation_performance(benchmark):
        """Benchmark concurrent session creation."""
        from core.session_manager import SessionManager
        
        manager = SessionManager()
        
        async def concurrent_session_creation():
            tasks = [
                manager.create_session_async()
                for i in range(30)
            ]
            results = await asyncio.gather(*tasks)
            return results
        
        result = benchmark(asyncio.run, concurrent_session_creation())
        assert result is not None

    def test_concurrent_message_addition_performance(benchmark):
        """Benchmark concurrent message addition."""
        from core.session_manager import SessionManager
        
        manager = SessionManager()
        
        # Create sessions
        session_ids = []
        for i in range(20):
            session = manager.create_session()
            session_ids.append(session.session_id)
        
        async def concurrent_message_addition():
            tasks = [
                manager.add_message_async(sid, "user", f"Message {i}")
                for i, sid in enumerate(session_ids)
            ]
            results = await asyncio.gather(*tasks)
            return results
        
        result = benchmark(asyncio.run, concurrent_message_addition())
        assert result is not None


class TestConcurrentVectorOperations:
    """Performance benchmarks for concurrent vector operations."""

    def test_concurrent_vector_storage_performance(benchmark):
        """Benchmark concurrent vector storage."""
        from core.vector_cache import VectorCache
        
        cache = VectorCache()
        
        async def concurrent_vector_storage():
            tasks = [
                cache.store_async(f"key{i}", [i/100] * 768)
                for i in range(50)
            ]
            results = await asyncio.gather(*tasks)
            return results
        
        result = benchmark(asyncio.run, concurrent_vector_storage())
        assert result is not None

    def test_concurrent_vector_search_performance(benchmark):
        """Benchmark concurrent vector search."""
        from core.vector_cache import VectorCache
        
        cache = VectorCache()
        
        # Store vectors
        for i in range(100):
            cache.store(f"key{i}", [i/100] * 768)
        
        async def concurrent_vector_search():
            tasks = [
                cache.similarity_search_async([i/50] * 768, top_k=5)
                for i in range(10)
            ]
            results = await asyncio.gather(*tasks)
            return results
        
        result = benchmark(asyncio.run, concurrent_vector_search())
        assert result is not None


class TestConcurrentBackupOperations:
    """Performance benchmarks for concurrent backup operations."""

    def test_concurrent_backup_creation_performance(benchmark, tmp_path):
        """Benchmark concurrent backup creation."""
        from memory.memory_backup import get_backup_manager
        
        backup_path = tmp_path / "backups"
        backup_path.mkdir()
        
        manager = get_backup_manager()
        manager.backup_path = backup_path
        
        async def concurrent_backup_creation():
            tasks = [
                manager.create_backup_async({"data": f"backup{i}"})
                for i in range(10)
            ]
            results = await asyncio.gather(*tasks)
            return results
        
        result = benchmark(asyncio.run, concurrent_backup_creation())
        assert result is not None


class TestConcurrentJarvisRequests:
    """Performance benchmarks for concurrent Jarvis requests."""

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_concurrent_jarvis_requests_performance(self, mock_loader, mock_memory, mock_config, benchmark):
        """Benchmark concurrent Jarvis requests."""
        from main import JarvisLive
        
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        jarvis = JarvisLive()
        
        async def concurrent_jarvis_requests():
            tasks = [
                jarvis.process_input_async(f"Query {i}")
                for i in range(10)
            ]
            results = await asyncio.gather(*tasks)
            return results
        
        result = benchmark(asyncio.run, concurrent_jarvis_requests())
        assert result is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--benchmark-only'])
