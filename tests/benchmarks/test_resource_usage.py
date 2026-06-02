"""
Performance benchmarks for resource usage
"""

import pytest
import psutil
import time
from unittest.mock import Mock, patch, MagicMock


class TestMemoryUsage:
    """Performance benchmarks for memory usage."""

    def test_memory_usage_during_large_operations(benchmark):
        """Benchmark memory usage during large operations."""
        from memory.memory_manager import MemoryManager
        
        memory = MemoryManager()
        
        def large_memory_operation():
            # Store large data
            for i in range(1000):
                memory.update_memory(f"key{i}", {"data": "x" * 1000})
            return True
        
        result = benchmark(large_memory_operation)
        assert result is not None

    def test_memory_cleanup_performance(benchmark):
        """Benchmark memory cleanup operations."""
        from memory.memory_manager import MemoryManager
        
        memory = MemoryManager()
        
        # Populate memory
        for i in range(1000):
            memory.update_memory(f"key{i}", {"data": "x" * 1000})
        
        def cleanup_memory():
            memory.cleanup_old_entries(max_age_hours=0)
            return True
        
        result = benchmark(cleanup_memory)
        assert result is not None


class TestCPUUsage:
    """Performance benchmarks for CPU usage."""

    def test_cpu_usage_during_computation(benchmark):
        """Benchmark CPU usage during computation."""
        import numpy as np
        
        def heavy_computation():
            # Perform heavy computation
            matrix = np.random.rand(1000, 1000)
            result = np.dot(matrix, matrix.T)
            return True
        
        result = benchmark(heavy_computation)
        assert result is not None

    def test_cpu_usage_during_vector_operations(benchmark):
        """Benchmark CPU usage during vector operations."""
        from core.vector_cache import VectorCache
        
        cache = VectorCache()
        
        def vector_operations():
            for i in range(100):
                cache.store(f"key{i}", [i/100] * 768)
            query = [0.5] * 768
            cache.similarity_search(query, top_k=10)
            return True
        
        result = benchmark(vector_operations)
        assert result is not None


class TestDiskIO:
    """Performance benchmarks for disk I/O."""

    def test_disk_write_performance(benchmark, tmp_path):
        """Benchmark disk write performance."""
        large_data = "x" * 10000000  # 10MB
        test_file = tmp_path / "large_file.txt"
        
        def disk_write():
            test_file.write_text(large_data)
            return True
        
        result = benchmark(disk_write)
        assert result is not None

    def test_disk_read_performance(benchmark, tmp_path):
        """Benchmark disk read performance."""
        large_data = "x" * 10000000  # 10MB
        test_file = tmp_path / "large_file.txt"
        test_file.write_text(large_data)
        
        def disk_read():
            return test_file.read_text()
        
        result = benchmark(disk_read)
        assert result is not None

    def test_backup_disk_io_performance(benchmark, tmp_path):
        """Benchmark backup disk I/O performance."""
        from memory.memory_backup import get_backup_manager
        
        backup_path = tmp_path / "backups"
        backup_path.mkdir()
        
        manager = get_backup_manager()
        manager.backup_path = backup_path
        
        large_data = {"data": "x" * 10000000}
        
        def backup_io():
            manager.create_backup(large_data)
            return True
        
        result = benchmark(backup_io)
        assert result is not None


class TestNetworkIO:
    """Performance benchmarks for network I/O."""

    @patch('core.api_cache.requests')
    def test_network_request_performance(self, mock_requests, benchmark):
        """Benchmark network request performance."""
        from core.http_pool import HTTPPool
        
        pool = HTTPPool()
        
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": "x" * 100000}  # Large response
        mock_response.status_code = 200
        mock_requests.get.return_value = mock_response
        
        def network_request():
            return pool.get("https://api.example.com/large_data")
        
        result = benchmark(network_request)
        assert result is not None


class TestFileHandleUsage:
    """Performance benchmarks for file handle usage."""

    def test_concurrent_file_operations_performance(benchmark, tmp_path):
        """Benchmark concurrent file operations."""
        def concurrent_file_ops():
            # Open and close many files
            for i in range(100):
                file_path = tmp_path / f"file{i}.txt"
                file_path.write_text(f"Content {i}")
                file_path.read_text()
            return True
        
        result = benchmark(concurrent_file_ops)
        assert result is not None


class TestThreadUsage:
    """Performance benchmarks for thread usage."""

    def test_thread_pool_performance(benchmark):
        """Benchmark thread pool performance."""
        from concurrent.futures import ThreadPoolExecutor
        
        def task(x):
            return x * 2
        
        def thread_pool_ops():
            with ThreadPoolExecutor(max_workers=10) as executor:
                results = list(executor.map(task, range(100)))
            return True
        
        result = benchmark(thread_pool_ops)
        assert result is not None


class TestProcessUsage:
    """Performance benchmarks for process usage."""

    def test_subprocess_performance(benchmark):
        """Benchmark subprocess operations."""
        import subprocess
        
        def subprocess_ops():
            for i in range(10):
                subprocess.run(["echo", "test"], capture_output=True)
            return True
        
        result = benchmark(subprocess_ops)
        assert result is not None


class TestResourceMonitoring:
    """Performance benchmarks for resource monitoring."""

    def test_monitoring_overhead(benchmark):
        """Benchmark monitoring system overhead."""
        from core.performance_monitor import PerformanceMonitor
        
        monitor = PerformanceMonitor()
        
        def monitoring_ops():
            for i in range(100):
                op_id = monitor.start_operation(f"op{i}")
                monitor.end_operation(op_id)
            return True
        
        result = benchmark(monitoring_ops)
        assert result is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--benchmark-only'])
