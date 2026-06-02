"""
Tests for the dependency injection system.
"""

import pytest

from core.dependency_injection import ServiceContainer, get_container, register_core_services


class TestServiceContainer:
    """Test cases for ServiceContainer."""
    
    def test_singleton_registration(self):
        """Test singleton service registration and retrieval."""
        container = ServiceContainer()
        
        def factory():
            return {"value": 42}
        
        container.register_singleton("test_service", factory)
        
        assert container.has("test_service")
        result1 = container.get("test_service")
        result2 = container.get("test_service")
        
        assert result1 == {"value": 42}
        assert result1 is result2  # Same instance
    
    def test_transient_registration(self):
        """Test transient service registration and retrieval."""
        container = ServiceContainer()
        
        class TestService:
            def __init__(self):
                self.value = 42
        
        def factory():
            return TestService()
        
        container.register_transient(TestService, factory)
        
        result1 = container.resolve(TestService)
        result2 = container.resolve(TestService)
        
        assert result1.value == 42
        assert result2.value == 42
        assert result1 is not result2  # Different instances
    
    def test_get_nonexistent_service(self):
        """Test getting a non-existent service raises KeyError."""
        container = ServiceContainer()
        
        with pytest.raises(KeyError):
            container.get("nonexistent")
    
    def test_resolve_nonexistent_service(self):
        """Test resolving a non-existent service type raises KeyError."""
        container = ServiceContainer()
        
        class TestService:
            pass
        
        with pytest.raises(KeyError):
            container.resolve(TestService)
    
    def test_clear(self):
        """Test clearing all services."""
        container = ServiceContainer()
        
        container.register_singleton("test", lambda: {"value": 42})
        assert container.has("test")
        
        container.clear()
        assert not container.has("test")


class TestGlobalContainer:
    """Test cases for global container instance."""
    
    def test_get_container_returns_same_instance(self):
        """Test that get_container returns the same instance."""
        container1 = get_container()
        container2 = get_container()
        
        assert container1 is container2
    
    def test_register_core_services(self):
        """Test registering core services."""
        container = get_container()
        register_core_services()
        
        # Check that core services are registered
        assert container.has("action_history")
        assert container.has("approval_flow")
        assert container.has("logger")
