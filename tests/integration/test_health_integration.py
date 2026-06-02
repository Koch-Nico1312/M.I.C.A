"""
Integration tests for health check system
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestHealthIntegration:
    """Integration tests for health check system components."""

    @pytest.fixture
    def healthcheck(self):
        """Create a fresh health check instance for testing."""
        from core.healthcheck import build_runtime_report
        return build_runtime_report

    def test_health_check_report(self, healthcheck):
        """Test building health check report."""
        report = healthcheck()
        
        assert report is not None
        assert 'status' in report
        assert 'components' in report

    def test_component_health_check(self):
        """Test individual component health checks."""
        from core.healthcheck import check_component_health
        
        # Check various components
        components = [
            "memory",
            "audio",
            "llm",
            "actions",
            "config"
        ]
        
        for component in components:
            health = check_component_health(component)
            assert health is not None

    def test_health_dashboard_integration(self):
        """Test health dashboard integration."""
        from core.health_dashboard import get_health_dashboard
        
        dashboard = get_health_dashboard()
        
        # Get health status
        status = dashboard.get_health_status()
        
        assert status is not None

    def test_health_monitoring(self):
        """Test continuous health monitoring."""
        from core.health_monitor import HealthMonitor
        
        monitor = HealthMonitor()
        monitor.enable_monitoring = True
        
        # Start monitoring
        monitor.start_monitoring()
        
        # Check health
        health = monitor.check_health()
        
        assert health is not None

    def test_health_alerts(self):
        """Test health alert generation."""
        from core.health_monitor import HealthMonitor
        
        monitor = HealthMonitor()
        
        # Simulate health issue
        monitor.set_component_status("memory", "degraded")
        
        # Check for alerts
        alerts = monitor.get_health_alerts()
        
        assert alerts is not None

    def test_health_with_jarvis(self):
        """Test health check integration with Jarvis."""
        from main import JarvisLive
        from core.healthcheck import build_runtime_report
        
        jarvis = JarvisLive()
        report = build_runtime_report()
        
        # Jarvis should be able to report its health
        assert report is not None

    def test_health_with_dependencies(self):
        """Test health check with dependency validation."""
        from core.healthcheck import check_dependencies
        
        dependencies = check_dependencies()
        
        assert dependencies is not None
        assert 'status' in dependencies

    def test_health_with_api(self):
        """Test health check with API connectivity."""
        from core.healthcheck import check_api_connectivity
        
        # Check API connectivity
        connectivity = check_api_connectivity("gemini")
        
        assert connectivity is not None

    def test_health_with_disk_space(self):
        """Test health check with disk space validation."""
        from core.healthcheck import check_disk_space
        
        # Check disk space
        disk_space = check_disk_space()
        
        assert disk_space is not None
        assert 'available_gb' in disk_space

    def test_health_with_memory_usage(self):
        """Test health check with memory usage."""
        from core.healthcheck import check_memory_usage
        
        # Check memory usage
        memory_usage = check_memory_usage()
        
        assert memory_usage is not None
        assert 'percent' in memory_usage


class TestHealthErrorHandling:
    """Error handling tests for health check system."""

    def test_component_failure_handling(self):
        """Test handling of component failures."""
        from core.healthcheck import check_component_health
        
        # Check non-existent component
        health = check_component_health("nonexistent_component")
        
        # Should handle gracefully
        assert health is not None

    def test_health_check_timeout(self):
        """Test handling of health check timeouts."""
        from core.healthcheck import build_runtime_report
        
        # Build report with timeout
        report = build_runtime_report(timeout=1)
        
        # Should handle timeout
        assert report is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
