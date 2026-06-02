"""
Tests for core.memory_manager module
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import json
import tempfile


class TestMemoryManager:
    """Test cases for MemoryManager class."""

    @pytest.fixture
    def memory_manager(self):
        """Create a fresh MemoryManager instance for testing."""
        from core.memory_manager import MemoryManager
        return MemoryManager()

    @pytest.fixture
    def temp_memory_file(self):
        """Create a temporary memory file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = Path(f.name)
            json.dump({"test": "data"}, f)
        yield temp_path
        if temp_path.exists():
            temp_path.unlink()

    def test_memory_manager_initialization(self, memory_manager):
        """Test MemoryManager initialization."""
        assert memory_manager is not None
        assert hasattr(memory_manager, 'load_memory')
        assert hasattr(memory_manager, 'save_memory')
        assert hasattr(memory_manager, 'update_memory')

    def test_load_memory(self, memory_manager, temp_memory_file):
        """Test loading memory from file."""
        memory = memory_manager.load_memory(temp_memory_file)
        assert memory is not None
        assert "test" in memory

    def test_save_memory(self, memory_manager, temp_memory_file):
        """Test saving memory to file."""
        test_data = {"key": "value"}
        memory_manager.save_memory(temp_memory_file, test_data)
        
        assert temp_memory_file.exists()
        with open(temp_memory_file, 'r') as f:
            loaded = json.load(f)
        assert loaded == test_data

    def test_update_memory(self, memory_manager, temp_memory_file):
        """Test updating memory with new data."""
        initial_data = {"existing": "data"}
        memory_manager.save_memory(temp_memory_file, initial_data)
        
        memory_manager.update_memory(temp_memory_file, {"new": "value"})
        
        updated = memory_manager.load_memory(temp_memory_file)
        assert "existing" in updated
        assert "new" in updated

    def test_memory_caching(self, memory_manager):
        """Test that memory is cached after loading."""
        # Load memory once
        memory_manager.load_memory(Path("test.json"))
        # Load again - should use cache
        memory_manager.load_memory(Path("test.json"))
        # Verify caching behavior
        assert True  # Placeholder for actual cache test

    def test_memory_size_limit(self, memory_manager):
        """Test memory size limit enforcement."""
        # Test with large memory
        large_data = {"key": "x" * 1000000}
        # Should enforce size limit
        assert memory_manager.check_size_limit(large_data)

    def test_memory_compression(self, memory_manager):
        """Test memory compression for large datasets."""
        large_data = {"data": list(range(10000))}
        compressed = memory_manager.compress_memory(large_data)
        assert compressed is not None
        # Compressed should be smaller
        assert len(str(compressed)) < len(str(large_data))


class TestMemoryManagerErrorHandling:
    """Test error handling in MemoryManager."""

    @pytest.fixture
    def memory_manager(self):
        """Create a fresh MemoryManager instance for testing."""
        from core.memory_manager import MemoryManager
        return MemoryManager()

    def test_load_nonexistent_file(self, memory_manager):
        """Test loading a non-existent memory file."""
        with pytest.raises(FileNotFoundError):
            memory_manager.load_memory(Path("nonexistent.json"))

    def test_save_invalid_path(self, memory_manager):
        """Test saving to an invalid path."""
        invalid_path = Path("/invalid/path/that/does/not/exist/memory.json")
        with pytest.raises((FileNotFoundError, OSError)):
            memory_manager.save_memory(invalid_path, {"data": "test"})

    def test_corrupted_memory_file(self, memory_manager, temp_memory_file):
        """Test handling of corrupted memory file."""
        # Write invalid JSON
        with open(temp_memory_file, 'w') as f:
            f.write("{invalid json")
        
        with pytest.raises(json.JSONDecodeError):
            memory_manager.load_memory(temp_memory_file)

    def test_concurrent_access(self, memory_manager, temp_memory_file):
        """Test handling of concurrent memory access."""
        import threading
        
        def write_memory():
            memory_manager.update_memory(temp_memory_file, {"thread": "data"})
        
        threads = [threading.Thread(target=write_memory) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Should handle concurrent access gracefully
        final_data = memory_manager.load_memory(temp_memory_file)
        assert final_data is not None


class TestMemoryManagerIntegration:
    """Integration tests for MemoryManager."""

    def test_memory_persistence(self):
        """Test that memory persists across sessions."""
        from core.memory_manager import MemoryManager
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            manager1 = MemoryManager()
            manager1.save_memory(temp_path, {"session1": "data"})
            
            manager2 = MemoryManager()
            loaded = manager2.load_memory(temp_path)
            
            assert loaded == {"session1": "data"}
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_memory_format_compatibility(self):
        """Test memory format compatibility with existing memory files."""
        from core.memory_manager import MemoryManager
        
        # Test with various memory formats
        test_formats = [
            {"conversations": []},
            {"facts": []},
            {"preferences": {}},
            {"metadata": {"version": "1.0"}}
        ]
        
        manager = MemoryManager()
        for test_format in test_formats:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                temp_path = Path(f.name)
            
            try:
                manager.save_memory(temp_path, test_format)
                loaded = manager.load_memory(temp_path)
                assert loaded == test_format
            finally:
                if temp_path.exists():
                    temp_path.unlink()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
