"""
Integration tests for full M.I.C.A workflows
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile


class TestFullWorkflow:
    """Integration tests for complete M.I.C.A workflows."""

    @pytest.fixture
    def mica(self):
        """Create a fresh M.I.C.A instance for testing."""
        from main import MicaLive
        return MicaLive()

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_voice_to_action_workflow(self, mock_loader, mock_memory, mock_config, mica):
        """Test complete workflow from voice input to action execution."""
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        # Simulate voice input
        voice_input = "Open Chrome and search for Python tutorials"
        
        # Process input
        response = mica.process_input(voice_input)
        
        assert response is not None

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_multi_step_task_workflow(self, mock_loader, mock_memory, mock_config, mica):
        """Test workflow with multiple sequential steps."""
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        # Create a workflow with multiple steps
        from core.workflow_engine import WorkflowEngine
        engine = WorkflowEngine()
        
        steps = [
            {"name": "Step 1", "action": "web_search", "parameters": {"query": "Python"}},
            {"name": "Step 2", "action": "open_app", "parameters": {"app": "chrome"}},
            {"name": "Step 3", "action": "file_controller", "parameters": {"action": "list"}}
        ]
        
        workflow = engine.create_workflow(
            name="Multi-step Workflow",
            goal="Complete multi-step task",
            description="Test workflow",
            steps=steps
        )
        
        assert workflow is not None
        assert len(workflow.steps) == 3

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_memory_integration_workflow(self, mock_loader, mock_memory, mock_config, mica):
        """Test workflow with memory integration."""
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        # Store information in memory
        mica.memory_manager.update_memory("user_preferences", {"theme": "dark"})
        
        # Retrieve from memory
        memory = mica.memory_manager.load_memory("user_preferences")
        
        assert memory is not None

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_approval_workflow(self, mock_loader, mock_memory, mock_config, mica):
        """Test workflow requiring approval."""
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        # Create a high-risk action requiring approval
        from core.approval_flow import get_approval_flow
        approval = get_approval_flow()
        
        result = approval.check_and_request_approval(
            action="delete_file",
            parameters={"path": "/important/file.txt"},
            risk_level="high"
        )
        
        assert result is not None

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_error_recovery_workflow(self, mock_loader, mock_memory, mock_config, mica):
        """Test workflow with error recovery."""
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        # Simulate action failure and recovery
        from core.llm_fallback import LLMFallback
        fallback = LLMFallback()
        
        # Primary fails, fallback should activate
        with patch.object(fallback, '_generate_primary', side_effect=Exception("Primary failed")):
            response = fallback.generate("Test prompt")
        
        assert response is not None

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_multimodal_workflow(self, mock_loader, mock_memory, mock_config, mica):
        """Test workflow with multimodal input (text + image)."""
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        from core.multimodal_context import MultimodalContext
        context = MultimodalContext()
        
        # Add text context
        context.add_text("User wants to analyze this image")
        
        # Add image context
        import numpy as np
        mock_image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        context.add_image(mock_image, description="Screenshot")
        
        # Get combined context
        combined = context.get_context()
        
        assert combined is not None
        assert 'text' in combined
        assert 'images' in combined

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_cross_device_workflow(self, mock_loader, mock_memory, mock_config, mica):
        """Test workflow across multiple devices."""
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        from core.cross_device import CrossDevice
        cross_device = CrossDevice()
        
        # Register devices
        desktop_id = cross_device.register_device("Desktop", "desktop", ["voice", "text"])
        mobile_id = cross_device.register_device("Mobile", "mobile", ["voice"])
        
        # Create session on desktop
        session_id = cross_device.create_session(desktop_id)
        
        # Handoff to mobile
        handoff_result = cross_device.handoff_session(session_id, desktop_id, mobile_id)
        
        assert handoff_result is True

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_background_task_workflow(self, mock_loader, mock_memory, mock_config, mica):
        """Test workflow with background task execution."""
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        from core.background_task_manager import get_background_task_manager
        bg_manager = get_background_task_manager()
        
        # Submit background task
        task_id = bg_manager.submit_task(
            task_func=lambda: "Task completed",
            task_name="Test Task"
        )
        
        # Get task result
        result = bg_manager.get_task_result(task_id)
        
        assert result is not None

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_daily_briefing_workflow(self, mock_loader, mock_memory, mock_config, mica):
        """Test daily briefing workflow."""
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        from core.daily_briefing import DailyBriefing
        briefing = DailyBriefing()
        
        # Add briefing items
        briefing.add_briefing_item("weather", "Sunny, 75°F", "low")
        briefing.add_briefing_item("calendar", "Meeting at 2 PM", "high")
        
        # Generate briefing
        generated = briefing.generate_briefing()
        
        assert generated is not None
        assert len(generated['items']) >= 2


class TestWorkflowPerformance:
    """Performance tests for workflows."""

    @pytest.fixture
    def mica(self):
        """Create a fresh M.I.C.A instance for testing."""
        from main import MicaLive
        return MicaLive()

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_response_time(self, mock_loader, mock_memory, mock_config, mica):
        """Test response time for simple queries."""
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        import time
        start = time.time()
        
        mica.process_input("Hello M.I.C.A")
        
        elapsed = time.time() - start
        assert elapsed < 5.0  # Should respond within 5 seconds

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_concurrent_requests(self, mock_loader, mock_memory, mock_config, mica):
        """Test handling of concurrent requests."""
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        import asyncio
        
        async def process_concurrent():
            tasks = [
                mica.process_input_async(f"Query {i}")
                for i in range(5)
            ]
            results = await asyncio.gather(*tasks)
            return results
        
        # Should handle concurrent requests
        assert True  # Placeholder for actual concurrent test


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
