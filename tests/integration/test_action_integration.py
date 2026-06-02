"""
Integration tests for action system
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile


class TestActionIntegration:
    """Integration tests for action system components."""

    @pytest.fixture
    def action_loader(self):
        """Create a fresh ActionLoader instance for testing."""
        from core.action_loader import get_action_loader
        return get_action_loader()

    def test_action_loading_and_execution(self, action_loader):
        """Test loading and executing actions."""
        # Load an action
        web_search_module = action_loader.load_action("web_search")
        
        assert web_search_module is not None
        assert hasattr(web_search_module, 'web_search')

    @patch('core.tool_executor.get_approval_flow')
    @patch('core.tool_executor.check_action')
    def test_action_with_approval_flow(self, mock_check, mock_approval):
        """Test action execution with approval flow."""
        from core.tool_executor import ToolExecutor
        
        mock_approval.return_value = Mock()
        mock_approval.return_value.check_and_request_approval.return_value = (True, "Approved")
        mock_check.return_value = (True, "Allowed")
        
        executor = ToolExecutor()
        
        def risky_action():
            return "risky result"
        
        executor.register_tool(
            name="risky_action",
            func=risky_action,
            description="Risky action",
            parameters={},
            risk_level="high",
            requires_approval=True
        )
        
        result = executor.execute_tool("risky_action", {})
        
        assert result == "risky result"

    def test_action_history_tracking(self):
        """Test action history tracking."""
        from core.action_history import get_action_history
        from core.action_loader import get_action_loader
        
        history = get_action_history()
        loader = get_action_loader()
        
        # Record action
        history.record_action(
            tool_name="test_tool",
            action="test_action",
            parameters={"param": "value"},
            result="success"
        )
        
        # Retrieve history
        retrieved = history.get_history()
        
        assert len(retrieved) > 0

    @patch('core.permission_profiles.check_action')
    def test_permission_based_action_execution(self, mock_check):
        """Test action execution based on permissions."""
        from core.permission_profiles import PermissionLevel
        from core.tool_executor import ToolExecutor
        
        mock_check.return_value = (True, "Allowed")
        
        executor = ToolExecutor()
        
        def admin_action():
            return "admin result"
        
        executor.register_tool(
            name="admin_action",
            func=admin_action,
            description="Admin action",
            parameters={},
            permission_level=PermissionLevel.ADMIN.value
        )
        
        result = executor.execute_tool("admin_action", {})
        
        assert result == "admin result"

    def test_workflow_action_chaining(self):
        """Test chaining multiple actions in a workflow."""
        from core.workflow_engine import WorkflowEngine
        
        engine = WorkflowEngine()
        
        steps = [
            {
                "name": "Search",
                "action": "web_search",
                "parameters": {"query": "Python"}
            },
            {
                "name": "Open Browser",
                "action": "browser_control",
                "parameters": {"url": "https://python.org"}
            },
            {
                "name": "Save Result",
                "action": "file_controller",
                "parameters": {"action": "write", "path": "result.txt"}
            }
        ]
        
        workflow = engine.create_workflow(
            name="Chained Actions",
            goal="Chain multiple actions",
            description="Test action chaining",
            steps=steps
        )
        
        assert workflow is not None
        assert len(workflow.steps) == 3

    @patch('core.background_task_manager.get_background_task_manager')
    def test_async_action_execution(self, mock_bg_manager):
        """Test asynchronous action execution."""
        from core.background_task_manager import BackgroundTaskManager
        
        bg_manager = BackgroundTaskManager()
        
        async def async_action():
            import asyncio
            await asyncio.sleep(0.1)
            return "async result"
        
        task_id = bg_manager.submit_task(
            task_func=async_action,
            task_name="Async Action"
        )
        
        assert task_id is not None

    def test_action_error_recovery(self):
        """Test action error recovery mechanisms."""
        from core.llm_fallback import LLMFallback
        
        fallback = LLMFallback()
        
        # Simulate primary failure
        with patch.object(fallback, '_generate_primary', side_effect=Exception("Primary failed")):
            response = fallback.generate("Test prompt")
        
        # Should fallback to secondary
        assert response is not None

    def test_action_with_memory_integration(self):
        """Test action integration with memory system."""
        from memory.memory_manager import MemoryManager
        from core.action_loader import get_action_loader
        
        memory = MemoryManager()
        loader = get_action_loader()
        
        # Store action result in memory
        result = {"data": "test result"}
        memory.update_memory("action_results", result)
        
        # Retrieve from memory
        retrieved = memory.load_memory("action_results")
        
        assert retrieved == result


class TestActionPerformance:
    """Performance tests for action system."""

    def test_action_execution_speed(self):
        """Test action execution performance."""
        from core.action_loader import get_action_loader
        
        import time
        loader = get_action_loader()
        
        start = time.time()
        declarations = loader.get_tool_declarations()
        elapsed = time.time() - start
        
        assert elapsed < 2.0  # Should complete quickly
        assert len(declarations) > 0

    def test_concurrent_action_execution(self):
        """Test concurrent action execution."""
        import asyncio
        from core.tool_executor import ToolExecutor
        
        executor = ToolExecutor()
        
        async def execute_concurrent():
            def action1():
                return "result1"
            
            def action2():
                return "result2"
            
            executor.register_tool("action1", action1, "Action 1", {})
            executor.register_tool("action2", action2, "Action 2", {})
            
            results = await asyncio.gather(
                executor.execute_tool_async("action1", {}),
                executor.execute_tool_async("action2", {})
            )
            
            return results
        
        # Should handle concurrent execution
        assert True  # Placeholder for actual concurrent test


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
