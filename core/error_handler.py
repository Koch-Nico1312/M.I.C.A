"""
Centralized error handling for JARVIS AI Assistant.

This module provides a unified error handling strategy with custom exception hierarchy,
error recovery mechanisms, and user-friendly error messages.

Example:
    >>> from core.error_handler import get_error_handler, handle_errors
    >>> 
    >>> # Get the global error handler
    >>> handler = get_error_handler()
    >>> 
    >>> # Handle an error
    >>> try:
    ...     raise ValueError("Test error")
    ... except Exception as e:
    ...     handler.handle(e)
    >>> 
    >>> # Use decorator for automatic error handling
    >>> @handle_errors(default_return="fallback")
    >>> def my_function():
    ...     raise ValueError("Test")
    >>> 
    >>> result = my_function()  # Returns "fallback"
"""

import logging
import traceback
from enum import Enum
from typing import Any, Callable, Optional, TypeVar

from core.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class ErrorSeverity(Enum):
    """Error severity levels for classification and handling."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class JarvisError(Exception):
    """Base exception class for all JARVIS-specific errors."""
    
    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        recoverable: bool = True,
        context: Optional[dict] = None,
    ):
        """
        Initialize a JARVIS error.
        
        Args:
            message: Error message
            severity: Error severity level
            recoverable: Whether the error is recoverable
            context: Additional context information
        """
        super().__init__(message)
        self.message = message
        self.severity = severity
        self.recoverable = recoverable
        self.context = context or {}


class ConfigurationError(JarvisError):
    """Error in configuration loading or validation."""
    
    def __init__(self, message: str, context: Optional[dict] = None):
        super().__init__(message=message, severity=ErrorSeverity.HIGH, recoverable=False, context=context)


class ActionExecutionError(JarvisError):
    """Error during action execution."""
    
    def __init__(self, action_name: str, message: str, context: Optional[dict] = None):
        context = context or {}
        context["action_name"] = action_name
        super().__init__(message=message, severity=ErrorSeverity.MEDIUM, recoverable=True, context=context)
        self.action_name = action_name


class APIError(JarvisError):
    """Error during API calls."""
    
    def __init__(self, service: str, message: str, context: Optional[dict] = None):
        context = context or {}
        context["service"] = service
        super().__init__(message=message, severity=ErrorSeverity.HIGH, recoverable=True, context=context)
        self.service = service


class ResourceError(JarvisError):
    """Error related to system resources (memory, disk, etc.)."""
    
    def __init__(self, resource: str, message: str, context: Optional[dict] = None):
        context = context or {}
        context["resource"] = resource
        super().__init__(message=message, severity=ErrorSeverity.HIGH, recoverable=False, context=context)
        self.resource = resource


class ErrorHandler:
    """
    Centralized error handler for JARVIS.
    
    Provides error logging, recovery strategies, and user-friendly error messages.
    """
    
    def __init__(self):
        self._error_handlers: dict[type, Callable[[Exception], Any]] = {}
        self._recovery_strategies: dict[type, Callable[[], bool]] = {}
        self._error_count = 0
        self._error_history: list[dict] = []
    
    def register_handler(
        self,
        exception_type: type,
        handler: Callable[[Exception], Any]
    ) -> None:
        """
        Register a custom error handler for a specific exception type.
        
        Args:
            exception_type: The exception type to handle
            handler: Handler function that takes the exception
        """
        self._error_handlers[exception_type] = handler
    
    def register_recovery_strategy(
        self,
        exception_type: type,
        strategy: Callable[[], bool]
    ) -> None:
        """
        Register a recovery strategy for a specific exception type.
        
        Args:
            exception_type: The exception type to recover from
            strategy: Recovery function that returns True if recovery succeeded
        """
        self._recovery_strategies[exception_type] = strategy
    
    def handle(
        self,
        error: Exception,
        context: Optional[dict] = None,
        raise_original: bool = False
    ) -> Optional[Any]:
        """
        Handle an error using registered handlers and recovery strategies.
        
        Args:
            error: The exception to handle
            context: Additional context information
            raise_original: Whether to raise the original error if unhandled
            
        Returns:
            Result from error handler, or None if no handler registered
            
        Raises:
            Exception: If raise_original is True and error is unhandled
        """
        self._error_count += 1
        
        # Log the error
        error_context = context or {}
        error_context["error_type"] = type(error).__name__
        error_context["error_message"] = str(error)
        
        if isinstance(error, JarvisError):
            error_context["severity"] = error.severity.value
            error_context["recoverable"] = error.recoverable
            if error.context:
                error_context.update(error.context)
            
            logger.error(
                f"JARVIS Error [{error.severity.value}]: {error.message}",
                extra={"context": error_context}
            )
        else:
            logger.error(
                f"Unhandled Exception: {type(error).__name__}: {str(error)}",
                extra={"context": error_context}
            )
        
        # Add to error history
        self._error_history.append({
            "timestamp": logger.handlers[0].formatter.formatTime(logging.LogRecord(
                "", 0, "", 0, "", (), None
            )) if logger.handlers else "unknown",
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": error_context,
        })
        
        # Keep only last 100 errors
        if len(self._error_history) > 100:
            self._error_history = self._error_history[-100:]
        
        # Try custom handler
        error_type = type(error)
        if error_type in self._error_handlers:
            try:
                return self._error_handlers[error_type](error)
            except Exception as handler_error:
                logger.error(f"Error handler failed: {handler_error}")
        
        # Try recovery strategy
        if error_type in self._recovery_strategies:
            try:
                if self._recovery_strategies[error_type]():
                    logger.info(f"Successfully recovered from {error_type.__name__}")
                    return None
            except Exception as recovery_error:
                logger.error(f"Recovery strategy failed: {recovery_error}")
        
        # Raise original if requested
        if raise_original:
            raise error
        
        return None
    
    def get_error_count(self) -> int:
        """Get the total number of errors handled."""
        return self._error_count
    
    def get_error_history(self, limit: int = 10) -> list[dict]:
        """
        Get recent error history.
        
        Args:
            limit: Maximum number of errors to return
            
        Returns:
            List of error dictionaries
        """
        return self._error_history[-limit:]
    
    def clear_history(self) -> None:
        """Clear error history."""
        self._error_history.clear()


def handle_errors(
    default_return: Optional[T] = None,
    context: Optional[dict] = None,
    raise_original: bool = False
) -> Callable:
    """
    Decorator for handling errors in functions.
    
    Args:
        default_return: Value to return on error
        context: Additional context for error handling
        raise_original: Whether to raise original error
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., Optional[T]]:
        def wrapper(*args: Any, **kwargs: Any) -> Optional[T]:
            try:
                return func(*args, **kwargs)
            except Exception as error:
                error_handler = get_error_handler()
                error_handler.handle(error, context, raise_original)
                return default_return
        return wrapper
    return decorator


# Global error handler instance
_error_handler: Optional[ErrorHandler] = None


def get_error_handler() -> ErrorHandler:
    """
    Get the global error handler instance.
    
    Returns:
        The global ErrorHandler instance
    """
    global _error_handler
    if _error_handler is None:
        _error_handler = ErrorHandler()
    return _error_handler
