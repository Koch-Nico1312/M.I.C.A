"""
Tests for actions.file_processor module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile


class TestFileProcessor:
    """Test cases for file_processor action."""

    @pytest.fixture
    def file_processor(self):
        """Create a fresh file_processor instance for testing."""
        from actions.file_processor import file_processor
        return file_processor

    def test_read_file(self, file_processor):
        """Test reading a file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test file content")
            temp_path = Path(f.name)
        
        try:
            result = file_processor.read(str(temp_path))
            
            assert result == "Test file content"
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_write_file(self, file_processor):
        """Test writing to a file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            result = file_processor.write(str(temp_path), "New content")
            
            assert result is not None
            assert temp_path.read_text() == "New content"
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_append_file(self, file_processor):
        """Test appending to a file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Initial content")
            temp_path = Path(f.name)
        
        try:
            file_processor.append(str(temp_path), " - appended")
            
            assert temp_path.read_text() == "Initial content - appended"
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_count_lines(self, file_processor):
        """Test counting lines in a file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Line 1\nLine 2\nLine 3")
            temp_path = Path(f.name)
        
        try:
            result = file_processor.count_lines(str(temp_path))
            
            assert result == 3
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_search_in_file(self, file_processor):
        """Test searching for text in a file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Hello World\nPython Programming\nHello Again")
            temp_path = Path(f.name)
        
        try:
            result = file_processor.search(str(temp_path), "Hello")
            
            assert result is not None
            assert len(result) >= 2
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_replace_in_file(self, file_processor):
        """Test replacing text in a file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Hello World")
            temp_path = Path(f.name)
        
        try:
            file_processor.replace(str(temp_path), "World", "Universe")
            
            assert temp_path.read_text() == "Hello Universe"
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_get_file_info(self, file_processor):
        """Test getting file information."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test content")
            temp_path = Path(f.name)
        
        try:
            result = file_processor.info(str(temp_path))
            
            assert result is not None
            assert 'size' in result
            assert 'name' in result
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_compress_file(self, file_processor):
        """Test compressing a file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test content" * 100)
            temp_path = Path(f.name)
        
        try:
            result = file_processor.compress(str(temp_path))
            
            assert result is not None
            assert Path(result).exists()
        finally:
            if temp_path.exists():
                temp_path.unlink()


class TestFileProcessorErrorHandling:
    """Test error handling in file_processor."""

    @pytest.fixture
    def file_processor(self):
        """Create a fresh file_processor instance for testing."""
        from actions.file_processor import file_processor
        return file_processor

    def test_read_nonexistent_file(self, file_processor):
        """Test reading a non-existent file."""
        with pytest.raises(FileNotFoundError):
            file_processor.read("/nonexistent/path/file.txt")

    def test_write_to_readonly_path(self, file_processor):
        """Test writing to a read-only path."""
        with pytest.raises((PermissionError, OSError)):
            file_processor.write("/readonly/file.txt", "content")

    def test_empty_search_term(self, file_processor):
        """Test handling of empty search term."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test content")
            temp_path = Path(f.name)
        
        try:
            with pytest.raises(ValueError):
                file_processor.search(str(temp_path), "")
        finally:
            if temp_path.exists():
                temp_path.unlink()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
