"""
Tests for actions.open_app module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestOpenApp:
    """Test cases for open_app action."""

    @pytest.fixture
    def open_app(self):
        """Create a fresh open_app instance for testing."""
        from actions.open_app import open_app
        return open_app

    @patch('actions.open_app.subprocess')
    def test_open_application(self, mock_subprocess, open_app):
        """Test opening an application."""
        mock_subprocess.Popen.return_value = MagicMock()
        
        result = open_app("chrome")
        
        assert result is not None
        mock_subprocess.Popen.assert_called_once()

    @patch('actions.open_app.subprocess')
    def test_open_with_arguments(self, mock_subprocess, open_app):
        """Test opening application with arguments."""
        mock_subprocess.Popen.return_value = MagicMock()
        
        result = open_app("chrome", arguments="--new-window https://example.com")
        
        assert result is not None

    @patch('actions.open_app.subprocess')
    def test_open_by_path(self, mock_subprocess, open_app):
        """Test opening application by path."""
        mock_subprocess.Popen.return_value = MagicMock()
        
        result = open_app("C:\\Program Files\\Chrome\\chrome.exe")
        
        assert result is not None

    @patch('actions.open_app.subprocess')
    def test_open_website(self, mock_subprocess, open_app):
        """Test opening a website in default browser."""
        mock_subprocess.Popen.return_value = MagicMock()
        
        result = open_app("https://example.com")
        
        assert result is not None

    @patch('actions.open_app.os')
    def test_open_macos(self, mock_os, open_app):
        """Test opening application on macOS."""
        mock_os.name = "darwin"
        mock_os.system.return_value = 0
        
        result = open_app("Safari")
        
        assert result is not None

    @patch('actions.open_app.subprocess')
    def test_open_linux(self, mock_subprocess, open_app):
        """Test opening application on Linux."""
        mock_subprocess.Popen.return_value = MagicMock()
        
        result = open_app("firefox")
        
        assert result is not None


class TestOpenAppErrorHandling:
    """Test error handling in open_app."""

    @pytest.fixture
    def open_app(self):
        """Create a fresh open_app instance for testing."""
        from actions.open_app import open_app
        return open_app

    @patch('actions.open_app.subprocess', side_effect=Exception("Subprocess error"))
    def test_subprocess_error(self, mock_subprocess, open_app):
        """Test error handling when subprocess fails."""
        with pytest.raises(Exception):
            open_app("chrome")

    def test_empty_app_name(self, open_app):
        """Test handling of empty app name."""
        with pytest.raises(ValueError):
            open_app("")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
