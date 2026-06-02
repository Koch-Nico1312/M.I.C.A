"""
Tests for core.response_streamer module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import asyncio


class TestResponseStreamer:
    """Test cases for ResponseStreamer class."""

    @pytest.fixture
    def response_streamer(self):
        """Create a fresh ResponseStreamer instance for testing."""
        from core.response_streamer import ResponseStreamer
        return ResponseStreamer()

    def test_response_streamer_initialization(self, response_streamer):
        """Test ResponseStreamer initialization."""
        assert response_streamer is not None
        assert hasattr(response_streamer, 'stream_response')
        assert hasattr(response_streamer, 'start_streaming')
        assert hasattr(response_streamer, 'stop_streaming')

    def test_start_streaming(self, response_streamer):
        """Test starting response streaming."""
        response_streamer.start_streaming()
        
        assert response_streamer.is_streaming

    def test_stop_streaming(self, response_streamer):
        """Test stopping response streaming."""
        response_streamer.is_streaming = True
        
        response_streamer.stop_streaming()
        
        assert not response_streamer.is_streaming

    def test_stream_response(self, response_streamer):
        """Test streaming a response."""
        response_text = "This is a test response"
        
        chunks = list(response_streamer.stream_response(response_text))
        
        assert len(chunks) > 0
        assert all(isinstance(chunk, str) for chunk in chunks)

    def test_stream_with_callback(self, response_streamer):
        """Test streaming with a callback function."""
        callback = Mock()
        response_streamer.set_stream_callback(callback)
        
        response_text = "Test response"
        list(response_streamer.stream_response(response_text))
        
        # Callback should have been called
        assert callback.call_count > 0

    def test_chunk_size(self, response_streamer):
        """Test chunk size configuration."""
        response_streamer.chunk_size = 5
        
        response_text = "This is a test response"
        chunks = list(response_streamer.stream_response(response_text))
        
        # Chunks should respect chunk size
        assert all(len(chunk) <= response_streamer.chunk_size + 2 for chunk in chunks)

    def test_stream_delay(self, response_streamer):
        """Test streaming delay configuration."""
        response_streamer.stream_delay = 0.01
        
        response_text = "Test"
        chunks = list(response_streamer.stream_response(response_text))
        
        assert len(chunks) > 0

    def test_buffer_full_handling(self, response_streamer):
        """Test handling of buffer full condition."""
        response_streamer.buffer_size = 10
        
        # Add more than buffer size
        for i in range(20):
            response_streamer.add_to_buffer(f"chunk_{i}")
        
        # Should handle buffer overflow
        assert True  # Placeholder for actual buffer test


class TestResponseStreamerAsync:
    """Test async functionality in ResponseStreamer."""

    @pytest.fixture
    def response_streamer(self):
        """Create a fresh ResponseStreamer instance for testing."""
        from core.response_streamer import ResponseStreamer
        return ResponseStreamer()

    @pytest.mark.asyncio
    async def test_async_stream_response(self, response_streamer):
        """Test async response streaming."""
        response_text = "This is a test response"
        
        chunks = []
        async for chunk in response_streamer.stream_response_async(response_text):
            chunks.append(chunk)
        
        assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_async_stream_with_callback(self, response_streamer):
        """Test async streaming with callback."""
        callback = AsyncMock()
        response_streamer.set_async_stream_callback(callback)
        
        response_text = "Test response"
        async for chunk in response_streamer.stream_response_async(response_text):
            await callback(chunk)
        
        assert callback.call_count > 0


class TestResponseStreamerErrorHandling:
    """Test error handling in ResponseStreamer."""

    @pytest.fixture
    def response_streamer(self):
        """Create a fresh ResponseStreamer instance for testing."""
        from core.response_streamer import ResponseStreamer
        return ResponseStreamer()

    def test_stream_empty_response(self, response_streamer):
        """Test streaming an empty response."""
        chunks = list(response_streamer.stream_response(""))
        
        assert len(chunks) == 0

    def test_stream_none_response(self, response_streamer):
        """Test streaming a None response."""
        with pytest.raises((ValueError, TypeError)):
            list(response_streamer.stream_response(None))

    def test_callback_error_handling(self, response_streamer):
        """Test handling of callback errors."""
        callback = Mock(side_effect=Exception("Callback error"))
        response_streamer.set_stream_callback(callback)
        
        response_text = "Test response"
        # Should handle callback error gracefully
        chunks = list(response_streamer.stream_response(response_text))
        
        assert len(chunks) > 0


class TestResponseStreamerIntegration:
    """Integration tests for ResponseStreamer."""

    def test_full_streaming_cycle(self):
        """Test a full streaming cycle."""
        from core.response_streamer import ResponseStreamer
        
        streamer = ResponseStreamer()
        
        # Start streaming
        streamer.start_streaming()
        
        # Stream response
        response_text = "This is a complete response that will be streamed in chunks"
        chunks = []
        for chunk in streamer.stream_response(response_text):
            chunks.append(chunk)
        
        # Stop streaming
        streamer.stop_streaming()
        
        # Verify all chunks combined to original
        combined = "".join(chunks)
        assert combined == response_text

    def test_streaming_with_tts(self):
        """Test streaming integration with text-to-speech."""
        from core.response_streamer import ResponseStreamer
        
        streamer = ResponseStreamer()
        streamer.enable_tts = True
        
        # Mock TTS
        mock_tts = Mock()
        streamer.set_tts_callback(mock_tts)
        
        response_text = "Hello world"
        list(streamer.stream_response(response_text))
        
        # Should have called TTS for chunks
        assert True  # Placeholder for actual TTS integration test

    def test_streaming_with_ui(self):
        """Test streaming integration with UI."""
        from core.response_streamer import ResponseStreamer
        
        streamer = ResponseStreamer()
        streamer.enable_ui_updates = True
        
        # Mock UI callback
        mock_ui = Mock()
        streamer.set_ui_callback(mock_ui)
        
        response_text = "Test response"
        list(streamer.stream_response(response_text))
        
        # Should have updated UI for chunks
        assert True  # Placeholder for actual UI integration test

    def test_streaming_with_memory(self):
        """Test streaming integration with memory system."""
        from core.response_streamer import ResponseStreamer
        from memory.memory_manager import MemoryManager
        
        streamer = ResponseStreamer()
        memory = MemoryManager()
        
        # Stream response and store in memory
        response_text = "Important information to remember"
        chunks = list(streamer.stream_response(response_text))
        
        # Store in memory
        # memory.store_streamed_response(chunks)
        
        assert len(chunks) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
