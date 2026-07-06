"""
Integration tests for MCP (Model Context Protocol) system
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestMCPIntegration:
    """Integration tests for MCP system components."""

    @pytest.fixture
    def mcp_client(self):
        """Create a fresh MCPClient instance for testing."""
        from core.mcp_client import get_mcp_client
        return get_mcp_client()

    @patch('core.mcp_client.subprocess')
    def test_mcp_server_connection(self, mock_subprocess, mcp_client):
        """Test connecting to MCP server."""
        mock_process = MagicMock()
        mock_process.stdout = MagicMock()
        mock_process.stderr = MagicMock()
        mock_subprocess.Popen.return_value = mock_process
        
        result = mcp_client.connect_server("test_server", "python server.py")
        
        assert result is not None

    @patch('core.mcp_client.subprocess')
    def test_mcp_tool_registration(self, mock_subprocess, mcp_client):
        """Test registering MCP tools."""
        mock_process = MagicMock()
        mock_process.stdout = MagicMock()
        mock_subprocess.Popen.return_value = mock_process
        
        mcp_client.connect_server("test_server", "python server.py")
        
        # Register tools from server
        tools = mcp_client.get_server_tools("test_server")
        
        assert tools is not None

    @patch('core.mcp_client.subprocess')
    def test_mcp_tool_execution(self, mock_subprocess, mcp_client):
        """Test executing MCP tools."""
        mock_process = MagicMock()
        mock_process.stdout = MagicMock()
        mock_subprocess.Popen.return_value = mock_process
        
        mcp_client.connect_server("test_server", "python server.py")
        
        result = mcp_client.execute_tool("test_server", "test_tool", {"param": "value"})
        
        assert result is not None

    @patch('core.mcp_client.subprocess')
    def test_mcp_server_disconnection(self, mock_subprocess, mcp_client):
        """Test disconnecting from MCP server."""
        mock_process = MagicMock()
        mock_process.stdout = MagicMock()
        mock_subprocess.Popen.return_value = mock_process
        
        mcp_client.connect_server("test_server", "python server.py")
        
        result = mcp_client.disconnect_server("test_server")
        
        assert result is not None

    @patch('core.mcp_client.subprocess')
    def test_mcp_multiple_servers(self, mock_subprocess, mcp_client):
        """Test managing multiple MCP servers."""
        mock_process = MagicMock()
        mock_process.stdout = MagicMock()
        mock_subprocess.Popen.return_value = mock_process
        
        # Connect to multiple servers
        mcp_client.connect_server("server1", "python server1.py")
        mcp_client.connect_server("server2", "python server2.py")
        mcp_client.connect_server("server3", "python server3.py")
        
        # List servers
        servers = mcp_client.list_servers()
        
        assert len(servers) >= 3

    @patch('core.mcp_client.subprocess')
    def test_mcp_error_handling(self, mock_subprocess, mcp_client):
        """Test MCP error handling."""
        mock_subprocess.Popen.side_effect = Exception("Server error")
        
        with pytest.raises(Exception):
            mcp_client.connect_server("test_server", "python server.py")

    @patch('core.mcp_client.subprocess')
    def test_mcp_with_mica(self, mock_subprocess):
        """Test MCP integration with M.I.C.A core."""
        from core.mcp_client import get_mcp_client
        from core.tool_executor import ToolExecutor
        
        mcp_client = get_mcp_client()
        executor = ToolExecutor()
        
        mock_process = MagicMock()
        mock_process.stdout = MagicMock()
        mock_subprocess.Popen.return_value = mock_process
        
        # Connect MCP server
        mcp_client.connect_server("test_server", "python server.py")
        
        # Register MCP tools with executor
        mcp_tools = mcp_client.get_server_tools("test_server")
        
        for tool in mcp_tools:
            executor.register_tool_from_declaration(tool)
        
        # Should have registered tools
        assert len(executor.tools) > 0


class TestMCPPerformance:
    """Performance tests for MCP system."""

    @patch('core.mcp_client.subprocess')
    def test_mcp_tool_execution_speed(self, mock_subprocess):
        """Test MCP tool execution performance."""
        from core.mcp_client import get_mcp_client
        
        import time
        mcp_client = get_mcp_client()
        
        mock_process = MagicMock()
        mock_process.stdout = MagicMock()
        mock_subprocess.Popen.return_value = mock_process
        
        mcp_client.connect_server("test_server", "python server.py")
        
        start = time.time()
        mcp_client.execute_tool("test_server", "test_tool", {})
        elapsed = time.time() - start
        
        assert elapsed < 2.0  # Should execute quickly


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
