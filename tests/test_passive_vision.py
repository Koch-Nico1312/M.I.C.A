"""
Tests for core.passive_vision module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import numpy as np
import tempfile


class TestPassiveVision:
    """Test cases for PassiveVision class."""

    @pytest.fixture
    def passive_vision(self):
        """Create a fresh PassiveVision instance for testing."""
        from core.passive_vision import PassiveVision
        return PassiveVision()

    def test_passive_vision_initialization(self, passive_vision):
        """Test PassiveVision initialization."""
        assert passive_vision is not None
        assert hasattr(passive_vision, 'start')
        assert hasattr(passive_vision, 'stop')
        assert hasattr(passive_vision, 'capture_screen')

    @patch('core.passive_vision.mss')
    def test_capture_screen(self, mock_mss, passive_vision):
        """Test screen capture."""
        mock_screenshot = MagicMock()
        mock_screenshot.rgb = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        mock_mss.mss.return_value.__enter__.return_value = mock_screenshot
        
        image = passive_vision.capture_screen()
        
        assert image is not None
        assert isinstance(image, np.ndarray)

    def test_start_passive_vision(self, passive_vision):
        """Test starting passive vision monitoring."""
        passive_vision.start()
        
        assert passive_vision.is_running

    def test_stop_passive_vision(self, passive_vision):
        """Test stopping passive vision monitoring."""
        passive_vision.is_running = True
        
        passive_vision.stop()
        
        assert not passive_vision.is_running

    def test_vision_memory_storage(self, passive_vision):
        """Test vision memory storage."""
        test_image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        
        passive_vision.store_vision_memory(test_image, timestamp="2024-01-01T00:00:00")
        
        assert len(passive_vision.vision_memory) > 0

    def test_query_vision_memory(self, passive_vision):
        """Test querying vision memory."""
        test_image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        passive_vision.store_vision_memory(test_image)
        
        results = passive_vision.query_memory("test query")
        
        assert results is not None

    def test_memory_cleanup(self, passive_vision):
        """Test automatic memory cleanup based on retention policy."""
        # Add old memories
        for i in range(20):
            test_image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
            passive_vision.store_vision_memory(test_image)
        
        # Trigger cleanup
        passive_vision.cleanup_old_memory(max_age_minutes=10)
        
        # Should respect retention policy
        assert len(passive_vision.vision_memory) <= passive_vision.max_memory_items


class TestPassiveVisionOCR:
    """Test OCR functionality in PassiveVision."""

    @pytest.fixture
    def passive_vision(self):
        """Create a fresh PassiveVision instance for testing."""
        from core.passive_vision import PassiveVision
        return PassiveVision()

    @patch('core.passive_vision.pytesseract')
    def test_extract_text_from_image(self, mock_tesseract, passive_vision):
        """Test text extraction from images."""
        mock_tesseract.image_to_string.return_value = "Sample text from image"
        
        test_image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        text = passive_vision.extract_text(test_image)
        
        assert text == "Sample text from image"
        mock_tesseract.image_to_string.assert_called_once()

    @patch('core.passive_vision.easyocr')
    def test_extract_text_with_easyocr(self, mock_easyocr, passive_vision):
        """Test text extraction using EasyOCR."""
        mock_reader = MagicMock()
        mock_reader.readtext.return_value = [([0, 0, 10, 10], "Text", 0.9)]
        mock_easyocr.Reader.return_value = mock_reader
        
        test_image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        text = passive_vision.extract_text_easyocr(test_image)
        
        assert text is not None


class TestPassiveVisionErrorHandling:
    """Test error handling in PassiveVision."""

    @pytest.fixture
    def passive_vision(self):
        """Create a fresh PassiveVision instance for testing."""
        from core.passive_vision import PassiveVision
        return PassiveVision()

    @patch('core.passive_vision.mss', side_effect=Exception("Screen capture error"))
    def test_screen_capture_error(self, mock_mss, passive_vision):
        """Test error handling during screen capture."""
        with pytest.raises(Exception):
            passive_vision.capture_screen()

    def test_invalid_image_handling(self, passive_vision):
        """Test handling of invalid image data."""
        invalid_images = [
            None,
            [],
            {},
            "not an image"
        ]
        
        for invalid_image in invalid_images:
            with pytest.raises((ValueError, TypeError, AttributeError)):
                passive_vision.store_vision_memory(invalid_image)

    def test_ocr_error_handling(self, passive_vision):
        """Test error handling during OCR."""
        test_image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        
        # Mock OCR failure
        with patch('core.passive_vision.pytesseract', side_effect=Exception("OCR error")):
            text = passive_vision.extract_text(test_image)
            # Should handle error gracefully
            assert text is None or text == ""


class TestPassiveVisionIntegration:
    """Integration tests for PassiveVision."""

    @patch('core.passive_vision.mss')
    def test_full_vision_cycle(self, mock_mss):
        """Test a full passive vision cycle."""
        from core.passive_vision import PassiveVision
        
        mock_screenshot = MagicMock()
        mock_screenshot.rgb = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        mock_mss.mss.return_value.__enter__.return_value = mock_screenshot
        
        vision = PassiveVision()
        vision.start()
        
        # Capture screen
        image = vision.capture_screen()
        assert image is not None
        
        # Store in memory
        vision.store_vision_memory(image)
        assert len(vision.vision_memory) > 0
        
        # Query memory
        results = vision.query_memory("test")
        assert results is not None
        
        vision.stop()

    def test_vision_persistence(self):
        """Test that vision memory persists across sessions."""
        from core.passive_vision import PassiveVision
        
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "vision_memory"
            
            # Session 1
            vision1 = PassiveVision(storage_path=storage_path)
            test_image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
            vision1.store_vision_memory(test_image)
            vision1.save_to_disk()
            
            # Session 2
            vision2 = PassiveVision(storage_path=storage_path)
            vision2.load_from_disk()
            
            assert len(vision2.vision_memory) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
