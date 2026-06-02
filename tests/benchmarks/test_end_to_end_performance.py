"""
Performance benchmarks for end-to-end scenarios
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestEndToEndScenariosPerformance:
    """Performance benchmarks for complete end-to-end scenarios."""

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_complete_user_session_performance(self, mock_loader, mock_memory, mock_config, benchmark):
        """Benchmark complete user session."""
        from main import JarvisLive
        
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        jarvis = JarvisLive()
        
        def complete_session():
            # User greeting
            jarvis.process_input("Hello Jarvis")
            # User question
            jarvis.process_input("What's the weather?")
            # User request
            jarvis.process_input("Open Chrome")
            # User farewell
            jarvis.process_input("Goodbye")
            return True
        
        result = benchmark(complete_session)
        assert result is not None

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_workflow_execution_performance(self, mock_loader, mock_memory, mock_config, benchmark):
        """Benchmark complete workflow execution."""
        from main import JarvisLive
        from core.workflow_engine import WorkflowEngine
        
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        jarvis = JarvisLive()
        engine = WorkflowEngine()
        
        def execute_workflow():
            # Create workflow
            steps = [
                {"name": "Search", "action": "web_search", "parameters": {"query": "Python"}},
                {"name": "Open", "action": "open_app", "parameters": {"app": "chrome"}},
                {"name": "Save", "action": "file_controller", "parameters": {"action": "write"}}
            ]
            workflow = engine.create_workflow(
                name="Test Workflow",
                goal="Test",
                description="Test",
                steps=steps
            )
            # Submit workflow
            engine.submit_workflow(workflow)
            return True
        
        result = benchmark(execute_workflow)
        assert result is not None

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_multimodal_interaction_performance(self, mock_loader, mock_memory, mock_config, benchmark):
        """Benchmark multimodal interaction."""
        from main import JarvisLive
        from core.multimodal_context import MultimodalContext
        import numpy as np
        
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        jarvis = JarvisLive()
        context = MultimodalContext()
        
        def multimodal_interaction():
            # Add text context
            context.add_text("Analyze this image")
            # Add image context
            image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
            context.add_image(image, description="Screenshot")
            # Process through Jarvis
            jarvis.process_input("What's in this image?", context=context)
            return True
        
        result = benchmark(multimodal_interaction)
        assert result is not None

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_cross_device_handoff_performance(self, mock_loader, mock_memory, mock_config, benchmark):
        """Benchmark cross-device handoff."""
        from main import JarvisLive
        from core.cross_device import CrossDevice
        
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        jarvis = JarvisLive()
        cross_device = CrossDevice()
        
        def cross_device_handoff():
            # Register devices
            desktop_id = cross_device.register_device("Desktop", "desktop", ["voice", "text"])
            mobile_id = cross_device.register_device("Mobile", "mobile", ["voice"])
            # Create session
            session_id = cross_device.create_session(desktop_id)
            cross_device.add_message_to_session(session_id, "user", "Start task")
            # Handoff
            cross_device.handoff_session(session_id, desktop_id, mobile_id)
            return True
        
        result = benchmark(cross_device_handoff)
        assert result is not None

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_backup_and_recovery_performance(self, mock_loader, mock_memory, mock_config, benchmark, tmp_path):
        """Benchmark backup and recovery."""
        from main import JarvisLive
        from memory.memory_backup import get_backup_manager
        from memory.memory_manager import MemoryManager
        
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        jarvis = JarvisLive()
        memory = MemoryManager()
        
        backup_path = tmp_path / "backups"
        backup_path.mkdir()
        
        manager = get_backup_manager()
        manager.backup_path = backup_path
        
        def backup_and_recovery():
            # Store data
            memory.update_memory("user_data", {"preferences": {"theme": "dark"}})
            # Create backup
            backup_data = {"memory": memory.load_memory("user_data")}
            backup_id = manager.create_backup(backup_data)
            # Restore backup
            manager.restore_backup(backup_id)
            return True
        
        result = benchmark(backup_and_recovery)
        assert result is not None

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_morning_routine_performance(self, mock_loader, mock_memory, mock_config, benchmark):
        """Benchmark morning routine execution."""
        from main import JarvisLive
        from core.morning_routine import MorningRoutine
        from core.daily_briefing import DailyBriefing
        
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        jarvis = JarvisLive()
        routine = MorningRoutine()
        briefing = DailyBriefing()
        
        def morning_routine():
            # Generate briefing
            briefing.add_briefing_item("weather", "Sunny, 75°F", "low")
            briefing.generate_briefing()
            # Execute routine tasks
            routine.add_task("Skin Check", "skin_analysis", None)
            routine.start_routine()
            # Process through Jarvis
            jarvis.process_input("Good morning Jarvis")
            return True
        
        result = benchmark(morning_routine)
        assert result is not None

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_research_session_performance(self, mock_loader, mock_memory, mock_config, benchmark):
        """Benchmark research session."""
        from main import JarvisLive
        from core.semantic_search import SemanticSearch
        
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        jarvis = JarvisLive()
        search = SemanticSearch()
        
        def research_session():
            # Add to search index
            search.add_text("Python machine learning research")
            # Process research query
            jarvis.process_input("Research Python machine learning")
            # Follow-up query
            jarvis.process_input("Tell me more about deep learning")
            return True
        
        result = benchmark(research_session)
        assert result is not None

    @patch('main.get_config')
    @patch('main.get_memory_manager')
    @patch('main.get_action_loader')
    def test_error_recovery_performance(self, mock_loader, mock_memory, mock_config, benchmark):
        """Benchmark error recovery."""
        from main import JarvisLive
        from core.llm_fallback import LLMFallback
        
        mock_config.return_value = Mock()
        mock_memory.return_value = Mock()
        mock_loader.return_value = Mock()
        
        jarvis = JarvisLive()
        fallback = LLMFallback()
        fallback.enable_auto_fallback = True
        
        def error_recovery():
            # Simulate primary failure
            with patch.object(fallback, '_generate_primary', side_effect=Exception("Primary failed")):
                jarvis.process_input("Test query")
            return True
        
        result = benchmark(error_recovery)
        assert result is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--benchmark-only'])
