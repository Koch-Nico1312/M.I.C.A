"""
Tests for actions.screen_processor module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import numpy as np


class TestScreenProcessor:
    """Test cases for screen_processor action."""

    @pytest.fixture
    def screen_processor(self):
        """Create a fresh screen_processor instance for testing."""
        from actions.screen_processor import screen_process
        return screen_processor

    @patch('actions.screen_processor.mss')
    def test_capture_screen(self, mock_mss, screen_processor):
        """Test capturing the screen."""
        mock_screenshot = MagicMock()
        mock_screenshot.rgb = np.random.randint(0, 255, (1920, 1080, 3), dtype=np.uint8)
        mock_mss.mss.return_value.__enter__.return_value = mock_screenshot
        
        result = screen_processor.capture()
        
        assert result is not None
        assert isinstance(result, np.ndarray)

    @patch('actions.screen_processor.mss')
    def test_capture_region(self, mock_mss, screen_processor):
        """Test capturing a specific screen region."""
        mock_screenshot = MagicMock()
        mock_screenshot.rgb = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        mock_mss.mss.return_value.__enter__.return_value = mock_screenshot
        
        result = screen_processor.capture_region(0, 0, 100, 100)
        
        assert result is not None

    @patch('actions.screen_processor.cv2')
    @patch('actions.screen_processor.mss')
    def test_find_element(self, mock_mss, mock_cv2, screen_processor):
        """Test finding an element on screen."""
        mock_screenshot = MagicMock()
        mock_screenshot.rgb = np.random.randint(0, 255, (1920, 1080, 3), dtype=np.uint8)
        mock_mss.mss.return_value.__enter__.return_value = mock_screenshot
        mock_cv2.matchTemplate.return_value = np.random.rand(100, 100)
        mock_cv2.minMaxLoc.return_value = (100, 200, 0, 0)
        
        template = np.random.randint(0, 255, (50, 50, 3), dtype=np.uint8)
        result = screen_processor.find_element(template)
        
        assert result is not None

    @patch('actions.screen_processor.cv2')
    @patch('actions.screen_processor.mss')
    def test_ocr_text(self, mock_mss, mock_cv2, screen_processor):
        """Test extracting text from screen using OCR."""
        mock_screenshot = MagicMock()
        mock_screenshot.rgb = np.random.randint(0, 255, (1920, 1080, 3), dtype=np.uint8)
        mock_mss.mss.return_value.__enter__.return_value = mock_screenshot
        mock_cv2.imread.return_value = mock_screenshot.rgb
        
        result = screen_processor.ocr_text()
        
        assert result is not None

    @patch('actions.screen_processor.mss')
    def test_save_screenshot(self, mock_mss, screen_processor):
        """Test saving screenshot to file."""
        mock_screenshot = MagicMock()
        mock_screenshot.rgb = np.random.randint(0, 255, (1920, 1080, 3), dtype=np.uint8)
        mock_mss.mss.return_value.__enter__.return_value = mock_screenshot
        
        result = screen_processor.save("screenshot.png")
        
        assert result is not None

    @patch('actions.screen_processor.mss')
    def test_get_screen_size(self, mock_mss, screen_processor):
        """Test getting screen size."""
        mock_screenshot = MagicMock()
        mock_screenshot.size = (1920, 1080)
        mock_mss.mss.return_value.__enter__.return_value = mock_screenshot
        
        result = screen_processor.get_size()
        
        assert result == (1920, 1080)


class TestScreenProcessorErrorHandling:
    """Test error handling in screen_processor."""

    @pytest.fixture
    def screen_processor(self):
        """Create a fresh screen_processor instance for testing."""
        from actions.screen_processor import screen_process
        return screen_processor

    @patch('actions.screen_processor.mss', side_effect=Exception("Screen capture error"))
    def test_capture_error(self, mock_mss, screen_processor):
        """Test error handling when screen capture fails."""
        with pytest.raises(Exception):
            screen_processor.capture()

    def test_invalid_region(self, screen_processor):
        """Test handling of invalid screen region."""
        invalid_regions = [
            (-100, 0, 100, 100),
            (0, -100, 100, 100),
            (0, 0, -100, 100),
            (0, 0, 100, -100)
        ]
        
        for x, y, w, h in invalid_regions:
            try:
                screen_processor.capture_region(x, y, w, h)
            except (ValueError, Exception):
                pass  # Expected


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
