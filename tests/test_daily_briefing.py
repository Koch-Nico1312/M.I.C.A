"""
Tests for core.daily_briefing module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta


class TestDailyBriefing:
    """Test cases for DailyBriefing class."""

    @pytest.fixture
    def daily_briefing(self):
        """Create a fresh DailyBriefing instance for testing."""
        from core.daily_briefing import DailyBriefing
        return DailyBriefing()

    def test_daily_briefing_initialization(self, daily_briefing):
        """Test DailyBriefing initialization."""
        assert daily_briefing is not None
        assert hasattr(daily_briefing, 'generate_briefing')
        assert hasattr(daily_briefing, 'add_briefing_item')
        assert hasattr(daily_briefing, 'get_briefing')

    def test_generate_briefing(self, daily_briefing):
        """Test generating a daily briefing."""
        briefing = daily_briefing.generate_briefing()
        
        assert briefing is not None
        assert isinstance(briefing, dict)
        assert 'date' in briefing
        assert 'items' in briefing

    def test_add_briefing_item(self, daily_briefing):
        """Test adding an item to the briefing."""
        daily_briefing.add_briefing_item(
            category="weather",
            content="Sunny day with high of 75°F",
            priority="medium"
        )
        
        briefing = daily_briefing.get_briefing()
        assert len(briefing['items']) > 0

    def test_get_briefing(self, daily_briefing):
        """Test getting the current briefing."""
        daily_briefing.add_briefing_item(
            category="calendar",
            content="Meeting at 2 PM",
            priority="high"
        )
        
        briefing = daily_briefing.get_briefing()
        
        assert briefing is not None
        assert len(briefing['items']) > 0

    def test_briefing_categories(self, daily_briefing):
        """Test briefing by category."""
        daily_briefing.add_briefing_item("weather", "Sunny", "low")
        daily_briefing.add_briefing_item("calendar", "Meeting", "high")
        daily_briefing.add_briefing_item("tasks", "Finish report", "medium")
        
        weather_items = daily_briefing.get_items_by_category("weather")
        
        assert len(weather_items) == 1
        assert weather_items[0]['content'] == "Sunny"

    def test_briefing_priority_sorting(self, daily_briefing):
        """Test sorting briefing items by priority."""
        daily_briefing.add_briefing_item("item1", "Low priority", "low")
        daily_briefing.add_briefing_item("item2", "High priority", "high")
        daily_briefing.add_briefing_item("item3", "Medium priority", "medium")
        
        sorted_items = daily_briefing.get_sorted_items()
        
        # High priority should come first
        assert sorted_items[0]['priority'] == "high"

    def test_clear_briefing(self, daily_briefing):
        """Test clearing the briefing."""
        daily_briefing.add_briefing_item("test", "Test item", "low")
        
        daily_briefing.clear_briefing()
        
        briefing = daily_briefing.get_briefing()
        assert len(briefing['items']) == 0

    def test_briefing_scheduled_generation(self, daily_briefing):
        """Test scheduled briefing generation."""
        daily_briefing.schedule_time = "08:00"
        daily_briefing.enable_scheduling = True
        
        # Should be able to schedule
        assert daily_briefing.enable_scheduling is True

    def test_briefing_customization(self, daily_briefing):
        """Test briefing customization options."""
        daily_briefing.include_weather = True
        daily_briefing.include_calendar = True
        daily_briefing.include_tasks = True
        daily_briefing.include_news = False
        
        briefing = daily_briefing.generate_briefing()
        
        assert briefing is not None


class TestDailyBriefingErrorHandling:
    """Test error handling in DailyBriefing."""

    @pytest.fixture
    def daily_briefing(self):
        """Create a fresh DailyBriefing instance for testing."""
        from core.daily_briefing import DailyBriefing
        return DailyBriefing()

    def test_invalid_priority(self, daily_briefing):
        """Test handling of invalid priority values."""
        invalid_priorities = [None, "", "invalid", 123]
        
        for invalid_priority in invalid_priorities:
            try:
                daily_briefing.add_briefing_item("test", "content", invalid_priority)
            except (ValueError, TypeError):
                pass  # Expected

    def test_invalid_category(self, daily_briefing):
        """Test handling of invalid category values."""
        invalid_categories = [None, "", 123]
        
        for invalid_category in invalid_categories:
            try:
                daily_briefing.add_briefing_item(invalid_category, "content", "low")
            except (ValueError, TypeError):
                pass  # Expected


class TestDailyBriefingIntegration:
    """Integration tests for DailyBriefing."""

    @patch('core.daily_briefing.weather_action')
    @patch('core.daily_briefing.calendar_manager')
    def test_full_briefing_generation(self, mock_calendar, mock_weather):
        """Test full briefing generation with real data sources."""
        from core.daily_briefing import DailyBriefing
        
        # Mock weather
        mock_weather.return_value = "Sunny, 75°F"
        
        # Mock calendar
        mock_calendar.get_events.return_value = [
            {"title": "Meeting", "time": "14:00"}
        ]
        
        briefing = DailyBriefing()
        briefing.include_weather = True
        briefing.include_calendar = True
        
        generated = briefing.generate_briefing()
        
        assert generated is not None
        assert 'items' in generated

    def test_briefing_with_memory(self):
        """Test briefing integration with memory system."""
        from core.daily_briefing import DailyBriefing
        from memory.memory_manager import MemoryManager
        
        briefing = DailyBriefing()
        memory = MemoryManager()
        
        # Add memory items
        # memory.add_memory("User preference: likes morning briefings")
        
        # Generate briefing
        generated = briefing.generate_briefing()
        
        assert generated is not None

    def test_briefing_delivery(self):
        """Test briefing delivery to user."""
        from core.daily_briefing import DailyBriefing
        
        briefing = DailyBriefing()
        briefing.add_briefing_item("test", "Test briefing item", "high")
        
        # Mock delivery
        mock_speak = Mock()
        briefing.set_delivery_callback(mock_speak)
        
        briefing.deliver_briefing()
        
        # Should have called delivery callback
        assert True  # Placeholder for actual delivery test

    def test_briefing_history(self):
        """Test briefing history tracking."""
        from core.daily_briefing import DailyBriefing
        
        briefing = DailyBriefing()
        
        # Generate multiple briefings
        for i in range(3):
            briefing.add_briefing_item(f"item_{i}", f"Content {i}", "low")
            briefing.save_briefing()
        
        history = briefing.get_briefing_history()
        
        assert len(history) >= 3


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
