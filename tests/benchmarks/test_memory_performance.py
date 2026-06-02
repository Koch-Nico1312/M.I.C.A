"""
Performance benchmarks for memory system
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile


class TestMemoryManagerPerformance:
    """Performance benchmarks for MemoryManager."""

    @pytest.fixture
    def memory_manager(self):
        """Create a fresh MemoryManager instance for benchmarking."""
        from memory.memory_manager import MemoryManager
        return MemoryManager()

    def test_large_memory_write_performance(self, memory_manager, benchmark, tmp_path):
        """Benchmark writing large memory data."""
        large_data = {"data": "x" * 1000000}  # 1MB of data
        
        def write_large():
            return memory_manager.save_memory(tmp_path / "large_memory.json", large_data)
        
        result = benchmark(write_large)
        assert result is not None

    def test_large_memory_read_performance(self, memory_manager, benchmark, tmp_path):
        """Benchmark reading large memory data."""
        large_data = {"data": "x" * 1000000}
        memory_manager.save_memory(tmp_path / "large_memory.json", large_data)
        
        def read_large():
            return memory_manager.load_memory(tmp_path / "large_memory.json")
        
        result = benchmark(read_large)
        assert result is not None

    def test_batch_memory_operations_performance(self, memory_manager, benchmark):
        """Benchmark batch memory operations."""
        def batch_operations():
            for i in range(100):
                memory_manager.update_memory(f"key{i}", {"value": i})
            return True
        
        result = benchmark(batch_operations)
        assert result is True


class TestHybridRetrievalPerformance:
    """Performance benchmarks for HybridRetrieval."""

    def test_large_index_search_performance(benchmark):
        """Benchmark search on large index."""
        from memory.hybrid_retrieval import get_hybrid_retrieval
        
        retrieval = get_hybrid_retrieval()
        
        # Add large number of memories
        for i in range(1000):
            retrieval.add_memory(
                content=f"Test memory content {i} with some text",
                metadata={"type": "test", "index": i}
            )
        
        def search_large_index():
            return retrieval.search("test memory")
        
        result = benchmark(search_large_index)
        assert result is not None

    def test_concurrent_retrieval_performance(benchmark):
        """Benchmark concurrent retrieval operations."""
        from memory.hybrid_retrieval import get_hybrid_retrieval
        import asyncio
        
        retrieval = get_hybrid_retrieval()
        
        # Add memories
        for i in range(100):
            retrieval.add_memory(f"Memory {i}", {"content": f"Test {i}"})
        
        async def concurrent_search():
            tasks = [
                retrieval.search_async(f"query {i}")
                for i in range(10)
            ]
            results = await asyncio.gather(*tasks)
            return results
        
        result = benchmark(asyncio.run, concurrent_search())
        assert result is not None


class TestObsidianPerformance:
    """Performance benchmarks for Obsidian vault."""

    def test_large_vault_sync_performance(benchmark, tmp_path):
        """Benchmark syncing large Obsidian vault."""
        from memory.obsidian_vault import get_obsidian_bridge
        
        # Create large vault
        for i in range(500):
            (tmp_path / f"note{i}.md").write_text(f"# Note {i}\n" + "Content " * 100)
        
        obsidian = get_obsidian_bridge()
        obsidian.vault_path = tmp_path
        
        def sync_large_vault():
            return obsidian.sync_vault()
        
        result = benchmark(sync_large_vault)
        assert result is not None

    def test_vault_search_performance(benchmark, tmp_path):
        """Benchmark searching large vault."""
        from memory.obsidian_vault import get_obsidian_bridge
        
        # Create vault with notes
        for i in range(200):
            (tmp_path / f"note{i}.md").write_text(f"# Note {i}\nPython programming content")
        
        obsidian = get_obsidian_bridge()
        obsidian.vault_path = tmp_path
        
        def search_vault():
            return obsidian.search_notes("Python")
        
        result = benchmark(search_vault)
        assert result is not None


class TestBackupPerformance:
    """Performance benchmarks for backup operations."""

    def test_incremental_backup_performance(benchmark, tmp_path):
        """Benchmark incremental backup performance."""
        from memory.memory_backup import get_backup_manager
        
        backup_path = tmp_path / "backups"
        backup_path.mkdir()
        
        manager = get_backup_manager()
        manager.backup_path = backup_path
        manager.enable_incremental = True
        
        # Create initial backup
        initial_data = {"data": "initial"}
        manager.create_backup(initial_data)
        
        # Incremental backup
        incremental_data = {"data": "initial", "new": "data"}
        
        def incremental_backup():
            return manager.create_backup(incremental_data)
        
        result = benchmark(incremental_backup)
        assert result is not None

    def test_compressed_backup_performance(benchmark, tmp_path):
        """Benchmark compressed backup performance."""
        from memory.memory_backup import get_backup_manager
        
        backup_path = tmp_path / "backups"
        backup_path.mkdir()
        
        manager = get_backup_manager()
        manager.backup_path = backup_path
        manager.enable_compression = True
        
        large_data = {"data": "x" * 100000}
        
        def compressed_backup():
            return manager.create_backup(large_data)
        
        result = benchmark(compressed_backup)
        assert result is not None


class TestConversationCompressionPerformance:
    """Performance benchmarks for conversation compression."""

    def test_conversation_compression_performance(benchmark):
        """Benchmark conversation compression."""
        from memory.conversation_compression import ConversationCompressor
        
        compressor = ConversationCompressor()
        
        # Create long conversation
        conversation = [
            {"role": "user", "content": f"Message {i}"}
            for i in range(1000)
        ]
        
        def compress_conversation():
            return compressor.compress(conversation)
        
        result = benchmark(compress_conversation)
        assert result is not None


class TestDreamMemoryPerformance:
    """Performance benchmarks for DreamMemory."""

    def test_dream_memory_storage_performance(benchmark, tmp_path):
        """Benchmark dream memory storage."""
        from memory.dream_memory import DreamMemory
        
        dream = DreamMemory(storage_path=tmp_path)
        
        def store_dream_memories():
            for i in range(100):
                dream.store(
                    content=f"Dream memory {i}",
                    importance=0.8,
                    tags=["dream", f"tag{i}"]
                )
            return True
        
        result = benchmark(store_dream_memories)
        assert result is True

    def test_dream_memory_retrieval_performance(benchmark, tmp_path):
        """Benchmark dream memory retrieval."""
        from memory.dream_memory import DreamMemory
        
        dream = DreamMemory(storage_path=tmp_path)
        
        # Store memories
        for i in range(100):
            dream.store(f"Memory {i}", 0.8, ["tag{i}"])
        
        def retrieve_dream_memories():
            return dream.retrieve(tags=["tag50"])
        
        result = benchmark(retrieve_dream_memories)
        assert result is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--benchmark-only'])
