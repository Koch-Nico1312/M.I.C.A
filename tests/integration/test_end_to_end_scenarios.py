"""
End-to-end integration tests for complete user scenarios
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile


class TestEndToEndScenarios:
    """End-to-end tests for complete user scenarios."""

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_morning_routine_scenario(self, mock_loader, mock_memory, mock_config):
        """Test complete morning routine scenario."""
        from main import JarvisLive
        from core.morning_routine import MorningRoutine
        from core.daily_briefing import DailyBriefing
        
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        jarvis = JarvisLive()
        routine = MorningRoutine()
        briefing = DailyBriefing()
        
        # 1. Generate daily briefing
        briefing.add_briefing_item("weather", "Sunny, 75°F", "low")
        briefing.add_briefing_item("calendar", "Meeting at 10 AM", "high")
        daily_briefing = briefing.generate_briefing()
        
        # 2. Execute morning routine tasks
        routine.add_task("Skin Check", "skin_analysis", None)
        routine.add_task("Weather Check", "weather", None)
        routine.start_routine()
        
        # 3. Process user request
        response = jarvis.process_input("Good morning Jarvis")
        
        assert daily_briefing is not None
        assert response is not None

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_work_session_scenario(self, mock_loader, mock_memory, mock_config):
        """Test complete work session scenario."""
        from main import JarvisLive
        from core.workflow_engine import WorkflowEngine
        from core.vscode_bridge import get_vscode_bridge
        
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        jarvis = JarvisLive()
        engine = WorkflowEngine()
        vscode = get_vscode_bridge()
        
        # 1. Create workflow for work session
        steps = [
            {"name": "Open VS Code", "action": "open_app", "parameters": {"app": "code"}},
            {"name": "Open Project", "action": "vscode", "parameters": {"action": "open_file", "path": "/project/main.py"}},
            {"name": "Start Timer", "action": "reminder", "parameters": {"message": "Work session started"}}
        ]
        
        workflow = engine.create_workflow(
            name="Work Session",
            goal="Start productive work session",
            description="Complete work session setup",
            steps=steps
        )
        
        # 2. Execute workflow
        workflow_id = engine.submit_workflow(workflow)
        
        # 3. Process user request
        response = jarvis.process_input("Start my work session")
        
        assert workflow is not None
        assert response is not None

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_research_scenario(self, mock_loader, mock_memory, mock_config):
        """Test complete research scenario."""
        from main import JarvisLive
        from core.semantic_search import SemanticSearch
        from actions.web_search import web_search_action
        
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        jarvis = JarvisLive()
        search = SemanticSearch()
        
        # 1. Web search
        with patch('actions.web_search.DDGS') as mock_ddgs:
            mock_ddgs.return_value.__enter__.return_value.text.return_value = [
                {"title": "Result 1", "body": "Description 1", "href": "https://example.com/1"}
            ]
            web_results = web_search_action("Python machine learning")
        
        # 2. Store in semantic search
        search.add_text("Python machine learning research")
        
        # 3. Process user request
        response = jarvis.process_input("Research Python machine learning")
        
        assert web_results is not None
        assert response is not None

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_smart_home_automation_scenario(self, mock_loader, mock_memory, mock_config):
        """Test complete smart home automation scenario."""
        from main import JarvisLive
        from core.smart_home import SmartHome
        
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        jarvis = JarvisLive()
        smart_home = SmartHome()
        
        # 1. Discover devices
        with patch('core.smart_home.requests') as mock_requests:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "devices": [
                    {"id": "light1", "name": "Living Room Light", "type": "light"},
                    {"id": "thermostat1", "name": "Thermostat", "type": "thermostat"}
                ]
            }
            mock_requests.get.return_value = mock_response
            devices = smart_home.discover_devices()
        
        # 2. Create automation
        automation = {
            "name": "Movie Night",
            "trigger": {"type": "time", "value": "20:00"},
            "actions": [
                {"device": "light1", "action": "dim", "value": 20},
                {"device": "thermostat1", "action": "set_temperature", "value": 22}
            ]
        }
        
        with patch('core.smart_home.requests') as mock_requests:
            mock_response = MagicMock()
            mock_response.json.return_value = {"status": "success"}
            mock_requests.post.return_value = mock_response
            smart_home.create_automation(automation)
        
        # 3. Process user request
        response = jarvis.process_input("Set up movie night mode")
        
        assert devices is not None
        assert response is not None

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_cross_device_handoff_scenario(self, mock_loader, mock_memory, mock_config):
        """Test complete cross-device handoff scenario."""
        from main import JarvisLive
        from core.cross_device import CrossDevice
        
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        jarvis = JarvisLive()
        cross_device = CrossDevice()
        
        # 1. Register devices
        desktop_id = cross_device.register_device("Desktop", "desktop", ["voice", "text"])
        mobile_id = cross_device.register_device("Mobile", "mobile", ["voice"])
        
        # 2. Create session on desktop
        session_id = cross_device.create_session(desktop_id)
        cross_device.add_message_to_session(session_id, "user", "Start task on desktop")
        
        # 3. Handoff to mobile
        cross_device.handoff_session(session_id, desktop_id, mobile_id)
        
        # 4. Process user request
        response = jarvis.process_input("Continue this task on my phone")
        
        assert session_id is not None
        assert response is not None

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_backup_and_recovery_scenario(self, mock_loader, mock_memory, mock_config):
        """Test complete backup and recovery scenario."""
        from main import JarvisLive
        from memory.memory_backup import get_backup_manager
        from memory.memory_manager import MemoryManager
        
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        jarvis = JarvisLive()
        backup_manager = get_backup_manager()
        memory = MemoryManager()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_path = Path(temp_dir) / "backups"
            backup_path.mkdir()
            backup_manager.backup_path = backup_path
            
            # 1. Store important data
            memory.update_memory("user_preferences", {"theme": "dark", "language": "en"})
            
            # 2. Create backup
            backup_data = {
                "memory": memory.load_memory("user_preferences"),
                "config": {"version": "1.0"}
            }
            backup_id = backup_manager.create_backup(backup_data)
            
            # 3. Simulate data loss and recovery
            recovered = backup_manager.restore_backup(backup_id)
            
            # 4. Process user request
            response = jarvis.process_input("Restore my data from backup")
            
            assert backup_id is not None
            assert recovered == backup_data
            assert response is not None

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_multimodal_interaction_scenario(self, mock_loader, mock_memory, mock_config):
        """Test complete multimodal interaction scenario."""
        from main import JarvisLive
        from core.multimodal_context import MultimodalContext
        from core.passive_vision import PassiveVision
        import numpy as np
        
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        jarvis = JarvisLive()
        context = MultimodalContext()
        vision = PassiveVision()
        
        # 1. Add text context
        context.add_text("User wants to analyze this screenshot")
        
        # 2. Add image context
        mock_image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        context.add_image(mock_image, description="Screenshot of error")
        
        # 3. Get combined context
        combined = context.get_context()
        
        # 4. Process user request
        response = jarvis.process_input("What's in this screenshot?")
        
        assert combined is not None
        assert response is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
