"""
Tests for the centralized error handling system.
"""

import pytest

from core.error_handler import (
    ActionExecutionError,
    APIError,
    ConfigurationError,
    ErrorHandler,
    ErrorSeverity,
    JarvisError,
    ResourceError,
    get_error_handler,
    handle_errors,
)


class TestJarvisError:
    """Test cases for JarvisError base class."""
    
    def test_basic_error_creation(self):
        """Test basic error creation."""
        error = JarvisError("Test error")
        assert error.message == "Test error"
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.recoverable is True
        assert error.context == {}
    
    def test_error_with_severity(self):
        """Test error with custom severity."""
        error = JarvisError("Test error", severity=ErrorSeverity.HIGH)
        assert error.severity == ErrorSeverity.HIGH
    
    def test_error_with_context(self):
        """Test error with context."""
        context = {"key": "value"}
        error = JarvisError("Test error", context=context)
        assert error.context == context


class TestSpecificErrors:
    """Test cases for specific error types."""
    
    def test_configuration_error(self):
        """Test ConfigurationError creation."""
        error = ConfigurationError("Config file not found")
        assert error.message == "Config file not found"
        assert error.severity == ErrorSeverity.HIGH
        assert error.recoverable is False
    
    def test_action_execution_error(self):
        """Test ActionExecutionError creation."""
        error = ActionExecutionError("test_action", "Execution failed")
        assert error.action_name == "test_action"
        assert error.context["action_name"] == "test_action"
    
    def test_api_error(self):
        """Test APIError creation."""
        error = APIError("gemini", "API call failed")
        assert error.service == "gemini"
        assert error.context["service"] == "gemini"
    
    def test_resource_error(self):
        """Test ResourceError creation."""
        error = ResourceError("memory", "Out of memory")
        assert error.resource == "memory"
        assert error.context["resource"] == "memory"


class TestErrorHandler:
    """Test cases for ErrorHandler."""
    
    def test_handle_error_without_handler(self):
        """Test handling error without registered handler."""
        handler = ErrorHandler()
        error = Exception("Test error")
        
        result = handler.handle(error, raise_original=False)
        assert result is None
        assert handler.get_error_count() == 1
    
    def test_handle_error_with_handler(self):
        """Test handling error with registered handler."""
        handler = ErrorHandler()
        error = ValueError("Test error")
        
        def custom_handler(e):
            return "handled"
        
        handler.register_handler(ValueError, custom_handler)
        result = handler.handle(error)
        
        assert result == "handled"
    
    def test_error_history(self):
        """Test error history tracking."""
        handler = ErrorHandler()
        
        handler.handle(Exception("Error 1"))
        handler.handle(Exception("Error 2"))
        
        history = handler.get_error_history(limit=10)
        assert len(history) == 2
        assert history[0]["error_message"] == "Error 1"
        assert history[1]["error_message"] == "Error 2"
    
    def test_clear_history(self):
        """Test clearing error history."""
        handler = ErrorHandler()
        handler.handle(Exception("Test error"))
        
        assert handler.get_error_count() == 1
        handler.clear_history()
        
        history = handler.get_error_history()
        assert len(history) == 0
    
    def test_recovery_strategy(self):
        """Test recovery strategy execution."""
        handler = ErrorHandler()
        error = ValueError("Test error")
        
        def recovery():
            return True
        
        handler.register_recovery_strategy(ValueError, recovery)
        handler.handle(error)
        
        # Recovery should have been attempted
        assert handler.get_error_count() == 1


class TestGlobalErrorHandler:
    """Test cases for global error handler."""
    
    def test_get_error_handler_returns_same_instance(self):
        """Test that get_error_handler returns the same instance."""
        handler1 = get_error_handler()
        handler2 = get_error_handler()
        
        assert handler1 is handler2


class TestHandleErrorsDecorator:
    """Test cases for handle_errors decorator."""
    
    def test_decorator_with_no_error(self):
        """Test decorator when no error occurs."""
        @handle_errors(default_return="fallback")
        def test_func():
            return "success"
        
        result = test_func()
        assert result == "success"
    
    def test_decorator_with_error(self):
        """Test decorator when error occurs."""
        @handle_errors(default_return="fallback")
        def test_func():
            raise ValueError("Test error")
        
        result = test_func()
        assert result == "fallback"
    
    def test_decorator_with_raise_original(self):
        """Test decorator with raise_original=True."""
        @handle_errors(raise_original=True)
        def test_func():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            test_func()
