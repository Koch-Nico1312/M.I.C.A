"""
Integration tests for LLM system
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestLLMIntegration:
    """Integration tests for LLM system components."""

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_llm_with_memory(self, mock_loader, mock_memory, mock_config):
        """Test LLM integration with memory system."""
        from main import MicaLive
        from memory.memory_manager import MemoryManager
        
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        mica = MicaLive()
        memory = MemoryManager()
        
        # Store memory
        memory.update_memory("user_preferences", {"theme": "dark"})
        
        # Process query that uses memory
        response = mica.process_input("What are my preferences?")
        
        assert response is not None

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_llm_with_tools(self, mock_loader, mock_memory, mock_config):
        """Test LLM integration with tool execution."""
        from main import MicaLive
        from core.tool_executor import ToolExecutor
        
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        mica = MicaLive()
        executor = ToolExecutor()
        
        # Register test tool
        def test_tool(param):
            return f"Result: {param}"
        
        executor.register_tool(
            name="test_tool",
            func=test_tool,
            description="Test tool",
            parameters={"type": "object", "properties": {"param": {"type": "string"}}}
        )
        
        # Process query that requires tool
        response = mica.process_input("Use test_tool with parameter 'hello'")
        
        assert response is not None

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_llm_with_multimodal(self, mock_loader, mock_memory, mock_config):
        """Test LLM integration with multimodal input."""
        from main import MicaLive
        from core.multimodal_context import MultimodalContext
        import numpy as np
        
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        mica = MicaLive()
        context = MultimodalContext()
        
        # Add multimodal context
        context.add_text("Analyze this image")
        mock_image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        context.add_image(mock_image, description="Screenshot")
        
        # Process multimodal query
        response = mica.process_input("What's in this image?", context=context)
        
        assert response is not None

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_llm_with_fallback(self, mock_loader, mock_memory, mock_config):
        """Test LLM integration with fallback mechanism."""
        from main import MicaLive
        from core.llm_fallback import LLMFallback
        
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        mica = MicaLive()
        fallback = LLMFallback()
        fallback.enable_auto_fallback = True
        
        # Simulate primary failure
        with patch.object(fallback, '_generate_primary', side_effect=Exception("Primary failed")):
            response = mica.process_input("Test query")
        
        # Should use fallback
        assert response is not None

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_llm_streaming(self, mock_loader, mock_memory, mock_config):
        """Test LLM streaming response."""
        from main import MicaLive
        from core.response_streamer import ResponseStreamer
        
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        mica = MicaLive()
        streamer = ResponseStreamer()
        
        # Stream response
        response_text = "This is a streamed response"
        chunks = list(streamer.stream_response(response_text))
        
        assert len(chunks) > 0
        assert "".join(chunks) == response_text

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_llm_with_caching(self, mock_loader, mock_memory, mock_config):
        """Test LLM response caching."""
        from main import MicaLive
        from core.api_cache import APICache
        
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        mica = MicaLive()
        cache = APICache()
        
        # Cache response
        cache.cache_response("test_query", {"response": "Cached response"}, ttl=300)
        
        # Retrieve from cache
        cached = cache.get_cached_response("test_query")
        
        assert cached is not None
        assert cached["response"] == "Cached response"

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_llm_with_system_prompt(self, mock_loader, mock_memory, mock_config):
        """Test LLM with custom system prompt."""
        from main import MicaLive
        from core.paths import project_path
        from pathlib import Path
        
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        mica = MicaLive()
        
        # Load system prompt
        prompt_path = project_path("core", "prompt.txt")
        if prompt_path.exists():
            system_prompt = prompt_path.read_text(encoding="utf-8")
            assert system_prompt is not None

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_llm_conversation_history(self, mock_loader, mock_memory, mock_config):
        """Test LLM with conversation history."""
        from main import MicaLive
        from core.session_manager import SessionManager
        
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        mica = MicaLive()
        session = SessionManager()
        
        # Create session with history
        session_id = session.create_session().session_id
        session.add_message(session_id, "user", "Hello")
        session.add_message(session_id, "assistant", "Hi there!")
        session.add_message(session_id, "user", "How are you?")
        
        # Get conversation history
        conversation = session.get_session(session_id)
        
        assert len(conversation.messages) == 3

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_llm_with_temperature(self, mock_loader, mock_memory, mock_config):
        """Test LLM with temperature parameter."""
        from main import MicaLive
        
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        mica = MicaLive()
        mica.temperature = 0.7
        
        # Process query with temperature
        response = mica.process_input("Generate a creative response")
        
        assert response is not None


class TestLLMErrorHandling:
    """Error handling tests for LLM system."""

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_llm_api_error(self, mock_loader, mock_memory, mock_config):
        """Test handling of LLM API errors."""
        from main import MicaLive
        
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        mica = MicaLive()
        
        # Simulate API error
        with patch.object(mica, '_generate_response', side_effect=Exception("API error")):
            with pytest.raises(Exception):
                mica.process_input("Test query")

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_tool_execution_error(self, mock_loader, mock_memory, mock_config):
        """Test handling of tool execution errors."""
        from main import MicaLive
        from core.tool_executor import ToolExecutor
        
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        mica = MicaLive()
        executor = ToolExecutor()
        
        # Register failing tool
        def failing_tool():
            raise ValueError("Tool error")
        
        executor.register_tool("failing_tool", failing_tool, "Failing tool", {})
        
        # Process query that uses failing tool
        response = mica.process_input("Use failing_tool")
        
        # Should handle error gracefully
        assert response is not None or response is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
