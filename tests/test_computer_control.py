"""
Tests for actions.computer_control module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestComputerControl:
    """Test cases for computer_control action."""

    @pytest.fixture
    def computer_control(self):
        """Create a fresh computer_control instance for testing."""
        from actions.computer_control import computer_control
        return computer_control

    @patch('actions.computer_control.os')
    def test_shutdown(self, mock_os, computer_control):
        """Test system shutdown."""
        mock_os.system.return_value = 0
        
        result = computer_control.shutdown()
        
        assert result is not None

    @patch('actions.computer_control.os')
    def test_restart(self, mock_os, computer_control):
        """Test system restart."""
        mock_os.system.return_value = 0
        
        result = computer_control.restart()
        
        assert result is not None

    @patch('actions.computer_control.os')
    def test_sleep(self, mock_os, computer_control):
        """Test system sleep."""
        mock_os.system.return_value = 0
        
        result = computer_control.sleep()
        
        assert result is not None

    @patch('actions.computer_control.os')
    def test_lock(self, mock_os, computer_control):
        """Test system lock."""
        mock_os.system.return_value = 0
        
        result = computer_control.lock()
        
        assert result is not None

    @patch('actions.computer_control.os')
    def test_logoff(self, mock_os, computer_control):
        """Test system logoff."""
        mock_os.system.return_value = 0
        
        result = computer_control.logoff()
        
        assert result is not None

    @patch('actions.computer_control.subprocess')
    def test_run_command(self, mock_subprocess, computer_control):
        """Test running a system command."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Command output"
        mock_subprocess.run.return_value = mock_result
        
        result = computer_control.run_command("echo test")
        
        assert result is not None
        assert result["returncode"] == 0

    @patch('actions.computer_control.subprocess')
    def test_get_process_list(self, mock_subprocess, computer_control):
        """Test getting list of running processes."""
        mock_result = MagicMock()
        mock_result.stdout = "chrome.exe 1234\nexplorer.exe 5678"
        mock_result.returncode = 0
        mock_subprocess.run.return_value = mock_result
        
        result = computer_control.get_process_list()
        
        assert result is not None

    @patch('actions.computer_control.subprocess')
    def test_kill_process(self, mock_subprocess, computer_control):
        """Test killing a process."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_subprocess.run.return_value = mock_result
        
        result = computer_control.kill_process(1234)
        
        assert result is not None


class TestComputerControlErrorHandling:
    """Test error handling in computer_control."""

    @pytest.fixture
    def computer_control(self):
        """Create a fresh computer_control instance for testing."""
        from actions.computer_control import computer_control
        return computer_control

    @patch('actions.computer_control.subprocess', side_effect=Exception("Subprocess error"))
    def test_command_error(self, mock_subprocess, computer_control):
        """Test error handling when command fails."""
        with pytest.raises(Exception):
            computer_control.run_command("invalid_command")

    def test_empty_command(self, computer_control):
        """Test handling of empty command."""
        with pytest.raises(ValueError):
            computer_control.run_command("")

    def test_invalid_pid(self, computer_control):
        """Test handling of invalid process ID."""
        with pytest.raises(ValueError):
            computer_control.kill_process(-1)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
