"""
Integration tests for memory system
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import json


class TestMemoryIntegration:
    """Integration tests for memory system components."""

    @pytest.fixture
    def memory_manager(self):
        """Create a fresh MemoryManager instance for testing."""
        from memory.memory_manager import MemoryManager
        return MemoryManager()

    def test_memory_persistence_across_sessions(self, memory_manager):
        """Test that memory persists across different sessions."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            # Session 1: Store data
            test_data = {"user_preferences": {"theme": "dark", "language": "en"}}
            memory_manager.save_memory(temp_path, test_data)
            
            # Session 2: Load data
            loaded_data = memory_manager.load_memory(temp_path)
            
            assert loaded_data == test_data
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_hybrid_retrieval_integration(self):
        """Test hybrid retrieval combining semantic and keyword search."""
        from memory.hybrid_retrieval import get_hybrid_retrieval
        
        retrieval = get_hybrid_retrieval()
        
        # Add test memories
        retrieval.add_memory(
            content="Python is a programming language",
            metadata={"type": "fact", "importance": "high"}
        )
        retrieval.add_memory(
            content="JavaScript is used for web development",
            metadata={"type": "fact", "importance": "medium"}
        )
        
        # Search
        results = retrieval.search("programming language")
        
        assert results is not None
        assert len(results) > 0

    def test_obsidian_integration(self):
        """Test integration with Obsidian vault."""
        from memory.obsidian_vault import get_obsidian_bridge
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test Obsidian files
            (temp_path / "note1.md").write_text("# Note 1\nTest content")
            (temp_path / "note2.md").write_text("# Note 2\nMore content")
            
            obsidian = get_obsidian_bridge()
            obsidian.vault_path = temp_path
            
            # Sync notes
            obsidian.sync_vault()
            
            # Search notes
            results = obsidian.search_notes("Test")
            
            assert results is not None

    def test_memory_backup_integration(self):
        """Test memory backup and recovery."""
        from memory.memory_backup import get_backup_manager
        
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_path = Path(temp_dir) / "backups"
            backup_path.mkdir()
            
            backup_manager = get_backup_manager()
            backup_manager.backup_path = backup_path
            
            # Create backup
            test_data = {"test": "data"}
            backup_manager.create_backup(test_data)
            
            # List backups
            backups = backup_manager.list_backups()
            
            assert len(backups) > 0

    def test_conversation_compression(self):
        """Test conversation compression for memory efficiency."""
        from memory.conversation_compression import ConversationCompressor
        
        compressor = ConversationCompressor()
        
        # Add conversation
        conversation = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "How are you?"},
            {"role": "assistant", "content": "I'm doing well, thanks!"}
        ]
        
        # Compress
        compressed = compressor.compress(conversation)
        
        assert compressed is not None
        assert len(compressed) < len(conversation)

    def test_dream_memory_integration(self):
        """Test dream memory for long-term storage."""
        from memory.dream_memory import DreamMemory
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            dream = DreamMemory(storage_path=temp_path)
            
            # Store important memory
            dream.store(
                content="User prefers dark theme",
                importance=0.9,
                tags=["preference", "ui"]
            )
            
            # Retrieve
            retrieved = dream.retrieve(tags=["preference"])
            
            assert retrieved is not None

    def test_memory_with_embeddings(self):
        """Test memory with vector embeddings."""
        from memory.memory_manager import MemoryManager
        from core.semantic_search import SemanticSearch
        
        memory = MemoryManager()
        search = SemanticSearch()
        
        # Store memory with embedding
        memory_data = {
            "content": "Test content for embedding",
            "embedding": None  # Will be generated
        }
        
        # Generate embedding
        embedding = search.get_embedding("Test content for embedding")
        memory_data["embedding"] = embedding
        
        # Store
        assert embedding is not None


class TestMemoryErrorHandling:
    """Error handling tests for memory integration."""

    @pytest.fixture
    def memory_manager(self):
        """Create a fresh MemoryManager instance for testing."""
        from memory.memory_manager import MemoryManager
        return MemoryManager()

    def test_corrupted_memory_recovery(self, memory_manager):
        """Test recovery from corrupted memory file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = Path(f.name)
            f.write("{invalid json content")
        
        try:
            with pytest.raises(json.JSONDecodeError):
                memory_manager.load_memory(temp_path)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_concurrent_memory_access(self, memory_manager):
        """Test handling of concurrent memory access."""
        import threading
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            def write_memory():
                memory_manager.save_memory(temp_path, {"data": "test"})
            
            threads = [threading.Thread(target=write_memory) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            
            # Should handle concurrent access gracefully
            final_data = memory_manager.load_memory(temp_path)
            assert final_data is not None
        finally:
            if temp_path.exists():
                temp_path.unlink()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
