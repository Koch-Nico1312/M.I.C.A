"""
Mocking utilities for JARVIS AI Assistant tests.

This module provides common mocking utilities for testing external dependencies,
file system operations, database operations, and network requests.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest


class MockConfig:
    """Mock configuration for testing."""
    
    def __init__(self):
        self._config: Dict[str, Any] = {
            "models": {
                "live": "models/gemini-2.5-flash-native-audio-preview-12-2025",
                "text": "gemini-2.5-flash",
                "vision": "gemini-2.5-flash",
            },
            "audio": {
                "channels": 1,
                "send_sample_rate": 16000,
                "receive_sample_rate": 24000,
            },
            "security": {
                "permission_profile": "safe",
                "confirmation_medium_risk": True,
                "confirmation_high_risk": True,
                "action_history_enabled": False,
            },
            "performance": {
                "enabled": False,
            },
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
        return value if value is not self._config else default
    
    def get_api_key(self, service: str) -> Optional[str]:
        """Get API key for a service."""
        return f"mock_{service}_api_key"


class MockFileSystem:
    """Mock file system for testing."""
    
    def __init__(self, temp_dir: Path):
        self.temp_dir = temp_dir
        self.files: Dict[str, str] = {}
    
    def create_file(self, path: str, content: str = "") -> Path:
        """Create a mock file."""
        file_path = self.temp_dir / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        self.files[path] = content
        return file_path
    
    def read_file(self, path: str) -> str:
        """Read a mock file."""
        return self.files.get(path, "")
    
    def delete_file(self, path: str) -> None:
        """Delete a mock file."""
        if path in self.files:
            del self.files[path]
    
    def exists(self, path: str) -> bool:
        """Check if a mock file exists."""
        return path in self.files


class MockDatabase:
    """Mock database for testing."""
    
    def __init__(self):
        self._data: Dict[str, Dict[str, Any]] = {}
        self._connections: int = 0
    
    def connect(self) -> None:
        """Mock database connection."""
        self._connections += 1
    
    def disconnect(self) -> None:
        """Mock database disconnection."""
        self._connections = max(0, self._connections - 1)
    
    def get(self, table: str, key: str) -> Optional[Dict[str, Any]]:
        """Get a value from the mock database."""
        return self._data.get(f"{table}:{key}")
    
    def set(self, table: str, key: str, value: Dict[str, Any]) -> None:
        """Set a value in the mock database."""
        self._data[f"{table}:{key}"] = value
    
    def delete(self, table: str, key: str) -> None:
        """Delete a value from the mock database."""
        if f"{table}:{key}" in self._data:
            del self._data[f"{table}:{key}"]
    
    def clear(self) -> None:
        """Clear all data from the mock database."""
        self._data.clear()


class MockAPIClient:
    """Mock API client for testing."""
    
    def __init__(self):
        self._responses: Dict[str, Any] = {}
        self._requests: list = []
    
    def set_response(self, endpoint: str, response: Any) -> None:
        """Set a mock response for an endpoint."""
        self._responses[endpoint] = response
    
    def request(self, method: str, endpoint: str, **kwargs) -> Any:
        """Mock API request."""
        self._requests.append({"method": method, "endpoint": endpoint, "kwargs": kwargs})
        return self._responses.get(endpoint, {"status": "ok"})
    
    def get_requests(self) -> list:
        """Get all made requests."""
        return self._requests
    
    def clear_requests(self) -> None:
        """Clear request history."""
        self._requests.clear()


@pytest.fixture
def mock_config():
    """Fixture providing a mock configuration."""
    return MockConfig()


@pytest.fixture
def mock_file_system(tmp_path):
    """Fixture providing a mock file system."""
    return MockFileSystem(tmp_path)


@pytest.fixture
def mock_database():
    """Fixture providing a mock database."""
    return MockDatabase()


@pytest.fixture
def mock_api_client():
    """Fixture providing a mock API client."""
    return MockAPIClient()


@pytest.fixture
def mock_logger():
    """Fixture providing a mock logger."""
    logger = MagicMock()
    logger.info = MagicMock()
    logger.warning = MagicMock()
    logger.error = MagicMock()
    logger.debug = MagicMock()
    return logger


def mock_action_response(action_name: str, result: str = "Success"):
    """
    Create a mock action response.
    
    Args:
        action_name: Name of the action
        result: Result message
        
    Returns:
        Mock action response
    """
    mock = MagicMock()
    mock.return_value = result
    return mock


def patch_external_api(module_path: str):
    """
    Patch an external API module.
    
    Args:
        module_path: Path to the module to patch
        
    Returns:
        Patch context manager
    """
    return patch(module_path)


def patch_file_operations():
    """
    Patch file system operations for testing.
    
    Returns:
        Tuple of patch context managers
    """
    return (
        patch("pathlib.Path.exists"),
        patch("pathlib.Path.read_text"),
        patch("pathlib.Path.write_text"),
    )


def patch_database_operations():
    """
    Patch database operations for testing.
    
    Returns:
        Patch context manager for database
    """
    return patch("core.memory_manager.sqlite3")


class MockAction:
    """Mock action for testing."""
    
    def __init__(self, name: str, result: str = "Success"):
        self.name = name
        self.result = result
        self.called = False
        self.call_count = 0
        self.last_parameters = None
    
    def __call__(self, **kwargs):
        self.called = True
        self.call_count += 1
        self.last_parameters = kwargs
        return self.result
    
    def reset(self):
        """Reset the mock action state."""
        self.called = False
        self.call_count = 0
        self.last_parameters = None


@pytest.fixture
def mock_action_factory():
    """Fixture providing a factory for creating mock actions."""
    def factory(name: str, result: str = "Success") -> MockAction:
        return MockAction(name, result)
    return factory
