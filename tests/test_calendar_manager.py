"""
Tests for actions.calendar_manager module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta


class TestCalendarManager:
    """Test cases for calendar_manager action."""

    @pytest.fixture
    def calendar_manager(self):
        """Create a fresh calendar_manager instance for testing."""
        from actions.calendar_manager import calendar_manager
        return calendar_manager

    @patch('actions.calendar_manager.googleapiclient')
    def test_create_event(self, mock_googleapi, calendar_manager):
        """Test creating a calendar event."""
        mock_service = MagicMock()
        mock_googleapi.discovery.build.return_value = mock_service
        
        result = calendar_manager.create_event(
            title="Test Meeting",
            start_time=datetime.now() + timedelta(hours=1),
            duration_minutes=60
        )
        
        assert result is not None

    @patch('actions.calendar_manager.googleapiclient')
    def test_get_events(self, mock_googleapi, calendar_manager):
        """Test getting calendar events."""
        mock_service = MagicMock()
        mock_service.events.return_value.list.return_value.execute.return_value = {
            "items": [
                {"summary": "Event 1", "start": {"dateTime": "2024-01-01T10:00:00"}},
                {"summary": "Event 2", "start": {"dateTime": "2024-01-01T14:00:00"}}
            ]
        }
        mock_googleapi.discovery.build.return_value = mock_service
        
        result = calendar_manager.get_events()
        
        assert result is not None
        assert len(result) >= 2

    @patch('actions.calendar_manager.googleapiclient')
    def test_delete_event(self, mock_googleapi, calendar_manager):
        """Test deleting a calendar event."""
        mock_service = MagicMock()
        mock_googleapi.discovery.build.return_value = mock_service
        
        result = calendar_manager.delete_event("event_id_123")
        
        assert result is not None

    @patch('actions.calendar_manager.googleapiclient')
    def test_update_event(self, mock_googleapi, calendar_manager):
        """Test updating a calendar event."""
        mock_service = MagicMock()
        mock_googleapi.discovery.build.return_value = mock_service
        
        result = calendar_manager.update_event(
            event_id="event_id_123",
            title="Updated Title"
        )
        
        assert result is not None

    @patch('actions.calendar_manager.googleapiclient')
    def test_get_availability(self, mock_googleapi, calendar_manager):
        """Test getting availability for a time slot."""
        mock_service = MagicMock()
        mock_service.freebusy.return_value.query.return_value.execute.return_value = {
            "calendars": {
                "primary": {
                    "busy": [
                        {"start": "2024-01-01T10:00:00Z", "end": "2024-01-01T11:00:00Z"}
                    ]
                }
            }
        }
        mock_googleapi.discovery.build.return_value = mock_service
        
        start = datetime.now() + timedelta(hours=1)
        end = datetime.now() + timedelta(hours=2)
        
        result = calendar_manager.get_availability(start, end)
        
        assert result is not None

    @patch('actions.calendar_manager.googleapiclient')
    def test_list_calendars(self, mock_googleapi, calendar_manager):
        """Test listing all calendars."""
        mock_service = MagicMock()
        mock_service.calendarList.return_value.list.return_value.execute.return_value = {
            "items": [
                {"id": "primary", "summary": "Primary Calendar"},
                {"id": "work", "summary": "Work Calendar"}
            ]
        }
        mock_googleapi.discovery.build.return_value = mock_service
        
        result = calendar_manager.list_calendars()
        
        assert result is not None
        assert len(result) >= 2


class TestCalendarManagerErrorHandling:
    """Test error handling in calendar_manager."""

    @pytest.fixture
    def calendar_manager(self):
        """Create a fresh calendar_manager instance for testing."""
        from actions.calendar_manager import calendar_manager
        return calendar_manager

    @patch('actions.calendar_manager.googleapiclient', side_effect=Exception("API error"))
    def test_api_error(self, mock_googleapi, calendar_manager):
        """Test error handling when API fails."""
        with pytest.raises(Exception):
            calendar_manager.create_event("Test", datetime.now(), 60)

    def test_empty_title(self, calendar_manager):
        """Test handling of empty event title."""
        with pytest.raises(ValueError):
            calendar_manager.create_event("", datetime.now(), 60)

    def test_invalid_time_range(self, calendar_manager):
        """Test handling of invalid time range."""
        start = datetime.now() + timedelta(hours=2)
        end = datetime.now() + timedelta(hours=1)  # End before start
        
        with pytest.raises(ValueError):
            calendar_manager.get_availability(start, end)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
