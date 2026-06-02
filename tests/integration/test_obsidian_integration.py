"""
Integration tests for Obsidian vault system
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile


class TestObsidianIntegration:
    """Integration tests for Obsidian vault system components."""

    @pytest.fixture
    def obsidian_bridge(self):
        """Create a fresh ObsidianBridge instance for testing."""
        from memory.obsidian_vault import get_obsidian_bridge
        return get_obsidian_bridge()

    def test_obsidian_vault_connection(self, obsidian_bridge):
        """Test connecting to Obsidian vault."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)
            (vault_path / ".obsidian").mkdir()
            (vault_path / ".obsidian" / "config.json").write_text('{"vaultName": "Test Vault"}')
            
            obsidian_bridge.vault_path = vault_path
            connected = obsidian_bridge.connect()
            
            assert connected is True

    def test_create_note(self, obsidian_bridge):
        """Test creating a note in Obsidian."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)
            obsidian_bridge.vault_path = vault_path
            
            note_content = "# Test Note\nThis is a test note."
            result = obsidian_bridge.create_note("test_note.md", note_content)
            
            assert result is not None
            assert (vault_path / "test_note.md").exists()

    def test_read_note(self, obsidian_bridge):
        """Test reading a note from Obsidian."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)
            obsidian_bridge.vault_path = vault_path
            
            note_path = vault_path / "test_note.md"
            note_path.write_text("# Test Note\nContent here")
            
            content = obsidian_bridge.read_note("test_note.md")
            
            assert content == "# Test Note\nContent here"

    def test_update_note(self, obsidian_bridge):
        """Test updating a note in Obsidian."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)
            obsidian_bridge.vault_path = vault_path
            
            note_path = vault_path / "test_note.md"
            note_path.write_text("Original content")
            
            obsidian_bridge.update_note("test_note.md", "Updated content")
            
            assert note_path.read_text() == "Updated content"

    def test_delete_note(self, obsidian_bridge):
        """Test deleting a note from Obsidian."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)
            obsidian_bridge.vault_path = vault_path
            
            note_path = vault_path / "test_note.md"
            note_path.write_text("Test content")
            
            result = obsidian_bridge.delete_note("test_note.md")
            
            assert result is True
            assert not note_path.exists()

    def test_search_notes(self, obsidian_bridge):
        """Test searching notes in Obsidian vault."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)
            obsidian_bridge.vault_path = vault_path
            
            (vault_path / "note1.md").write_text("# Python\nPython programming")
            (vault_path / "note2.md").write_text("# JavaScript\nWeb development")
            (vault_path / "note3.md").write_text("# Python\nData science")
            
            results = obsidian_bridge.search_notes("Python")
            
            assert results is not None
            assert len(results) >= 2

    def test_list_notes(self, obsidian_bridge):
        """Test listing all notes in Obsidian vault."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)
            obsidian_bridge.vault_path = vault_path
            
            (vault_path / "note1.md").write_text("Content 1")
            (vault_path / "note2.md").write_text("Content 2")
            (vault_path / "note3.md").write_text("Content 3")
            
            notes = obsidian_bridge.list_notes()
            
            assert len(notes) >= 3

    def test_sync_vault(self, obsidian_bridge):
        """Test syncing Obsidian vault."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)
            obsidian_bridge.vault_path = vault_path
            
            (vault_path / "note1.md").write_text("Content 1")
            
            result = obsidian_bridge.sync_vault()
            
            assert result is not None

    def test_integration_with_memory(self, obsidian_bridge):
        """Test Obsidian integration with memory system."""
        from memory.memory_manager import MemoryManager
        
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)
            obsidian_bridge.vault_path = vault_path
            
            memory = MemoryManager()
            
            # Create note in Obsidian
            obsidian_bridge.create_note("memory_note.md", "# Memory\nImportant information")
            
            # Sync with memory
            obsidian_bridge.sync_to_memory(memory)
            
            # Should have synced
            assert True  # Placeholder for actual sync test


class TestObsidianErrorHandling:
    """Error handling tests for Obsidian system."""

    @pytest.fixture
    def obsidian_bridge(self):
        """Create a fresh ObsidianBridge instance for testing."""
        from memory.obsidian_vault import get_obsidian_bridge
        return get_obsidian_bridge()

    def test_invalid_vault_path(self, obsidian_bridge):
        """Test handling of invalid vault path."""
        obsidian_bridge.vault_path = Path("/nonexistent/path")
        
        with pytest.raises(FileNotFoundError):
            obsidian_bridge.connect()

    def test_read_nonexistent_note(self, obsidian_bridge):
        """Test reading a non-existent note."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vault_path = Path(temp_dir)
            obsidian_bridge.vault_path = vault_path
            
            with pytest.raises(FileNotFoundError):
                obsidian_bridge.read_note("nonexistent.md")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
