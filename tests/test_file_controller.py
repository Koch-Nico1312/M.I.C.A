"""
Tests for actions.file_controller module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile


class TestFileController:
    """Test cases for file_controller action."""

    @pytest.fixture
    def file_controller(self):
        """Create a fresh file_controller instance for testing."""
        from actions.file_controller import file_controller
        return file_controller

    def test_list_files(self, file_controller):
        """Test listing files in a directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "test1.txt").write_text("content1")
            (temp_path / "test2.txt").write_text("content2")
            
            result = file_controller.list(str(temp_path))
            
            assert result is not None
            assert len(result) >= 2

    def test_read_file(self, file_controller):
        """Test reading a file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test file content")
            temp_path = Path(f.name)
        
        try:
            result = file_controller.read(str(temp_path))
            
            assert result == "Test file content"
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_write_file(self, file_controller):
        """Test writing to a file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            result = file_controller.write(str(temp_path), "New content")
            
            assert result is not None
            assert temp_path.read_text() == "New content"
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_delete_file(self, file_controller):
        """Test deleting a file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test content")
            temp_path = Path(f.name)
        
        try:
            result = file_controller.delete(str(temp_path))
            
            assert result is not None
            assert not temp_path.exists()
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_create_directory(self, file_controller):
        """Test creating a directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "new_directory"
            
            result = file_controller.create_directory(str(temp_path))
            
            assert result is not None
            assert temp_path.exists()
            assert temp_path.is_dir()

    def test_get_file_info(self, file_controller):
        """Test getting file information."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test content")
            temp_path = Path(f.name)
        
        try:
            result = file_controller.info(str(temp_path))
            
            assert result is not None
            assert 'size' in result
            assert 'name' in result
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_copy_file(self, file_controller):
        """Test copying a file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source = temp_path / "source.txt"
            dest = temp_path / "dest.txt"
            source.write_text("Test content")
            
            result = file_controller.copy(str(source), str(dest))
            
            assert result is not None
            assert dest.exists()
            assert dest.read_text() == "Test content"

    def test_move_file(self, file_controller):
        """Test moving a file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source = temp_path / "source.txt"
            dest = temp_path / "dest.txt"
            source.write_text("Test content")
            
            result = file_controller.move(str(source), str(dest))
            
            assert result is not None
            assert not source.exists()
            assert dest.exists()

    def test_search_files(self, file_controller):
        """Test searching for files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "test1.txt").write_text("content1")
            (temp_path / "test2.txt").write_text("content2")
            (temp_path / "other.txt").write_text("content3")
            
            result = file_controller.search(str(temp_path), pattern="test*")
            
            assert result is not None
            assert len(result) >= 2


class TestFileControllerErrorHandling:
    """Test error handling in file_controller."""

    @pytest.fixture
    def file_controller(self):
        """Create a fresh file_controller instance for testing."""
        from actions.file_controller import file_controller
        return file_controller

    def test_read_nonexistent_file(self, file_controller):
        """Test reading a non-existent file."""
        with pytest.raises(FileNotFoundError):
            file_controller.read("/nonexistent/path/file.txt")

    def test_delete_nonexistent_file(self, file_controller):
        """Test deleting a non-existent file."""
        with pytest.raises(FileNotFoundError):
            file_controller.delete("/nonexistent/path/file.txt")

    def test_write_to_nonexistent_directory(self, file_controller):
        """Test writing to a non-existent directory."""
        with pytest.raises(FileNotFoundError):
            file_controller.write("/nonexistent/path/file.txt", "content")

    def test_invalid_path(self, file_controller):
        """Test handling of invalid paths."""
        invalid_paths = [None, "", [], {}]
        
        for invalid_path in invalid_paths:
            try:
                file_controller.list(invalid_path)
            except (ValueError, TypeError, FileNotFoundError):
                pass  # Expected


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
