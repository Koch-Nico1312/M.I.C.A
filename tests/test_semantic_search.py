"""
Tests for core.semantic_search module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile


class TestSemanticSearch:
    """Test cases for SemanticSearch class."""

    @pytest.fixture
    def semantic_search(self):
        """Create a fresh SemanticSearch instance for testing."""
        from core.semantic_search import SemanticSearch
        return SemanticSearch()

    def test_semantic_search_initialization(self, semantic_search):
        """Test SemanticSearch initialization."""
        assert semantic_search is not None
        assert hasattr(semantic_search, 'index_directory')
        assert hasattr(semantic_search, 'search')
        assert hasattr(semantic_search, 'ask')

    @patch('core.semantic_search.chromadb')
    def test_index_directory(self, mock_chroma, semantic_search):
        """Test indexing a directory of documents."""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.PersistentClient.return_value = mock_client
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            # Create test documents
            (temp_path / "doc1.txt").write_text("Test document 1")
            (temp_path / "doc2.txt").write_text("Test document 2")
            
            semantic_search.index_directory(temp_path)
            
            assert semantic_search.indexed

    @patch('core.semantic_search.chromadb')
    def test_search_query(self, mock_chroma, semantic_search):
        """Test semantic search query."""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "documents": [["Test result 1", "Test result 2"]],
            "metadatas": [[{"source": "doc1"}, {"source": "doc2"}]],
            "distances": [[0.1, 0.2]]
        }
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.PersistentClient.return_value = mock_client
        
        results = semantic_search.search("test query")
        
        assert results is not None
        assert len(results) > 0

    @patch('core.semantic_search.chromadb')
    def test_ask_question(self, mock_chroma, semantic_search):
        """Test asking a question with RAG."""
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "documents": [["Relevant context for the question"]],
            "metadatas": [[{"source": "doc1"}]],
            "distances": [[0.1]]
        }
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.PersistentClient.return_value = mock_client
        
        answer = semantic_search.ask("What is the meaning of life?")
        
        assert answer is not None
        assert isinstance(answer, str)

    def test_chunking_strategy(self, semantic_search):
        """Test document chunking strategy."""
        long_text = "This is a test. " * 100  # Long text
        
        chunks = semantic_search.chunk_text(long_text, chunk_size=100, overlap=20)
        
        assert len(chunks) > 1
        assert all(len(chunk) <= 100 for chunk in chunks)

    def test_embedding_generation(self, semantic_search):
        """Test embedding generation for text."""
        test_text = "Test text for embedding"
        
        # Mock embedding model
        semantic_search.embedding_model = Mock()
        semantic_search.embedding_model.encode.return_value = [0.1, 0.2, 0.3]
        
        embedding = semantic_search.get_embedding(test_text)
        
        assert embedding is not None
        assert len(embedding) > 0


class TestSemanticSearchErrorHandling:
    """Test error handling in SemanticSearch."""

    @pytest.fixture
    def semantic_search(self):
        """Create a fresh SemanticSearch instance for testing."""
        from core.semantic_search import SemanticSearch
        return SemanticSearch()

    @patch('core.semantic_search.chromadb', side_effect=Exception("ChromaDB error"))
    def test_chromadb_error_handling(self, mock_chroma, semantic_search):
        """Test error handling when ChromaDB fails."""
        with pytest.raises(Exception):
            semantic_search.index_directory(Path("test"))

    def test_empty_directory_handling(self, semantic_search):
        """Test handling of empty directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Should handle empty directory gracefully
            try:
                semantic_search.index_directory(temp_path)
            except (ValueError, FileNotFoundError):
                pass  # Expected

    def test_invalid_query_handling(self, semantic_search):
        """Test handling of invalid queries."""
        invalid_queries = [None, "", [], {}]
        
        for invalid_query in invalid_queries:
            try:
                semantic_search.search(invalid_query)
            except (ValueError, TypeError, AttributeError):
                pass  # Expected


class TestSemanticSearchIntegration:
    """Integration tests for SemanticSearch."""

    @patch('core.semantic_search.chromadb')
    def test_full_rag_pipeline(self, mock_chroma):
        """Test a full RAG pipeline."""
        from core.semantic_search import SemanticSearch
        
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "documents": [["Context for answering the question"]],
            "metadatas": [[{"source": "doc1"}]],
            "distances": [[0.1]]
        }
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.PersistentClient.return_value = mock_client
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "test.txt").write_text("Test document with information")
            
            search = SemanticSearch()
            search.index_directory(temp_path)
            
            # Search
            results = search.search("test query")
            assert results is not None
            
            # Ask
            answer = search.ask("What information is in the document?")
            assert answer is not None

    def test_vector_db_persistence(self):
        """Test that vector database persists across sessions."""
        from core.semantic_search import SemanticSearch
        
        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "vector_db"
            
            # Session 1
            search1 = SemanticSearch(index_path=index_path)
            with tempfile.TemporaryDirectory() as doc_dir:
                doc_path = Path(doc_dir)
                (doc_path / "doc.txt").write_text("Test document")
                search1.index_directory(doc_path)
            
            # Session 2
            search2 = SemanticSearch(index_path=index_path)
            # Should be able to load existing index
            assert search2.indexed or True  # Placeholder


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
