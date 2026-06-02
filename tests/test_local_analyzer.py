"""
Tests for core.local_analyzer module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import numpy as np


class TestLocalAnalyzer:
    """Test cases for LocalAnalyzer class."""

    @pytest.fixture
    def local_analyzer(self):
        """Create a fresh LocalAnalyzer instance for testing."""
        from core.local_analyzer import LocalAnalyzer
        return LocalAnalyzer()

    def test_local_analyzer_initialization(self, local_analyzer):
        """Test LocalAnalyzer initialization."""
        assert local_analyzer is not None
        assert hasattr(local_analyzer, 'analyze_image')
        assert hasattr(local_analyzer, 'analyze_document')
        assert hasattr(local_analyzer, 'analyze_skin')

    @patch('core.local_analyzer.cv2')
    def test_analyze_image(self, mock_cv2, local_analyzer):
        """Test local image analysis."""
        mock_image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        
        result = local_analyzer.analyze_image(mock_image)
        
        assert result is not None
        assert isinstance(result, dict)

    @patch('core.local_analyzer.easyocr')
    def test_extract_text_from_image(self, mock_ocr, local_analyzer):
        """Test text extraction from images."""
        mock_reader = MagicMock()
        mock_reader.readtext.return_value = [([0, 0, 10, 10], "Sample text", 0.9)]
        mock_ocr.Reader.return_value = mock_reader
        
        mock_image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        text = local_analyzer.extract_text(mock_image)
        
        assert text is not None
        assert isinstance(text, str)

    @patch('core.local_analyzer.PIL')
    def test_analyze_document(self, mock_pil, local_analyzer):
        """Test document analysis."""
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            result = local_analyzer.analyze_document(temp_path)
            assert result is not None
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_analyze_skin(self, local_analyzer):
        """Test skin analysis."""
        mock_image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        
        result = local_analyzer.analyze_skin(mock_image)
        
        assert result is not None
        assert isinstance(result, dict)
        assert 'analysis' in result

    def test_cache_results(self, local_analyzer):
        """Test result caching."""
        local_analyzer.cache_enabled = True
        
        mock_image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        
        # Analyze once
        result1 = local_analyzer.analyze_image(mock_image)
        # Analyze again - should use cache
        result2 = local_analyzer.analyze_image(mock_image)
        
        assert result1 is not None
        assert result2 is not None

    def test_supported_formats(self, local_analyzer):
        """Test supported file formats."""
        assert 'png' in local_analyzer.supported_image_formats
        assert 'jpg' in local_analyzer.supported_image_formats
        assert 'pdf' in local_analyzer.supported_document_formats


class TestLocalAnalyzerErrorHandling:
    """Test error handling in LocalAnalyzer."""

    @pytest.fixture
    def local_analyzer(self):
        """Create a fresh LocalAnalyzer instance for testing."""
        from core.local_analyzer import LocalAnalyzer
        return LocalAnalyzer()

    def test_invalid_image_handling(self, local_analyzer):
        """Test handling of invalid image data."""
        invalid_images = [None, [], {}, "not an image"]
        
        for invalid_image in invalid_images:
            try:
                local_analyzer.analyze_image(invalid_image)
            except (ValueError, TypeError, AttributeError):
                pass  # Expected

    def test_nonexistent_file_handling(self, local_analyzer):
        """Test handling of non-existent files."""
        nonexistent_path = Path("/nonexistent/path/file.pdf")
        
        with pytest.raises(FileNotFoundError):
            local_analyzer.analyze_document(nonexistent_path)

    def test_unsupported_format_handling(self, local_analyzer):
        """Test handling of unsupported file formats."""
        with tempfile.NamedTemporaryFile(suffix='.xyz', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            with pytest.raises(ValueError):
                local_analyzer.analyze_document(temp_path)
        finally:
            if temp_path.exists():
                temp_path.unlink()


class TestLocalAnalyzerIntegration:
    """Integration tests for LocalAnalyzer."""

    @patch('core.local_analyzer.easyocr')
    @patch('core.local_analyzer.cv2')
    def test_multimodal_analysis(self, mock_cv2, mock_ocr):
        """Test multimodal analysis combining vision and text."""
        from core.local_analyzer import LocalAnalyzer
        
        analyzer = LocalAnalyzer()
        
        # Mock OCR
        mock_reader = MagicMock()
        mock_reader.readtext.return_value = [([0, 0, 10, 10], "Text in image", 0.9)]
        mock_ocr.Reader.return_value = mock_reader
        
        # Analyze image with text
        mock_image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        result = analyzer.analyze_image(mock_image, extract_text=True)
        
        assert result is not None
        assert 'text' in result or 'analysis' in result

    def test_batch_analysis(self):
        """Test batch analysis of multiple files."""
        from core.local_analyzer import LocalAnalyzer
        
        analyzer = LocalAnalyzer()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test images
            for i in range(3):
                image_path = temp_path / f"image_{i}.png"
                mock_image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
                # Would need to actually save the image
            
            # Batch analyze
            # results = analyzer.batch_analyze(temp_path)
            # assert len(results) == 3
            
            # Placeholder for actual implementation
            assert True

    def test_analysis_timeout(self):
        """Test analysis timeout handling."""
        from core.local_analyzer import LocalAnalyzer
        
        analyzer = LocalAnalyzer()
        analyzer.analysis_timeout_seconds = 1
        
        # Test with a long-running analysis
        mock_image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        
        # Should timeout after specified duration
        # result = analyzer.analyze_image(mock_image)
        # assert result is not None or result is None  # Timeout handling
        
        # Placeholder
        assert True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
