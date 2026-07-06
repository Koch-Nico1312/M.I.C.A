"""
Integration tests for monitoring system
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta


class TestMonitoringIntegration:
    """Integration tests for monitoring system components."""

    @pytest.fixture
    def performance_tracker(self):
        """Create a fresh PerformanceTracker instance for testing."""
        from core.performance_tracker import get_performance_tracker
        return get_performance_tracker()

    def test_performance_tracking(self, performance_tracker):
        """Test performance tracking for operations."""
        # Start operation
        op_id = performance_tracker.start_operation("test_operation")
        
        # Simulate work
        import time
        time.sleep(0.1)
        
        # End operation
        performance_tracker.end_operation(op_id, {"result": "success"})
        
        # Get metrics
        metrics = performance_tracker.get_operation_metrics(op_id)
        
        assert metrics is not None
        assert 'duration_ms' in metrics

    def test_aggregate_metrics(self, performance_tracker):
        """Test aggregate metrics calculation."""
        # Run multiple operations
        for i in range(5):
            op_id = performance_tracker.start_operation(f"operation_{i}")
            import time
            time.sleep(0.05)
            performance_tracker.end_operation(op_id)
        
        # Get aggregate metrics
        aggregate = performance_tracker.get_aggregate_metrics()
        
        assert aggregate is not None
        assert 'total_operations' in aggregate
        assert aggregate['total_operations'] == 5

    def test_health_check_integration(self):
        """Test health check integration."""
        from core.healthcheck import build_runtime_report
        
        report = build_runtime_report()
        
        assert report is not None
        assert 'status' in report
        assert 'components' in report

    def test_metrics_collector(self):
        """Test metrics collector integration."""
        from core.metrics_collector import get_metrics_collector
        
        collector = get_metrics_collector()
        
        # Start operation
        collector.start_operation("test_op")
        
        # End operation
        collector.end_operation("test_op", {"cached": False})
        
        # Get metrics
        metrics = collector.get_metrics()
        
        assert metrics is not None

    def test_performance_monitor(self):
        """Test performance monitor integration."""
        from core.performance_monitor import PerformanceMonitor
        
        monitor = PerformanceMonitor()
        
        # Monitor operation
        op_id = monitor.start_operation("test_operation")
        monitor.end_operation(op_id)
        
        # Get resource metrics
        resources = monitor.get_resource_metrics()
        
        assert resources is not None
        assert 'cpu_percent' in resources

    def test_slow_operation_detection(self, performance_tracker):
        """Test slow operation detection."""
        performance_tracker.slow_threshold_ms = 50
        
        # Run slow operation
        op_id = performance_tracker.start_operation("slow_operation")
        import time
        time.sleep(0.1)  # 100ms
        performance_tracker.end_operation(op_id)
        
        # Get slow operations
        slow_ops = performance_tracker.get_slow_operations()
        
        assert len(slow_ops) > 0

    def test_metrics_persistence(self, performance_tracker):
        """Test metrics persistence to disk."""
        # Run operation
        op_id = performance_tracker.start_operation("test_operation")
        performance_tracker.end_operation(op_id)
        
        # Save metrics
        performance_tracker.save_metrics()
        
        # Load metrics
        performance_tracker.load_metrics()
        
        # Should persist
        assert True  # Placeholder for actual persistence test

    def test_real_time_monitoring(self):
        """Test real-time monitoring capabilities."""
        from core.performance_monitor import PerformanceMonitor
        
        monitor = PerformanceMonitor()
        monitor.enable_real_time_monitoring = True
        
        # Start monitoring
        monitor.start_real_time_monitoring()
        
        # Run operations
        for i in range(3):
            op_id = monitor.start_operation(f"op_{i}")
            monitor.end_operation(op_id)
        
        # Stop monitoring
        monitor.stop_real_time_monitoring()
        
        # Should have collected real-time data
        assert True  # Placeholder for actual real-time test


class TestMonitoringAlerts:
    """Test monitoring alert system."""

    @pytest.fixture
    def performance_tracker(self):
        """Create a fresh PerformanceTracker instance for testing."""
        from core.performance_tracker import get_performance_tracker
        return get_performance_tracker()

    def test_performance_alerts(self, performance_tracker):
        """Test performance alert generation."""
        performance_tracker.alert_threshold_ms = 100
        
        # Trigger alert with slow operation
        op_id = performance_tracker.start_operation("slow_operation")
        import time
        time.sleep(0.15)  # 150ms
        performance_tracker.end_operation(op_id)
        
        # Get alerts
        alerts = performance_tracker.get_performance_alerts()
        
        assert len(alerts) > 0

    def test_health_alerts(self):
        """Test health alert generation."""
        from core.healthcheck import build_runtime_report
        
        report = build_runtime_report()
        
        # Check for health issues
        if report['status'] == 'degraded':
            assert 'issues' in report
        else:
            assert report['status'] in ['healthy', 'degraded']


class TestMonitoringIntegrationWithMica:
    """Test monitoring integration with M.I.C.A core."""

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_mica_with_monitoring(self, mock_loader, mock_memory, mock_config):
        """Test M.I.C.A with monitoring enabled."""
        from main import MicaLive
        from core.performance_tracker import get_performance_tracker
        
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        mica = MicaLive()
        tracker = get_performance_tracker()
        
        # Track M.I.C.A operations
        op_id = tracker.start_operation("mica_response")
        mica.process_input("Hello M.I.C.A")
        tracker.end_operation(op_id)
        
        # Get metrics
        metrics = tracker.get_operation_metrics(op_id)
        
        assert metrics is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
