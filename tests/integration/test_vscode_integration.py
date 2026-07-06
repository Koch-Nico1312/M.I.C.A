"""
Integration tests for VS Code bridge system
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestVSCodeIntegration:
    """Integration tests for VS Code bridge system components."""

    @pytest.fixture
    def vscode_bridge(self):
        """Create a fresh VSCodeBridge instance for testing."""
        from core.vscode_bridge import get_vscode_bridge
        return get_vscode_bridge()

    @patch('core.vscode_bridge.subprocess')
    def test_open_file_in_vscode(self, mock_subprocess, vscode_bridge):
        """Test opening a file in VS Code."""
        mock_subprocess.run.return_value = MagicMock()
        
        result = vscode_bridge.open_file("/path/to/file.py")
        
        assert result is not None
        mock_subprocess.run.assert_called_once()

    @patch('core.vscode_bridge.subprocess')
    def test_execute_command_in_vscode(self, mock_subprocess, vscode_bridge):
        """Test executing a VS Code command."""
        mock_subprocess.run.return_value = MagicMock()
        
        result = vscode_bridge.execute_command("workbench.action.files.save")
        
        assert result is not None

    @patch('core.vscode_bridge.subprocess')
    def test_get_cursor_position(self, mock_subprocess, vscode_bridge):
        """Test getting cursor position."""
        mock_result = MagicMock()
        mock_result.stdout = '{"line": 10, "character": 5}'
        mock_subprocess.run.return_value = mock_result
        
        position = vscode_bridge.get_cursor_position()
        
        assert position is not None
        assert position["line"] == 10

    @patch('core.vscode_bridge.subprocess')
    def test_set_cursor_position(self, mock_subprocess, vscode_bridge):
        """Test setting cursor position."""
        mock_subprocess.run.return_value = MagicMock()
        
        result = vscode_bridge.set_cursor_position(line=10, character=5)
        
        assert result is not None

    @patch('core.vscode_bridge.subprocess')
    def test_get_selected_text(self, mock_subprocess, vscode_bridge):
        """Test getting selected text."""
        mock_result = MagicMock()
        mock_result.stdout = "Selected text"
        mock_subprocess.run.return_value = mock_result
        
        text = vscode_bridge.get_selected_text()
        
        assert text == "Selected text"

    @patch('core.vscode_bridge.subprocess')
    def test_insert_text(self, mock_subprocess, vscode_bridge):
        """Test inserting text at cursor position."""
        mock_subprocess.run.return_value = MagicMock()
        
        result = vscode_bridge.insert_text("Hello World")
        
        assert result is not None

    @patch('core.vscode_bridge.subprocess')
    def test_get_file_content(self, mock_subprocess, vscode_bridge):
        """Test getting file content from VS Code."""
        mock_result = MagicMock()
        mock_result.stdout = "File content here"
        mock_subprocess.run.return_value = mock_result
        
        content = vscode_bridge.get_file_content("/path/to/file.py")
        
        assert content == "File content here"

    @patch('core.vscode_bridge.subprocess')
    def test_run_code(self, mock_subprocess, vscode_bridge):
        """Test running code in VS Code."""
        mock_subprocess.run.return_value = MagicMock()
        
        result = vscode_bridge.run_code()
        
        assert result is not None

    @patch('core.vscode_bridge.subprocess')
    def test_debug_code(self, mock_subprocess, vscode_bridge):
        """Test debugging code in VS Code."""
        mock_subprocess.run.return_value = MagicMock()
        
        result = vscode_bridge.debug_code()
        
        assert result is not None

    @patch('core.vscode_bridge.subprocess')
    def test_integration_with_mica(self, mock_subprocess):
        """Test VS Code integration with M.I.C.A."""
        from core.vscode_bridge import get_vscode_bridge
        from main import MicaLive
        
        vscode = get_vscode_bridge()
        mica = MicaLive()
        
        mock_subprocess.run.return_value = MagicMock()
        
        # Open file through M.I.C.A
        result = vscode.open_file("/path/to/file.py")
        
        assert result is not None


class TestVSCodeErrorHandling:
    """Error handling tests for VS Code bridge system."""

    @pytest.fixture
    def vscode_bridge(self):
        """Create a fresh VSCodeBridge instance for testing."""
        from core.vscode_bridge import get_vscode_bridge
        return get_vscode_bridge()

    @patch('core.vscode_bridge.subprocess', side_effect=Exception("VS Code not found"))
    def test_vscode_not_found(self, mock_subprocess, vscode_bridge):
        """Test handling when VS Code is not found."""
        with pytest.raises(Exception):
            vscode_bridge.open_file("/path/to/file.py")

    def test_invalid_file_path(self, vscode_bridge):
        """Test handling of invalid file path."""
        with pytest.raises(ValueError):
            vscode_bridge.open_file("")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
