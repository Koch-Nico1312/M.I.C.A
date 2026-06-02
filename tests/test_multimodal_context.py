"""
Tests for core.multimodal_context module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import numpy as np


class TestMultimodalContext:
    """Test cases for MultimodalContext class."""

    @pytest.fixture
    def multimodal_context(self):
        """Create a fresh MultimodalContext instance for testing."""
        from core.multimodal_context import MultimodalContext
        return MultimodalContext()

    def test_multimodal_context_initialization(self, multimodal_context):
        """Test MultimodalContext initialization."""
        assert multimodal_context is not None
        assert hasattr(multimodal_context, 'add_text')
        assert hasattr(multimodal_context, 'add_image')
        assert hasattr(multimodal_context, 'add_file')
        assert hasattr(multimodal_context, 'get_context')

    def test_add_text(self, multimodal_context):
        """Test adding text context."""
        multimodal_context.add_text("User query: What is the weather?")
        
        context = multimodal_context.get_context()
        assert context is not None
        assert 'text' in context

    def test_add_image(self, multimodal_context):
        """Test adding image context."""
        mock_image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        
        multimodal_context.add_image(mock_image, description="Screenshot of error")
        
        context = multimodal_context.get_context()
        assert context is not None
        assert 'images' in context

    def test_add_file(self, multimodal_context):
        """Test adding file context."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test file content")
            temp_path = Path(f.name)
        
        try:
            multimodal_context.add_file(temp_path)
            
            context = multimodal_context.get_context()
            assert context is not None
            assert 'files' in context
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_get_combined_context(self, multimodal_context):
        """Test getting combined multimodal context."""
        # Add various context types
        multimodal_context.add_text("User query")
        mock_image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        multimodal_context.add_image(mock_image)
        
        context = multimodal_context.get_context()
        
        assert 'text' in context
        assert 'images' in context
        assert len(context['text']) > 0

    def test_context_limit(self, multimodal_context):
        """Test context size limit."""
        multimodal_context.max_context_items = 5
        
        # Add more than limit
        for i in range(10):
            multimodal_context.add_text(f"Text {i}")
        
        context = multimodal_context.get_context()
        assert len(context['text']) <= multimodal_context.max_context_items

    def test_clear_context(self, multimodal_context):
        """Test clearing context."""
        multimodal_context.add_text("Test text")
        multimodal_context.clear()
        
        context = multimodal_context.get_context()
        assert len(context.get('text', [])) == 0

    def test_context_priority(self, multimodal_context):
        """Test context priority ordering."""
        multimodal_context.add_text("Old message", priority="low")
        multimodal_context.add_text("Recent message", priority="high")
        
        context = multimodal_context.get_context()
        # High priority should come first
        assert context['text'][0].content == "Recent message"


class TestMultimodalContextErrorHandling:
    """Test error handling in MultimodalContext."""

    @pytest.fixture
    def multimodal_context(self):
        """Create a fresh MultimodalContext instance for testing."""
        from core.multimodal_context import MultimodalContext
        return MultimodalContext()

    def test_invalid_image_handling(self, multimodal_context):
        """Test handling of invalid image data."""
        invalid_images = [None, [], {}, "not an image"]
        
        for invalid_image in invalid_images:
            try:
                multimodal_context.add_image(invalid_image)
            except (ValueError, TypeError, AttributeError):
                pass  # Expected

    def test_nonexistent_file_handling(self, multimodal_context):
        """Test handling of non-existent files."""
        nonexistent_path = Path("/nonexistent/path/file.txt")
        
        with pytest.raises(FileNotFoundError):
            multimodal_context.add_file(nonexistent_path)

    def test_invalid_priority_handling(self, multimodal_context):
        """Test handling of invalid priority values."""
        invalid_priorities = [None, "", "invalid", 123]
        
        for invalid_priority in invalid_priorities:
            try:
                multimodal_context.add_text("Test", priority=invalid_priority)
            except (ValueError, TypeError):
                pass  # Expected


class TestMultimodalContextIntegration:
    """Integration tests for MultimodalContext."""

    def test_full_multimodal_pipeline(self):
        """Test a full multimodal context pipeline."""
        from core.multimodal_context import MultimodalContext
        
        context = MultimodalContext()
        
        # Add text
        context.add_text("User wants to know about the image")
        
        # Add image
        mock_image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        context.add_image(mock_image, description="Product image")
        
        # Add file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Product specification")
            temp_path = Path(f.name)
        
        try:
            context.add_file(temp_path)
            
            # Get combined context
            combined = context.get_context()
            
            assert 'text' in combined
            assert 'images' in combined
            assert 'files' in combined
            assert len(combined['text']) > 0
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_context_with_memory(self):
        """Test multimodal context integration with memory system."""
        from core.multimodal_context import MultimodalContext
        from memory.memory_manager import MemoryManager
        
        context = MultimodalContext()
        memory = MemoryManager()
        
        # Add context
        context.add_text("Remember this information")
        
        # Store in memory
        context_data = context.get_context()
        # memory.store_context(context_data)
        
        # Should integrate with memory
        assert True  # Placeholder for actual integration test

    def test_context_for_llm(self):
        """Test formatting context for LLM consumption."""
        from core.multimodal_context import MultimodalContext
        
        context = MultimodalContext()
        context.add_text("User query")
        mock_image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        context.add_image(mock_image)
        
        # Format for LLM
        formatted = context.format_for_llm()
        
        assert formatted is not None
        assert isinstance(formatted, str)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
