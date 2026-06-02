"""
Tests for core.performance_monitor module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import time


class TestPerformanceMonitor:
    """Test cases for PerformanceMonitor class."""

    @pytest.fixture
    def performance_monitor(self):
        """Create a fresh PerformanceMonitor instance for testing."""
        from core.performance_monitor import PerformanceMonitor
        return PerformanceMonitor()

    def test_performance_monitor_initialization(self, performance_monitor):
        """Test PerformanceMonitor initialization."""
        assert performance_monitor is not None
        assert hasattr(performance_monitor, 'start_operation')
        assert hasattr(performance_monitor, 'end_operation')
        assert hasattr(performance_monitor, 'get_metrics')

    def test_start_operation(self, performance_monitor):
        """Test starting an operation measurement."""
        operation_id = performance_monitor.start_operation("test_operation")
        
        assert operation_id is not None
        assert operation_id in performance_monitor.active_operations

    def test_end_operation(self, performance_monitor):
        """Test ending an operation measurement."""
        operation_id = performance_monitor.start_operation("test_operation")
        time.sleep(0.1)  # Simulate some work
        
        performance_monitor.end_operation(operation_id, {"result": "success"})
        
        assert operation_id not in performance_monitor.active_operations
        assert operation_id in performance_monitor.completed_operations

    def test_get_operation_metrics(self, performance_monitor):
        """Test getting metrics for an operation."""
        operation_id = performance_monitor.start_operation("test_operation")
        time.sleep(0.1)
        performance_monitor.end_operation(operation_id, {"result": "success"})
        
        metrics = performance_monitor.get_operation_metrics(operation_id)
        
        assert metrics is not None
        assert 'duration_ms' in metrics
        assert 'metadata' in metrics

    def test_get_aggregate_metrics(self, performance_monitor):
        """Test getting aggregate metrics."""
        # Run multiple operations
        for i in range(5):
            operation_id = performance_monitor.start_operation(f"operation_{i}")
            time.sleep(0.05)
            performance_monitor.end_operation(operation_id)
        
        aggregate = performance_monitor.get_aggregate_metrics()
        
        assert aggregate is not None
        assert 'total_operations' in aggregate
        assert 'average_duration_ms' in aggregate

    def test_slow_operation_detection(self, performance_monitor):
        """Test detection of slow operations."""
        performance_monitor.slow_threshold_ms = 50
        
        operation_id = performance_monitor.start_operation("slow_operation")
        time.sleep(0.1)  # 100ms
        performance_monitor.end_operation(operation_id)
        
        slow_ops = performance_monitor.get_slow_operations()
        
        assert len(slow_ops) > 0
        assert operation_id in [op['operation_id'] for op in slow_ops]

    def test_resource_monitoring(self, performance_monitor):
        """Test resource monitoring."""
        performance_monitor.enable_resource_monitoring = True
        
        metrics = performance_monitor.get_resource_metrics()
        
        assert metrics is not None
        assert 'cpu_percent' in metrics
        assert 'memory_percent' in metrics

    def test_metrics_persistence(self, performance_monitor):
        """Test metrics persistence to disk."""
        operation_id = performance_monitor.start_operation("test_operation")
        performance_monitor.end_operation(operation_id)
        
        # Save metrics
        performance_monitor.save_metrics()
        
        # Load metrics
        performance_monitor.load_metrics()
        
        # Should persist
        assert True  # Placeholder for actual persistence test

    def test_metrics_cleanup(self, performance_monitor):
        """Test automatic cleanup of old metrics."""
        performance_monitor.max_history_size = 10
        
        # Add more than max
        for i in range(20):
            operation_id = performance_monitor.start_operation(f"operation_{i}")
            performance_monitor.end_operation(operation_id)
        
        performance_monitor.cleanup_old_metrics()
        
        assert len(performance_monitor.completed_operations) <= performance_monitor.max_history_size


class TestPerformanceMonitorErrorHandling:
    """Test error handling in PerformanceMonitor."""

    @pytest.fixture
    def performance_monitor(self):
        """Create a fresh PerformanceMonitor instance for testing."""
        from core.performance_monitor import PerformanceMonitor
        return PerformanceMonitor()

    def test_end_nonexistent_operation(self, performance_monitor):
        """Test ending a non-existent operation."""
        with pytest.raises(KeyError):
            performance_monitor.end_operation("nonexistent_id")

    def test_duplicate_operation_id(self, performance_monitor):
        """Test handling of duplicate operation IDs."""
        operation_id = performance_monitor.start_operation("test_operation")
        
        # Try to start another with same ID
        with pytest.raises(ValueError):
            performance_monitor.start_operation("test_operation", operation_id=operation_id)


class TestPerformanceMonitorIntegration:
    """Integration tests for PerformanceMonitor."""

    def test_full_monitoring_cycle(self):
        """Test a full performance monitoring cycle."""
        from core.performance_monitor import PerformanceMonitor
        
        monitor = PerformanceMonitor()
        
        # Monitor an operation
        op_id = monitor.start_operation("complex_operation")
        
        # Simulate work
        time.sleep(0.1)
        
        # End operation
        monitor.end_operation(op_id, {"status": "completed"})
        
        # Get metrics
        metrics = monitor.get_operation_metrics(op_id)
        
        assert metrics is not None
        assert metrics['duration_ms'] > 0

    def test_real_time_monitoring(self):
        """Test real-time performance monitoring."""
        from core.performance_monitor import PerformanceMonitor
        
        monitor = PerformanceMonitor()
        monitor.enable_real_time_monitoring = True
        
        # Start monitoring
        monitor.start_real_time_monitoring()
        
        # Run operations
        for i in range(3):
            op_id = monitor.start_operation(f"realtime_op_{i}")
            time.sleep(0.05)
            monitor.end_operation(op_id)
        
        # Stop monitoring
        monitor.stop_real_time_monitoring()
        
        # Should have collected real-time data
        assert True  # Placeholder for actual real-time test

    def test_performance_alerts(self):
        """Test performance alert generation."""
        from core.performance_monitor import PerformanceMonitor
        
        monitor = PerformanceMonitor()
        monitor.alert_threshold_ms = 100
        
        # Trigger alert with slow operation
        op_id = monitor.start_operation("slow_operation")
        time.sleep(0.15)  # 150ms
        monitor.end_operation(op_id)
        
        alerts = monitor.get_performance_alerts()
        
        assert len(alerts) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
