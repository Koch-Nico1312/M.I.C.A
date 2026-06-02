"""
Tests for actions.computer_settings module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestComputerSettings:
    """Test cases for computer_settings action."""

    @pytest.fixture
    def computer_settings(self):
        """Create a fresh computer_settings instance for testing."""
        from actions.computer_settings import computer_settings
        return computer_settings

    @patch('actions.computer_settings.ctypes')
    def test_set_volume(self, mock_ctypes, computer_settings):
        """Test setting system volume."""
        mock_ctypes.windll.winmm = MagicMock()
        
        result = computer_settings.set_volume(50)
        
        assert result is not None

    @patch('actions.computer_settings.ctypes')
    def test_get_volume(self, mock_ctypes, computer_settings):
        """Test getting system volume."""
        mock_ctypes.windll.winmm = MagicMock()
        mock_ctypes.windll.winmm.waveOutGetVolume.return_value = 0
        
        result = computer_settings.get_volume()
        
        assert result is not None

    @patch('actions.computer_settings.subprocess')
    def test_set_brightness(self, mock_subprocess, computer_settings):
        """Test setting screen brightness."""
        mock_subprocess.run.return_value = MagicMock()
        
        result = computer_settings.set_brightness(75)
        
        assert result is not None

    @patch('actions.computer_settings.subprocess')
    def test_get_brightness(self, mock_subprocess, computer_settings):
        """Test getting screen brightness."""
        mock_subprocess.run.return_value = MagicMock(stdout="75")
        
        result = computer_settings.get_brightness()
        
        assert result is not None

    @patch('actions.computer_settings.subprocess')
    def test_toggle_wifi(self, mock_subprocess, computer_settings):
        """Test toggling WiFi."""
        mock_subprocess.run.return_value = MagicMock()
        
        result = computer_settings.toggle_wifi(True)
        
        assert result is not None

    @patch('actions.computer_settings.subprocess')
    def test_toggle_bluetooth(self, mock_subprocess, computer_settings):
        """Test toggling Bluetooth."""
        mock_subprocess.run.return_value = MagicMock()
        
        result = computer_settings.toggle_bluetooth(True)
        
        assert result is not None

    @patch('actions.computer_settings.subprocess')
    def test_shutdown(self, mock_subprocess, computer_settings):
        """Test system shutdown."""
        mock_subprocess.run.return_value = MagicMock()
        
        result = computer_settings.shutdown()
        
        assert result is not None

    @patch('actions.computer_settings.subprocess')
    def test_restart(self, mock_subprocess, computer_settings):
        """Test system restart."""
        mock_subprocess.run.return_value = MagicMock()
        
        result = computer_settings.restart()
        
        assert result is not None

    @patch('actions.computer_settings.subprocess')
    def test_lock_screen(self, mock_subprocess, computer_settings):
        """Test locking the screen."""
        mock_subprocess.run.return_value = MagicMock()
        
        result = computer_settings.lock()
        
        assert result is not None


class TestComputerSettingsErrorHandling:
    """Test error handling in computer_settings."""

    @pytest.fixture
    def computer_settings(self):
        """Create a fresh computer_settings instance for testing."""
        from actions.computer_settings import computer_settings
        return computer_settings

    @patch('actions.computer_settings.ctypes', side_effect=Exception("CTypes error"))
    def test_volume_error(self, mock_ctypes, computer_settings):
        """Test error handling when volume control fails."""
        with pytest.raises(Exception):
            computer_settings.set_volume(50)

    @patch('actions.computer_settings.subprocess', side_effect=Exception("Subprocess error"))
    def test_brightness_error(self, mock_subprocess, computer_settings):
        """Test error handling when brightness control fails."""
        with pytest.raises(Exception):
            computer_settings.set_brightness(75)

    def test_invalid_volume(self, computer_settings):
        """Test handling of invalid volume values."""
        invalid_volumes = [-1, 101, 150, "invalid"]
        
        for invalid_volume in invalid_volumes:
            try:
                computer_settings.set_volume(invalid_volume)
            except (ValueError, TypeError):
                pass  # Expected

    def test_invalid_brightness(self, computer_settings):
        """Test handling of invalid brightness values."""
        invalid_brightness = [-1, 101, 150, "invalid"]
        
        for invalid_brightness in invalid_brightness:
            try:
                computer_settings.set_brightness(invalid_brightness)
            except (ValueError, TypeError):
                pass  # Expected


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
