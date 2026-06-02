"""
Dependency Injection Container for JARVIS AI Assistant.

This module provides a simple dependency injection system to manage service lifecycles
and provide dependencies to components that need them.

Example:
    >>> from core.dependency_injection import get_container
    >>> container = get_container()
    >>> 
    >>> # Register a singleton service
    >>> container.register_singleton("my_service", lambda: MyService())
    >>> 
    >>> # Get the service (same instance every time)
    >>> service = container.get("my_service")
"""

from typing import Any, Callable, Dict, Optional, TypeVar, Type

T = TypeVar("T")


class ServiceContainer:
    """
    Simple dependency injection container for managing service lifecycles.
    
    Supports:
    - Singleton services (created once, reused)
    - Transient services (created each time)
    - Factory functions for complex initialization
    """
    
    def __init__(self):
        self._singletons: Dict[str, Any] = {}
        self._factories: Dict[str, Callable[[], Any]] = {}
        self._transients: Dict[Type, Callable[[], Any]] = {}
    
    def register_singleton(self, name: str, factory: Callable[[], T]) -> None:
        """
        Register a singleton service.
        
        Args:
            name: Service name/identifier
            factory: Factory function to create the service
        """
        self._factories[name] = factory
    
    def register_transient(self, service_type: Type[T], factory: Callable[[], T]) -> None:
        """
        Register a transient service (created each time).
        
        Args:
            service_type: Service type/class
            factory: Factory function to create the service
        """
        self._transients[service_type] = factory
    
    def get(self, name: str) -> Any:
        """
        Get a singleton service by name.
        
        Args:
            name: Service name/identifier
            
        Returns:
            The service instance
            
        Raises:
            KeyError: If service not registered
        """
        if name not in self._singletons:
            if name not in self._factories:
                raise KeyError(f"Service '{name}' not registered")
            self._singletons[name] = self._factories[name]()
        return self._singletons[name]
    
    def resolve(self, service_type: Type[T]) -> T:
        """
        Resolve a transient service by type.
        
        Args:
            service_type: Service type/class
            
        Returns:
            New instance of the service
            
        Raises:
            KeyError: If service type not registered
        """
        if service_type not in self._transients:
            raise KeyError(f"Service type '{service_type}' not registered")
        return self._transients[service_type]()
    
    def has(self, name: str) -> bool:
        """
        Check if a singleton service is registered.
        
        Args:
            name: Service name/identifier
            
        Returns:
            True if service is registered
        """
        return name in self._factories
    
    def clear(self) -> None:
        """Clear all registered services and singletons."""
        self._singletons.clear()
        self._factories.clear()
        self._transients.clear()


# Global container instance
_container: Optional[ServiceContainer] = None


def get_container() -> ServiceContainer:
    """
    Get the global service container instance.
    
    Returns:
        The global ServiceContainer instance
    """
    global _container
    if _container is None:
        _container = ServiceContainer()
    return _container


def register_core_services() -> None:
    """
    Register core JARVIS services in the dependency injection container.
    
    This should be called during application initialization to set up
    the core services that are used throughout the application.
    """
    container = get_container()
    
    # Register core services as singletons
    # These will be initialized lazily on first access
    from core.action_history import get_action_history
    from core.approval_flow import get_approval_flow
    from core.background_task_manager import get_background_task_manager
    from core.logger import get_logger
    from core.memory_manager import get_memory_manager
    from core.metrics_collector import get_metrics_collector
    from core.performance_monitor import get_performance_monitor
    from core.performance_tracker import get_performance_tracker
    from core.plugin_system import get_plugin_manager
    from core.semantic_search import get_semantic_search
    from core.session_manager import get_session_manager
    from core.workflow_engine import get_workflow_engine
    
    container.register_singleton("action_history", get_action_history)
    container.register_singleton("approval_flow", get_approval_flow)
    container.register_singleton("background_task_manager", get_background_task_manager)
    container.register_singleton("logger", lambda: get_logger(__name__))
    container.register_singleton("memory_manager", get_memory_manager)
    container.register_singleton("metrics_collector", get_metrics_collector)
    container.register_singleton("performance_monitor", get_performance_monitor)
    container.register_singleton("performance_tracker", get_performance_tracker)
    container.register_singleton("plugin_manager", get_plugin_manager)
    container.register_singleton("semantic_search", get_semantic_search)
    container.register_singleton("session_manager", get_session_manager)
    container.register_singleton("workflow_engine", get_workflow_engine)
