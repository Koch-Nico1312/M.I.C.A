"""
Tests for actions.desktop module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestDesktop:
    """Test cases for desktop action."""

    @pytest.fixture
    def desktop(self):
        """Create a fresh desktop instance for testing."""
        from actions.desktop import desktop_control
        return desktop

    @patch('actions.desktop.pyautogui')
    def test_get_screen_size(self, mock_pyautogui, desktop):
        """Test getting screen size."""
        mock_pyautogui.size.return_value = (1920, 1080)
        
        result = desktop.get_screen_size()
        
        assert result == (1920, 1080)

    @patch('actions.desktop.pyautogui')
    def test_move_mouse(self, mock_pyautogui, desktop):
        """Test moving mouse cursor."""
        mock_pyautogui.moveTo.return_value = None
        
        result = desktop.move_mouse(100, 200)
        
        assert result is not None
        mock_pyautogui.moveTo.assert_called_once()

    @patch('actions.desktop.pyautogui')
    def test_click_mouse(self, mock_pyautogui, desktop):
        """Test clicking mouse."""
        mock_pyautogui.click.return_value = None
        
        result = desktop.click()
        
        assert result is not None
        mock_pyautogui.click.assert_called_once()

    @patch('actions.desktop.pyautogui')
    def test_right_click(self, mock_pyautogui, desktop):
        """Test right-clicking."""
        mock_pyautogui.rightClick.return_value = None
        
        result = desktop.right_click()
        
        assert result is not None
        mock_pyautogui.rightClick.assert_called_once()

    @patch('actions.desktop.pyautogui')
    def test_double_click(self, mock_pyautogui, desktop):
        """Test double-clicking."""
        mock_pyautogui.doubleClick.return_value = None
        
        result = desktop.double_click()
        
        assert result is not None
        mock_pyautogui.doubleClick.assert_called_once()

    @patch('actions.desktop.pyautogui')
    def test_type_text(self, mock_pyautogui, desktop):
        """Test typing text."""
        mock_pyautogui.typewrite.return_value = None
        
        result = desktop.type("Hello World")
        
        assert result is not None
        mock_pyautogui.typewrite.assert_called_once()

    @patch('actions.desktop.pyautogui')
    def test_press_key(self, mock_pyautogui, desktop):
        """Test pressing a key."""
        mock_pyautogui.press.return_value = None
        
        result = desktop.press("enter")
        
        assert result is not None
        mock_pyautogui.press.assert_called_once()

    @patch('actions.desktop.pyautogui')
    def test_hotkey(self, mock_pyautogui, desktop):
        """Test pressing a hotkey combination."""
        mock_pyautogui.hotkey.return_value = None
        
        result = desktop.hotkey("ctrl", "c")
        
        assert result is not None
        mock_pyautogui.hotkey.assert_called_once()

    @patch('actions.desktop.pyautogui')
    def test_scroll(self, mock_pyautogui, desktop):
        """Test scrolling."""
        mock_pyautogui.scroll.return_value = None
        
        result = desktop.scroll(10)
        
        assert result is not None
        mock_pyautogui.scroll.assert_called_once()

    @patch('actions.desktop.pyautogui')
    def test_screenshot(self, mock_pyautogui, desktop):
        """Test taking a screenshot."""
        mock_image = MagicMock()
        mock_pyautogui.screenshot.return_value = mock_image
        
        result = desktop.screenshot()
        
        assert result is not None
        mock_pyautogui.screenshot.assert_called_once()


class TestDesktopErrorHandling:
    """Test error handling in desktop."""

    @pytest.fixture
    def desktop(self):
        """Create a fresh desktop instance for testing."""
        from actions.desktop import desktop_control
        return desktop

    @patch('actions.desktop.pyautogui', side_effect=Exception("PyAutoGUI error"))
    def test_pyautogui_error(self, mock_pyautogui, desktop):
        """Test error handling when PyAutoGUI fails."""
        with pytest.raises(Exception):
            desktop.move_mouse(100, 200)

    def test_invalid_coordinates(self, desktop):
        """Test handling of invalid coordinates."""
        invalid_coords = [
            (-100, 100),
            (100, -100),
            ("invalid", 100),
            (100, "invalid")
        ]
        
        for x, y in invalid_coords:
            try:
                desktop.move_mouse(x, y)
            except (ValueError, TypeError):
                pass  # Expected


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
