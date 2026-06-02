"""
Tests for core.proactive_suggestions module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta


class TestProactiveSuggestions:
    """Test cases for ProactiveSuggestions class."""

    @pytest.fixture
    def proactive_suggestions(self):
        """Create a fresh ProactiveSuggestions instance for testing."""
        from core.proactive_suggestions import ProactiveSuggestions
        return ProactiveSuggestions()

    def test_proactive_suggestions_initialization(self, proactive_suggestions):
        """Test ProactiveSuggestions initialization."""
        assert proactive_suggestions is not None
        assert hasattr(proactive_suggestions, 'start')
        assert hasattr(proactive_suggestions, 'stop')
        assert hasattr(proactive_suggestions, 'track_action')

    def test_track_action(self, proactive_suggestions):
        """Test tracking user actions."""
        proactive_suggestions.track_action("open_chrome", success=True)
        
        assert "open_chrome" in proactive_suggestions.action_history
        assert proactive_suggestions.action_history["open_chrome"]["count"] > 0

    def test_generate_suggestions(self, proactive_suggestions):
        """Test generating proactive suggestions."""
        # Track some actions
        proactive_suggestions.track_action("open_chrome", success=True)
        proactive_suggestions.track_action("open_chrome", success=True)
        proactive_suggestions.track_action("open_chrome", success=True)
        
        suggestions = proactive_suggestions.generate_suggestions()
        
        assert suggestions is not None
        assert isinstance(suggestions, list)

    def test_start_monitoring(self, proactive_suggestions):
        """Test starting proactive monitoring."""
        proactive_suggestions.start()
        
        assert proactive_suggestions.is_running

    def test_stop_monitoring(self, proactive_suggestions):
        """Test stopping proactive monitoring."""
        proactive_suggestions.is_running = True
        
        proactive_suggestions.stop()
        
        assert not proactive_suggestions.is_running

    def test_pattern_detection(self, proactive_suggestions):
        """Test pattern detection in user actions."""
        # Track repetitive actions
        for _ in range(5):
            proactive_suggestions.track_action("check_weather", success=True)
        
        patterns = proactive_suggestions.detect_patterns()
        
        assert patterns is not None
        assert len(patterns) > 0

    def test_speak_callback(self, proactive_suggestions):
        """Test speak callback for suggestions."""
        mock_speak = Mock()
        proactive_suggestions.set_speak_callback(mock_speak)
        
        proactive_suggestions.speak_suggestion("You should check the weather")
        
        mock_speak.assert_called_once_with("You should check the weather")

    def test_cooldown_period(self, proactive_suggestions):
        """Test cooldown period for suggestions."""
        proactive_suggestions.cooldown_minutes = 5
        
        # Generate a suggestion
        proactive_suggestions.last_suggestion_time = datetime.now()
        
        # Try to generate another suggestion immediately
        should_suggest = proactive_suggestions.should_suggest()
        
        assert not should_suggest  # Should be in cooldown

    def test_max_suggestions_limit(self, proactive_suggestions):
        """Test maximum suggestions limit."""
        proactive_suggestions.max_suggestions = 3
        
        # Generate more than max suggestions
        suggestions = proactive_suggestions.generate_suggestions()
        
        assert len(suggestions) <= proactive_suggestions.max_suggestions


class TestProactiveSuggestionsErrorHandling:
    """Test error handling in ProactiveSuggestions."""

    @pytest.fixture
    def proactive_suggestions(self):
        """Create a fresh ProactiveSuggestions instance for testing."""
        from core.proactive_suggestions import ProactiveSuggestions
        return ProactiveSuggestions()

    def test_invalid_action_tracking(self, proactive_suggestions):
        """Test tracking invalid actions."""
        invalid_actions = [None, "", [], {}]
        
        for invalid_action in invalid_actions:
            try:
                proactive_suggestions.track_action(invalid_action)
            except (ValueError, TypeError, AttributeError):
                pass  # Expected

    def test_speak_callback_error(self, proactive_suggestions):
        """Test error handling in speak callback."""
        mock_speak = Mock(side_effect=Exception("Speak error"))
        proactive_suggestions.set_speak_callback(mock_speak)
        
        # Should handle error gracefully
        proactive_suggestions.speak_suggestion("Test suggestion")
        
        # Should not crash
        assert True


class TestProactiveSuggestionsIntegration:
    """Integration tests for ProactiveSuggestions."""

    def test_full_suggestion_cycle(self):
        """Test a full proactive suggestion cycle."""
        from core.proactive_suggestions import ProactiveSuggestions
        
        suggestions = ProactiveSuggestions()
        
        # Track actions
        suggestions.track_action("open_chrome", success=True)
        suggestions.track_action("open_chrome", success=True)
        suggestions.track_action("open_chrome", success=True)
        
        # Generate suggestions
        generated = suggestions.generate_suggestions()
        
        assert generated is not None
        
        # Should detect pattern
        patterns = suggestions.detect_patterns()
        assert patterns is not None

    def test_suggestion_persistence(self):
        """Test that suggestion history persists."""
        from core.proactive_suggestions import ProactiveSuggestions
        
        suggestions1 = ProactiveSuggestions()
        suggestions1.track_action("test_action", success=True)
        
        # In a real implementation, this would persist to disk
        history = suggestions1.action_history
        
        assert "test_action" in history

    def test_integration_with_action_history(self):
        """Test integration with action history system."""
        from core.proactive_suggestions import ProactiveSuggestions
        from core.action_history import get_action_history
        
        suggestions = ProactiveSuggestions()
        action_history = get_action_history()
        
        # Track action in both systems
        suggestions.track_action("test_action", success=True)
        action_history.record_action("test_tool", "test_action", {})
        
        # Both should have records
        assert "test_action" in suggestions.action_history
        assert len(action_history.get_history()) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
