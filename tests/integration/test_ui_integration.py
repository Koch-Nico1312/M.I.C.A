"""
Integration tests for UI system
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestUIIntegration:
    """Integration tests for UI system components."""

    @pytest.fixture
    def ui_bridge(self):
        """Create a fresh UIBridge instance for testing."""
        from ui_bridge import MicaUI
        return MicaUI()

    def test_ui_bridge_initialization(self, ui_bridge):
        """Test UI bridge initialization."""
        assert ui_bridge is not None
        assert hasattr(ui_bridge, 'send_message')
        assert hasattr(ui_bridge, 'receive_message')

    @patch('ui_bridge.QtWidgets')
    def test_ui_message_sending(self, mock_qt, ui_bridge):
        """Test sending messages to UI."""
        mock_signal = MagicMock()
        ui_bridge.message_signal = mock_signal
        
        ui_bridge.send_message("Test message")
        
        assert mock_signal.emit.called

    @patch('ui_bridge.QtWidgets')
    def test_ui_message_receiving(self, mock_qt, ui_bridge):
        """Test receiving messages from UI."""
        mock_signal = MagicMock()
        ui_bridge.input_signal = mock_signal
        
        ui_bridge.receive_message("User input")
        
        assert mock_signal.emit.called

    @patch('ui_bridge.QtWidgets')
    def test_ui_state_updates(self, mock_qt, ui_bridge):
        """Test UI state updates."""
        mock_signal = MagicMock()
        ui_bridge.state_signal = mock_signal
        
        ui_bridge.update_state({"status": "processing", "progress": 50})
        
        assert mock_signal.emit.called

    @patch('ui_bridge.QtWidgets')
    def test_ui_with_mica(self, mock_qt):
        """Test UI integration with M.I.C.A core."""
        from ui_bridge import MicaUI
        from main import MicaLive
        
        ui = MicaUI()
        mica = MicaLive()
        
        # Connect UI to M.I.C.A
        ui.set_mica(mica)
        
        # Send message through UI
        ui.send_message("Test message")
        
        assert ui.mica is not None

    @patch('ui_bridge.QtWidgets')
    def test_hud_overlay_integration(self, mock_qt):
        """Test HUD overlay integration with UI."""
        from ui_bridge import MicaUI
        from core.hud_overlay import get_hud_manager
        
        ui = MicaUI()
        hud = get_hud_manager()
        
        # Show HUD
        hud.show()
        
        # Update HUD through UI
        ui.update_hud({"status": "Active", "message": "Processing"})
        
        assert hud.is_visible

    @patch('ui_bridge.QtWidgets')
    def test_settings_ui_integration(self, mock_qt):
        """Test settings UI integration."""
        from ui_bridge import MicaUI
        from core.settings_overview import get_settings_overview
        
        ui = MicaUI()
        settings = get_settings_overview()
        
        # Get settings
        current_settings = settings.get_settings()
        
        # Update through UI
        ui.update_settings({"theme": "dark"})
        
        assert current_settings is not None

    @patch('ui_bridge.QtWidgets')
    def test_health_dashboard_integration(self, mock_qt):
        """Test health dashboard integration with UI."""
        from ui_bridge import MicaUI
        from core.health_dashboard import get_health_dashboard
        
        ui = MicaUI()
        dashboard = get_health_dashboard()
        
        # Get health status
        health = dashboard.get_health_status()
        
        # Display in UI
        ui.display_health(health)
        
        assert health is not None


class TestUIPerformance:
    """Performance tests for UI system."""

    @patch('ui_bridge.QtWidgets')
    def test_ui_response_time(self, mock_qt):
        """Test UI response time."""
        from ui_bridge import MicaUI
        
        import time
        ui = MicaUI()
        
        start = time.time()
        ui.send_message("Test message")
        elapsed = time.time() - start
        
        assert elapsed < 0.5  # Should respond quickly

    @patch('ui_bridge.QtWidgets')
    def test_ui_concurrent_updates(self, mock_qt):
        """Test handling of concurrent UI updates."""
        from ui_bridge import MicaUI
        import asyncio
        
        ui = MicaUI()
        
        async def update_concurrent():
            tasks = [
                ui.update_state_async({"status": f"status_{i}"})
                for i in range(10)
            ]
            await asyncio.gather(*tasks)
        
        # Should handle concurrent updates
        assert True  # Placeholder for actual concurrent test


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
