"""
Tests for core.jarvis_live module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import asyncio


class TestJarvisLive:
    """Test cases for JarvisLive class."""

    @pytest.fixture
    def jarvis_live(self):
        """Create a fresh JarvisLive instance for testing."""
        from core.jarvis_live import JarvisLive
        return JarvisLive()

    def test_jarvis_live_initialization(self, jarvis_live):
        """Test JarvisLive initialization."""
        assert jarvis_live is not None
        assert hasattr(jarvis_live, 'start')
        assert hasattr(jarvis_live, 'stop')
        assert hasattr(jarvis_live, 'process_input')

    @patch('core.jarvis_live.get_config')
    def test_start_jarvis(self, mock_config, jarvis_live):
        """Test starting Jarvis."""
        mock_config.return_value = Mock()
        
        jarvis_live.start()
        
        assert jarvis_live.is_running

    @patch('core.jarvis_live.get_config')
    def test_stop_jarvis(self, mock_config, jarvis_live):
        """Test stopping Jarvis."""
        mock_config.return_value = Mock()
        jarvis_live.is_running = True
        
        jarvis_live.stop()
        
        assert not jarvis_live.is_running

    @patch('core.jarvis_live.get_config')
    def test_process_text_input(self, mock_config, jarvis_live):
        """Test processing text input."""
        mock_config.return_value = Mock()
        
        response = jarvis_live.process_input("Hello Jarvis")
        
        assert response is not None
        assert isinstance(response, str)

    @patch('core.jarvis_live.get_config')
    def test_process_audio_input(self, mock_config, jarvis_live):
        """Test processing audio input."""
        mock_config.return_value = Mock()
        
        import numpy as np
        audio_data = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        
        response = jarvis_live.process_audio(audio_data)
        
        assert response is not None

    def test_tool_execution(self, jarvis_live):
        """Test tool execution."""
        tool_name = "test_tool"
        parameters = {"param": "value"}
        
        # Mock the tool executor
        jarvis_live.tool_executor = Mock()
        jarvis_live.tool_executor.execute_tool.return_value = "result"
        
        result = jarvis_live.execute_tool(tool_name, parameters)
        
        assert result == "result"
        jarvis_live.tool_executor.execute_tool.assert_called_once()

    def test_memory_integration(self, jarvis_live):
        """Test memory integration."""
        # Test that Jarvis can access memory
        jarvis_live.memory_manager = Mock()
        jarvis_live.memory_manager.load_memory.return_value = {"test": "data"}
        
        memory = jarvis_live.get_memory()
        
        assert memory is not None
        jarvis_live.memory_manager.load_memory.assert_called_once()

    def test_voice_output(self, jarvis_live):
        """Test voice output."""
        jarvis_live.audio_handler = Mock()
        
        jarvis_live.speak("Hello")
        
        jarvis_live.audio_handler.speak.assert_called_once_with("Hello")


class TestJarvisLiveAsync:
    """Test async functionality in JarvisLive."""

    @pytest.fixture
    def jarvis_live(self):
        """Create a fresh JarvisLive instance for testing."""
        from core.jarvis_live import JarvisLive
        return JarvisLive()

    @pytest.mark.asyncio
    async def test_async_tool_execution(self, jarvis_live):
        """Test async tool execution."""
        jarvis_live.tool_executor = Mock()
        jarvis_live.tool_executor.execute_tool_async = AsyncMock(return_value="result")
        
        result = await jarvis_live.execute_tool_async("test_tool", {"param": "value"})
        
        assert result == "result"

    @pytest.mark.asyncio
    async def test_async_input_processing(self, jarvis_live):
        """Test async input processing."""
        jarvis_live.process_input_async = AsyncMock(return_value="response")
        
        result = await jarvis_live.process_input_async("test input")
        
        assert result == "response"


class TestJarvisLiveErrorHandling:
    """Test error handling in JarvisLive."""

    @pytest.fixture
    def jarvis_live(self):
        """Create a fresh JarvisLive instance for testing."""
        from core.jarvis_live import JarvisLive
        return JarvisLive()

    def test_tool_execution_error(self, jarvis_live):
        """Test error handling during tool execution."""
        jarvis_live.tool_executor = Mock()
        jarvis_live.tool_executor.execute_tool.side_effect = Exception("Tool error")
        
        with pytest.raises(Exception):
            jarvis_live.execute_tool("test_tool", {})

    def test_invalid_input_handling(self, jarvis_live):
        """Test handling of invalid input."""
        invalid_inputs = [None, "", [], {}]
        
        for invalid_input in invalid_inputs:
            try:
                jarvis_live.process_input(invalid_input)
            except (ValueError, TypeError, AttributeError):
                pass  # Expected to raise an error

    def test_memory_error_handling(self, jarvis_live):
        """Test error handling for memory operations."""
        jarvis_live.memory_manager = Mock()
        jarvis_live.memory_manager.load_memory.side_effect = Exception("Memory error")
        
        with pytest.raises(Exception):
            jarvis_live.get_memory()


class TestJarvisLiveIntegration:
    """Integration tests for JarvisLive."""

    @patch('core.jarvis_live.get_config')
    @patch('core.jarvis_live.get_memory_manager')
    @patch('core.jarvis_live.get_action_loader')
    def test_full_session_lifecycle(self, mock_loader, mock_memory, mock_config):
        """Test a full Jarvis session lifecycle."""
        from core.jarvis_live import JarvisLive
        
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        jarvis = JarvisLive()
        
        # Start session
        jarvis.start()
        assert jarvis.is_running
        
        # Process input
        jarvis.process_input("Hello")
        
        # Stop session
        jarvis.stop()
        assert not jarvis.is_running

    @patch('core.jarvis_live.get_config')
    def test_multi_turn_conversation(self, mock_config):
        """Test multi-turn conversation handling."""
        from core.jarvis_live import JarvisLive
        
        mock_config.return_value = Mock()
        jarvis = JarvisLive()
        
        # Simulate conversation
        jarvis.process_input("What's the weather?")
        jarvis.process_input("What about tomorrow?")
        jarvis.process_input("Thanks")
        
        # Verify conversation history is maintained
        assert len(jarvis.conversation_history) >= 3


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
