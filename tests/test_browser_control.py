"""
Tests for actions.browser_control module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestBrowserControl:
    """Test cases for browser_control action."""

    @pytest.fixture
    def browser_control(self):
        """Create a fresh browser_control instance for testing."""
        from actions.browser_control import browser_control
        return browser_control

    @patch('actions.browser_control.playwright')
    def test_open_browser(self, mock_playwright, browser_control):
        """Test opening a browser."""
        mock_browser = MagicMock()
        mock_page = MagicMock()
        mock_playwright.return_value.__enter__.return_value.chromium.launch.return_value.new_context.return_value.new_page.return_value = mock_page
        
        result = browser_control.open("https://example.com")
        
        assert result is not None

    @patch('actions.browser_control.playwright')
    def test_navigate_to_url(self, mock_playwright, browser_control):
        """Test navigating to a URL."""
        mock_page = MagicMock()
        mock_playwright.return_value.__enter__.return_value.chromium.launch.return_value.new_context.return_value.new_page.return_value = mock_page
        
        result = browser_control.navigate("https://example.com")
        
        assert result is not None
        mock_page.goto.assert_called_once()

    @patch('actions.browser_control.playwright')
    def test_click_element(self, mock_playwright, browser_control):
        """Test clicking an element on the page."""
        mock_page = MagicMock()
        mock_element = MagicMock()
        mock_page.query_selector.return_value = mock_element
        mock_playwright.return_value.__enter__.return_value.chromium.launch.return_value.new_context.return_value.new_page.return_value = mock_page
        
        result = browser_control.click("#submit-button")
        
        assert result is not None
        mock_element.click.assert_called_once()

    @patch('actions.browser_control.playwright')
    def test_type_text(self, mock_playwright, browser_control):
        """Test typing text into an element."""
        mock_page = MagicMock()
        mock_element = MagicMock()
        mock_page.query_selector.return_value = mock_element
        mock_playwright.return_value.__enter__.return_value.chromium.launch.return_value.new_context.return_value.new_page.return_value = mock_page
        
        result = browser_control.type("#search-input", "test query")
        
        assert result is not None
        mock_element.type.assert_called_once()

    @patch('actions.browser_control.playwright')
    def test_get_page_text(self, mock_playwright, browser_control):
        """Test getting text from the page."""
        mock_page = MagicMock()
        mock_page.evaluate.return_value = "Page content"
        mock_playwright.return_value.__enter__.return_value.chromium.launch.return_value.new_context.return_value.new_page.return_value = mock_page
        
        result = browser_control.get_text()
        
        assert result == "Page content"

    @patch('actions.browser_control.playwright')
    def test_close_browser(self, mock_playwright, browser_control):
        """Test closing the browser."""
        mock_browser = MagicMock()
        mock_playwright.return_value.__enter__.return_value.chromium.launch.return_value = mock_browser
        
        result = browser_control.close()
        
        assert result is not None
        mock_browser.close.assert_called_once()

    @patch('actions.browser_control.playwright')
    def test_take_screenshot(self, mock_playwright, browser_control):
        """Test taking a screenshot."""
        mock_page = MagicMock()
        mock_playwright.return_value.__enter__.return_value.chromium.launch.return_value.new_context.return_value.new_page.return_value = mock_page
        
        result = browser_control.screenshot("screenshot.png")
        
        assert result is not None
        mock_page.screenshot.assert_called_once()


class TestBrowserControlErrorHandling:
    """Test error handling in browser_control."""

    @pytest.fixture
    def browser_control(self):
        """Create a fresh browser_control instance for testing."""
        from actions.browser_control import browser_control
        return browser_control

    @patch('actions.browser_control.playwright', side_effect=Exception("Playwright error"))
    def test_playwright_error_handling(self, mock_playwright, browser_control):
        """Test error handling when Playwright fails."""
        with pytest.raises(Exception):
            browser_control.open("https://example.com")

    @patch('actions.browser_control.playwright')
    def test_element_not_found(self, mock_playwright, browser_control):
        """Test handling of element not found."""
        mock_page = MagicMock()
        mock_page.query_selector.return_value = None
        mock_playwright.return_value.__enter__.return_value.chromium.launch.return_value.new_context.return_value.new_page.return_value = mock_page
        
        with pytest.raises(Exception):
            browser_control.click("#nonexistent-element")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
