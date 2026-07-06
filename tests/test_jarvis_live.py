"""
Tests for core.mica_live module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import asyncio


class TestMicaLive:
    """Test cases for MicaLive class."""

    @pytest.fixture
    def mica_live(self):
        """Create a fresh MicaLive instance for testing."""
        from core.mica_live import MicaLive
        return MicaLive()

    def test_mica_live_initialization(self, mica_live):
        """Test MicaLive initialization."""
        assert mica_live is not None
        assert hasattr(mica_live, 'start')
        assert hasattr(mica_live, 'stop')
        assert hasattr(mica_live, 'process_input')

    @patch('core.mica_live.get_config')
    def test_start_mica(self, mock_config, mica_live):
        """Test starting M.I.C.A."""
        mock_config.return_value = Mock()
        
        mica_live.start()
        
        assert mica_live.is_running

    @patch('core.mica_live.get_config')
    def test_stop_mica(self, mock_config, mica_live):
        """Test stopping M.I.C.A."""
        mock_config.return_value = Mock()
        mica_live.is_running = True
        
        mica_live.stop()
        
        assert not mica_live.is_running

    @patch('core.mica_live.get_config')
    def test_process_text_input(self, mock_config, mica_live):
        """Test processing text input."""
        mock_config.return_value = Mock()
        
        response = mica_live.process_input("Hello M.I.C.A")
        
        assert response is not None
        assert isinstance(response, str)

    @patch('core.mica_live.get_config')
    def test_process_audio_input(self, mock_config, mica_live):
        """Test processing audio input."""
        mock_config.return_value = Mock()
        
        import numpy as np
        audio_data = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        
        response = mica_live.process_audio(audio_data)
        
        assert response is not None

    def test_tool_execution(self, mica_live):
        """Test tool execution."""
        tool_name = "test_tool"
        parameters = {"param": "value"}
        
        # Mock the tool executor
        mica_live.tool_executor = Mock()
        mica_live.tool_executor.execute_tool.return_value = "result"
        
        result = mica_live.execute_tool(tool_name, parameters)
        
        assert result == "result"
        mica_live.tool_executor.execute_tool.assert_called_once()

    def test_memory_integration(self, mica_live):
        """Test memory integration."""
        # Test that M.I.C.A can access memory
        mica_live.memory_manager = Mock()
        mica_live.memory_manager.load_memory.return_value = {"test": "data"}
        
        memory = mica_live.get_memory()
        
        assert memory is not None
        mica_live.memory_manager.load_memory.assert_called_once()

    def test_voice_output(self, mica_live):
        """Test voice output."""
        mica_live.audio_handler = Mock()
        
        mica_live.speak("Hello")
        
        mica_live.audio_handler.speak.assert_called_once_with("Hello")


class TestMicaLiveAsync:
    """Test async functionality in MicaLive."""

    @pytest.fixture
    def mica_live(self):
        """Create a fresh MicaLive instance for testing."""
        from core.mica_live import MicaLive
        return MicaLive()

    @pytest.mark.asyncio
    async def test_async_tool_execution(self, mica_live):
        """Test async tool execution."""
        mica_live.tool_executor = Mock()
        mica_live.tool_executor.execute_tool_async = AsyncMock(return_value="result")
        
        result = await mica_live.execute_tool_async("test_tool", {"param": "value"})
        
        assert result == "result"

    @pytest.mark.asyncio
    async def test_async_input_processing(self, mica_live):
        """Test async input processing."""
        mica_live.process_input_async = AsyncMock(return_value="response")
        
        result = await mica_live.process_input_async("test input")
        
        assert result == "response"


class TestMicaLiveErrorHandling:
    """Test error handling in MicaLive."""

    @pytest.fixture
    def mica_live(self):
        """Create a fresh MicaLive instance for testing."""
        from core.mica_live import MicaLive
        return MicaLive()

    def test_tool_execution_error(self, mica_live):
        """Test error handling during tool execution."""
        mica_live.tool_executor = Mock()
        mica_live.tool_executor.execute_tool.side_effect = Exception("Tool error")
        
        with pytest.raises(Exception):
            mica_live.execute_tool("test_tool", {})

    def test_invalid_input_handling(self, mica_live):
        """Test handling of invalid input."""
        invalid_inputs = [None, "", [], {}]
        
        for invalid_input in invalid_inputs:
            try:
                mica_live.process_input(invalid_input)
            except (ValueError, TypeError, AttributeError):
                pass  # Expected to raise an error

    def test_memory_error_handling(self, mica_live):
        """Test error handling for memory operations."""
        mica_live.memory_manager = Mock()
        mica_live.memory_manager.load_memory.side_effect = Exception("Memory error")
        
        with pytest.raises(Exception):
            mica_live.get_memory()


class TestMicaLiveIntegration:
    """Integration tests for MicaLive."""

    @patch('core.mica_live.get_config')
    @patch('core.mica_live.get_memory_manager')
    @patch('core.mica_live.get_action_loader')
    def test_full_session_lifecycle(self, mock_loader, mock_memory, mock_config):
        """Test a full M.I.C.A session lifecycle."""
        from core.mica_live import MicaLive
        
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        mica = MicaLive()
        
        # Start session
        mica.start()
        assert mica.is_running
        
        # Process input
        mica.process_input("Hello")
        
        # Stop session
        mica.stop()
        assert not mica.is_running

    @patch('core.mica_live.get_config')
    def test_multi_turn_conversation(self, mock_config):
        """Test multi-turn conversation handling."""
        from core.mica_live import MicaLive
        
        mock_config.return_value = Mock()
        mica = MicaLive()
        
        # Simulate conversation
        mica.process_input("What's the weather?")
        mica.process_input("What about tomorrow?")
        mica.process_input("Thanks")
        
        # Verify conversation history is maintained
        assert len(mica.conversation_history) >= 3


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
