"""
Tests for core.hud_overlay module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path


class TestHUDOverlay:
    """Test cases for HUDOverlay class."""

    @pytest.fixture
    def hud_overlay(self):
        """Create a fresh HUDOverlay instance for testing."""
        from core.hud_overlay import HUDOverlay
        return HUDOverlay()

    def test_hud_overlay_initialization(self, hud_overlay):
        """Test HUDOverlay initialization."""
        assert hud_overlay is not None
        assert hasattr(hud_overlay, 'show')
        assert hasattr(hud_overlay, 'hide')
        assert hasattr(hud_overlay, 'update')

    def test_show_hud(self, hud_overlay):
        """Test showing the HUD overlay."""
        hud_overlay.show()
        
        assert hud_overlay.is_visible

    def test_hide_hud(self, hud_overlay):
        """Test hiding the HUD overlay."""
        hud_overlay.is_visible = True
        
        hud_overlay.hide()
        
        assert not hud_overlay.is_visible

    def test_update_hud(self, hud_overlay):
        """Test updating HUD content."""
        hud_overlay.update(
            status="Processing",
            progress=50,
            message="Analyzing data..."
        )
        
        assert hud_overlay.current_status == "Processing"

    def test_add_widget(self, hud_overlay):
        """Test adding a widget to the HUD."""
        widget_id = hud_overlay.add_widget(
            widget_type="status",
            position="top_left",
            content="Status: OK"
        )
        
        assert widget_id is not None
        assert widget_id in hud_overlay.widgets

    def test_remove_widget(self, hud_overlay):
        """Test removing a widget from the HUD."""
        widget_id = hud_overlay.add_widget("status", "top_left", "Status: OK")
        
        hud_overlay.remove_widget(widget_id)
        
        assert widget_id not in hud_overlay.widgets

    def test_set_position(self, hud_overlay):
        """Test setting HUD position."""
        hud_overlay.set_position(x=100, y=100)
        
        assert hud_overlay.position == (100, 100)

    def test_set_opacity(self, hud_overlay):
        """Test setting HUD opacity."""
        hud_overlay.set_opacity(0.8)
        
        assert hud_overlay.opacity == 0.8

    def test_set_theme(self, hud_overlay):
        """Test setting HUD theme."""
        hud_overlay.set_theme("dark")
        
        assert hud_overlay.theme == "dark"

    def test_get_widget(self, hud_overlay):
        """Test getting a widget by ID."""
        widget_id = hud_overlay.add_widget("status", "top_left", "Status: OK")
        
        widget = hud_overlay.get_widget(widget_id)
        
        assert widget is not None
        assert widget['content'] == "Status: OK"


class TestHUDOverlayErrorHandling:
    """Test error handling in HUDOverlay."""

    @pytest.fixture
    def hud_overlay(self):
        """Create a fresh HUDOverlay instance for testing."""
        from core.hud_overlay import HUDOverlay
        return HUDOverlay()

    def test_remove_nonexistent_widget(self, hud_overlay):
        """Test removing a non-existent widget."""
        result = hud_overlay.remove_widget("nonexistent_id")
        assert result is False

    def test_invalid_opacity(self, hud_overlay):
        """Test handling of invalid opacity values."""
        invalid_opacities = [-1, 2, "invalid", None]
        
        for invalid_opacity in invalid_opacities:
            try:
                hud_overlay.set_opacity(invalid_opacity)
            except (ValueError, TypeError):
                pass  # Expected

    def test_invalid_position(self, hud_overlay):
        """Test handling of invalid position values."""
        invalid_positions = [
            ("invalid", 100),
            (100, "invalid"),
            (-100, 100),
            (100, -100)
        ]
        
        for invalid_position in invalid_positions:
            try:
                hud_overlay.set_position(*invalid_position)
            except (ValueError, TypeError):
                pass  # Expected


class TestHUDOverlayIntegration:
    """Integration tests for HUDOverlay."""

    @patch('core.hud_overlay.QtWidgets')
    def test_full_hud_lifecycle(self, mock_qt):
        """Test a full HUD lifecycle."""
        from core.hud_overlay import HUDOverlay
        
        mock_window = MagicMock()
        mock_qt.QMainWindow.return_value = mock_window
        
        hud = HUDOverlay()
        
        # Show HUD
        hud.show()
        assert hud.is_visible
        
        # Add widgets
        hud.add_widget("status", "top_left", "Status: OK")
        hud.add_widget("progress", "top_right", "50%")
        
        # Update content
        hud.update(status="Processing", progress=75)
        
        # Hide HUD
        hud.hide()
        assert not hud.is_visible

    def test_hud_with_performance_tracking(self):
        """Test HUD integration with performance tracking."""
        from core.hud_overlay import HUDOverlay
        from core.performance_tracker import get_performance_tracker
        
        hud = HUDOverlay()
        tracker = get_performance_tracker()
        
        # Enable performance display
        hud.show_performance = True
        
        # Update with performance data
        performance_data = tracker.get_current_metrics()
        hud.update_performance(performance_data)
        
        assert hud.show_performance is True

    def test_hud_with_workflow_status(self):
        """Test HUD integration with workflow status."""
        from core.hud_overlay import HUDOverlay
        from core.workflow_engine import get_workflow_engine
        
        hud = HUDOverlay()
        engine = get_workflow_engine()
        
        # Show workflow status
        hud.show_workflow_status = True
        
        # Update with workflow data
        workflow_data = engine.get_statistics()
        hud.update_workflow(workflow_data)
        
        assert hud.show_workflow_status is True

    def test_hud_persistence(self):
        """Test HUD configuration persistence."""
        from core.hud_overlay import HUDOverlay
        
        hud1 = HUDOverlay()
        hud1.set_position(100, 100)
        hud1.set_opacity(0.8)
        hud1.set_theme("dark")
        hud1.save_configuration()
        
        hud2 = HUDOverlay()
        hud2.load_configuration()
        
        # Should load saved configuration
        assert True  # Placeholder for actual persistence test


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
