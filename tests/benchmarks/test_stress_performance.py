"""
Performance benchmarks for stress testing
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestStressScenarios:
    """Performance benchmarks for stress testing scenarios."""

    def test_rapid_request_stress_performance(benchmark):
        """Benchmark rapid request stress."""
        from main import JarvisLive
        from core.session_manager import SessionManager
        
        jarvis = JarvisLive()
        session = SessionManager()
        
        def rapid_requests():
            # Simulate rapid user requests
            for i in range(100):
                jarvis.process_input(f"Query {i}")
            return True
        
        result = benchmark(rapid_requests)
        assert result is not None

    def test_large_context_stress_performance(benchmark):
        """Benchmark large context stress."""
        from core.multimodal_context import MultimodalContext
        import numpy as np
        
        context = MultimodalContext()
        
        def large_context():
            # Add large amount of context
            for i in range(1000):
                context.add_text(f"Context item {i}")
            for i in range(50):
                image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
                context.add_image(image, description=f"Image {i}")
            return context.get_context()
        
        result = benchmark(large_context)
        assert result is not None

    def test_memory_pressure_stress_performance(benchmark):
        """Benchmark memory pressure stress."""
        from memory.memory_manager import MemoryManager
        
        memory = MemoryManager()
        
        def memory_pressure():
            # Store large amount of data
            for i in range(10000):
                memory.update_memory(f"key{i}", {"data": "x" * 1000})
            return True
        
        result = benchmark(memory_pressure)
        assert result is not None

    def test_concurrent_sessions_stress_performance(benchmark):
        """Benchmark concurrent sessions stress."""
        from core.session_manager import SessionManager
        
        manager = SessionManager()
        
        def concurrent_sessions():
            # Create many concurrent sessions
            for i in range(500):
                session = manager.create_session()
                manager.add_message(session.session_id, "user", f"Message {i}")
            return True
        
        result = benchmark(concurrent_sessions)
        assert result is not None

    def test_workflow_complexity_stress_performance(benchmark):
        """Benchmark workflow complexity stress."""
        from core.workflow_engine import WorkflowEngine
        
        engine = WorkflowEngine()
        
        def complex_workflow():
            # Create very complex workflow
            steps = [
                {"name": f"Step {i}", "action": "test", "parameters": {"param": i}}
                for i in range(500)
            ]
            workflow = engine.create_workflow(
                name="Complex Workflow",
                goal="Test",
                description="Test",
                steps=steps
            )
            return workflow
        
        result = benchmark(complex_workflow)
        assert result is not None

    def test_vector_index_stress_performance(benchmark):
        """Benchmark vector index stress."""
        from core.vector_cache import VectorCache
        
        cache = VectorCache()
        
        def vector_index_stress():
            # Build large vector index
            for i in range(50000):
                cache.store(f"key{i}", [i/50000] * 768)
            return True
        
        result = benchmark(vector_index_stress)
        assert result is not None

    def test_api_rate_limit_stress_performance(benchmark):
        """Benchmark API rate limit stress."""
        from core.http_pool import HTTPPool
        
        pool = HTTPPool()
        pool.enable_rate_limiting = True
        pool.rate_limit_per_second = 100
        
        @patch('core.api_cache.requests')
        def api_stress(mock_requests):
            mock_response = MagicMock()
            mock_response.json.return_value = {"result": "success"}
            mock_response.status_code = 200
            mock_requests.get.return_value = mock_response
            
            # Make many rapid requests
            for i in range(200):
                pool.get(f"https://api.example.com/endpoint{i}")
            return True
        
        result = benchmark(api_stress)
        assert result is not None

    def test_backup_stress_performance(benchmark, tmp_path):
        """Benchmark backup stress."""
        from memory.memory_backup import get_backup_manager
        
        backup_path = tmp_path / "backups"
        backup_path.mkdir()
        
        manager = get_backup_manager()
        manager.backup_path = backup_path
        
        def backup_stress():
            # Create many backups
            for i in range(50):
                large_data = {"data": "x" * 100000}
                manager.create_backup(large_data)
            return True
        
        result = benchmark(backup_stress)
        assert result is not None

    def test_obsidian_stress_performance(benchmark, tmp_path):
        """Benchmark Obsidian stress."""
        from memory.obsidian_vault import get_obsidian_bridge
        
        # Create large vault
        for i in range(5000):
            (tmp_path / f"note{i}.md").write_text(f"# Note {i}\n" + "Content " * 100)
        
        obsidian = get_obsidian_bridge()
        obsidian.vault_path = tmp_path
        
        def obsidian_stress():
            return obsidian.sync_vault()
        
        result = benchmark(obsidian_stress)
        assert result is not None

    def test_tool_registration_stress_performance(benchmark):
        """Benchmark tool registration stress."""
        from core.tool_executor import ToolExecutor
        
        executor = ToolExecutor()
        
        def tool_registration_stress():
            # Register many tools
            for i in range(500):
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
        
        result = benchmark(tool_registration_stress)
        assert result is not None


class TestLongRunningOperations:
    """Performance benchmarks for long-running operations."""

    def test_long_session_performance(benchmark):
        """Benchmark long session duration."""
        from main import JarvisLive
        from core.session_manager import SessionManager
        
        jarvis = JarvisLive()
        session = SessionManager()
        
        def long_session():
            session_id = session.create_session().session_id
            # Simulate long conversation
            for i in range(1000):
                session.add_message(session_id, "user", f"Message {i}")
                session.add_message(session_id, "assistant", f"Response {i}")
            return True
        
        result = benchmark(long_session)
        assert result is not None

    def test_continuous_monitoring_performance(benchmark):
        """Benchmark continuous monitoring."""
        from core.performance_monitor import PerformanceMonitor
        
        monitor = PerformanceMonitor()
        monitor.enable_real_time_monitoring = True
        
        def continuous_monitoring():
            monitor.start_real_time_monitoring()
            # Simulate continuous operations
            for i in range(100):
                op_id = monitor.start_operation(f"op{i}")
                monitor.end_operation(op_id)
            monitor.stop_real_time_monitoring()
            return True
        
        result = benchmark(continuous_monitoring)
        assert result is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--benchmark-only'])
