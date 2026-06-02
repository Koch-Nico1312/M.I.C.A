"""
Tests for core.tool_executor module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import asyncio


class TestToolExecutor:
    """Test cases for ToolExecutor class."""

    @pytest.fixture
    def tool_executor(self):
        """Create a fresh ToolExecutor instance for testing."""
        from core.tool_executor import ToolExecutor
        return ToolExecutor()

    def test_tool_executor_initialization(self, tool_executor):
        """Test ToolExecutor initialization."""
        assert tool_executor is not None
        assert hasattr(tool_executor, 'execute_tool')
        assert hasattr(tool_executor, 'get_tool')
        assert hasattr(tool_executor, 'register_tool')

    def test_register_tool(self, tool_executor):
        """Test registering a tool."""
        def test_tool(param1: str, param2: int = 10):
            return f"Result: {param1}, {param2}"
        
        tool_executor.register_tool(
            name="test_tool",
            func=test_tool,
            description="Test tool description",
            parameters={
                "type": "object",
                "properties": {
                    "param1": {"type": "string"},
                    "param2": {"type": "integer", "default": 10}
                }
            }
        )
        
        assert "test_tool" in tool_executor.tools

    def test_execute_tool(self, tool_executor):
        """Test executing a tool."""
        def test_tool(param1: str):
            return f"Result: {param1}"
        
        tool_executor.register_tool(
            name="test_tool",
            func=test_tool,
            description="Test tool",
            parameters={"type": "object", "properties": {"param1": {"type": "string"}}}
        )
        
        result = tool_executor.execute_tool("test_tool", {"param1": "test"})
        
        assert result == "Result: test"

    def test_get_tool(self, tool_executor):
        """Test getting tool information."""
        def test_tool():
            return "result"
        
        tool_executor.register_tool(
            name="test_tool",
            func=test_tool,
            description="Test tool",
            parameters={"type": "object", "properties": {}}
        )
        
        tool_info = tool_executor.get_tool("test_tool")
        
        assert tool_info is not None
        assert tool_info['name'] == "test_tool"

    def test_list_tools(self, tool_executor):
        """Test listing all available tools."""
        def tool1():
            return "result1"
        
        def tool2():
            return "result2"
        
        tool_executor.register_tool("tool1", tool1, "Tool 1", {})
        tool_executor.register_tool("tool2", tool2, "Tool 2", {})
        
        tools = tool_executor.list_tools()
        
        assert len(tools) == 2
        assert "tool1" in tools
        assert "tool2" in tools

    def test_tool_timeout(self, tool_executor):
        """Test tool execution timeout."""
        def slow_tool():
            import time
            time.sleep(5)
            return "result"
        
        tool_executor.register_tool("slow_tool", slow_tool, "Slow tool", {})
        tool_executor.default_timeout = 1
        
        with pytest.raises(TimeoutError):
            tool_executor.execute_tool("slow_tool", {})

    def test_tool_validation(self, tool_executor):
        """Test tool parameter validation."""
        def validated_tool(required_param: str, optional_param: int = 10):
            return f"{required_param}, {optional_param}"
        
        tool_executor.register_tool(
            name="validated_tool",
            func=validated_tool,
            description="Validated tool",
            parameters={
                "type": "object",
                "properties": {
                    "required_param": {"type": "string"},
                    "optional_param": {"type": "integer", "default": 10}
                },
                "required": ["required_param"]
            }
        )
        
        # Valid call
        result = tool_executor.execute_tool("validated_tool", {"required_param": "test"})
        assert result is not None
        
        # Invalid call (missing required param)
        with pytest.raises(ValueError):
            tool_executor.execute_tool("validated_tool", {})


class TestToolExecutorAsync:
    """Test async functionality in ToolExecutor."""

    @pytest.fixture
    def tool_executor(self):
        """Create a fresh ToolExecutor instance for testing."""
        from core.tool_executor import ToolExecutor
        return ToolExecutor()

    @pytest.mark.asyncio
    async def test_execute_tool_async(self, tool_executor):
        """Test async tool execution."""
        async def async_tool(param: str):
            await asyncio.sleep(0.1)
            return f"Async result: {param}"
        
        tool_executor.register_tool(
            name="async_tool",
            func=async_tool,
            description="Async tool",
            parameters={"type": "object", "properties": {"param": {"type": "string"}}}
        )
        
        result = await tool_executor.execute_tool_async("async_tool", {"param": "test"})
        
        assert result == "Async result: test"

    @pytest.mark.asyncio
    async def test_parallel_tool_execution(self, tool_executor):
        """Test parallel execution of multiple tools."""
        async def tool1():
            await asyncio.sleep(0.1)
            return "result1"
        
        async def tool2():
            await asyncio.sleep(0.1)
            return "result2"
        
        tool_executor.register_tool("tool1", tool1, "Tool 1", {})
        tool_executor.register_tool("tool2", tool2, "Tool 2", {})
        
        # Execute in parallel
        results = await asyncio.gather(
            tool_executor.execute_tool_async("tool1", {}),
            tool_executor.execute_tool_async("tool2", {})
        )
        
        assert results == ["result1", "result2"]


class TestToolExecutorErrorHandling:
    """Test error handling in ToolExecutor."""

    @pytest.fixture
    def tool_executor(self):
        """Create a fresh ToolExecutor instance for testing."""
        from core.tool_executor import ToolExecutor
        return ToolExecutor()

    def test_execute_nonexistent_tool(self, tool_executor):
        """Test executing a non-existent tool."""
        with pytest.raises(KeyError):
            tool_executor.execute_tool("nonexistent_tool", {})

    def test_tool_exception_handling(self, tool_executor):
        """Test handling of tool exceptions."""
        def failing_tool():
            raise ValueError("Tool error")
        
        tool_executor.register_tool("failing_tool", failing_tool, "Failing tool", {})
        
        with pytest.raises(ValueError):
            tool_executor.execute_tool("failing_tool", {})

    def test_invalid_parameters(self, tool_executor):
        """Test handling of invalid parameters."""
        def typed_tool(param: int):
            return param * 2
        
        tool_executor.register_tool(
            name="typed_tool",
            func=typed_tool,
            description="Typed tool",
            parameters={"type": "object", "properties": {"param": {"type": "integer"}}}
        )
        
        with pytest.raises((TypeError, ValueError)):
            tool_executor.execute_tool("typed_tool", {"param": "not_an_int"})


class TestToolExecutorIntegration:
    """Integration tests for ToolExecutor."""

    @patch('core.tool_executor.get_approval_flow')
    @patch('core.tool_executor.check_action')
    def test_tool_with_approval(self, mock_check, mock_approval):
        """Test tool execution with approval flow."""
        from core.tool_executor import ToolExecutor
        
        mock_approval.return_value = Mock()
        mock_approval.return_value.check_and_request_approval.return_value = (True, "Approved")
        mock_check.return_value = (True, "Allowed")
        
        executor = ToolExecutor()
        
        def risky_tool():
            return "risky result"
        
        executor.register_tool(
            name="risky_tool",
            func=risky_tool,
            description="Risky tool",
            parameters={},
            risk_level="high",
            requires_approval=True
        )
        
        result = executor.execute_tool("risky_tool", {})
        
        assert result == "risky result"

    def test_tool_with_action_loader(self):
        """Test tool executor integration with action loader."""
        from core.tool_executor import ToolExecutor
        from core.action_loader import get_action_loader
        
        executor = ToolExecutor()
        loader = get_action_loader()
        
        # Load tools from action loader
        tools = loader.get_tool_declarations()
        
        for tool_decl in tools:
            executor.register_tool_from_declaration(tool_decl)
        
        # Should have loaded tools
        assert len(executor.tools) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
