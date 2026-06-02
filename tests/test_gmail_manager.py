"""
Tests for actions.gmail_manager module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from email.mime.text import MIMEText


class TestGmailManager:
    """Test cases for gmail_manager action."""

    @pytest.fixture
    def gmail_manager(self):
        """Create a fresh gmail_manager instance for testing."""
        from actions.gmail_manager import gmail_manager
        return gmail_manager

    @patch('actions.gmail_manager.googleapiclient')
    def test_send_email(self, mock_googleapi, gmail_manager):
        """Test sending an email."""
        mock_service = MagicMock()
        mock_service.users.return_value.messages.return_value.send.return_value.execute.return_value = {"id": "msg123"}
        mock_googleapi.discovery.build.return_value = mock_service
        
        result = gmail_manager.send(
            to="recipient@example.com",
            subject="Test Subject",
            body="Test body"
        )
        
        assert result is not None

    @patch('actions.gmail_manager.googleapiclient')
    def test_get_emails(self, mock_googleapi, gmail_manager):
        """Test getting emails."""
        mock_service = MagicMock()
        mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": [{"id": "msg1"}, {"id": "msg2"}]
        }
        mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = {
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Test Subject"},
                    {"name": "From", "value": "sender@example.com"}
                ],
                "body": {"data": "VGVzdCBib2R5"}
            }
        }
        mock_googleapi.discovery.build.return_value = mock_service
        
        result = gmail_manager.get_emails(max_results=10)
        
        assert result is not None
        assert len(result) >= 2

    @patch('actions.gmail_manager.googleapiclient')
    def test_search_emails(self, mock_googleapi, gmail_manager):
        """Test searching emails."""
        mock_service = MagicMock()
        mock_service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": [{"id": "msg1"}]
        }
        mock_service.users.return_value.messages.return_value.get.return_value.execute.return_value = {
            "payload": {
                "headers": [{"name": "Subject", "value": "Test"}],
                "body": {"data": "VGVzdA=="}
            }
        }
        mock_googleapi.discovery.build.return_value = mock_service
        
        result = gmail_manager.search(query="is:unread")
        
        assert result is not None

    @patch('actions.gmail_manager.googleapiclient')
    def test_delete_email(self, mock_googleapi, gmail_manager):
        """Test deleting an email."""
        mock_service = MagicMock()
        mock_service.users.return_value.messages.return_value.trash.return_value.execute.return_value = {}
        mock_googleapi.discovery.build.return_value = mock_service
        
        result = gmail_manager.delete("msg123")
        
        assert result is not None

    @patch('actions.gmail_manager.googleapiclient')
    def test_mark_as_read(self, mock_googleapi, gmail_manager):
        """Test marking an email as read."""
        mock_service = MagicMock()
        mock_service.users.return_value.messages.return_value.modify.return_value.execute.return_value = {}
        mock_googleapi.discovery.build.return_value = mock_service
        
        result = gmail_manager.mark_as_read("msg123")
        
        assert result is not None

    @patch('actions.gmail_manager.googleapiclient')
    def test_mark_as_unread(self, mock_googleapi, gmail_manager):
        """Test marking an email as unread."""
        mock_service = MagicMock()
        mock_service.users.return_value.messages.return_value.modify.return_value.execute.return_value = {}
        mock_googleapi.discovery.build.return_value = mock_service
        
        result = gmail_manager.mark_as_unread("msg123")
        
        assert result is not None

    @patch('actions.gmail_manager.googleapiclient')
    def test_star_email(self, mock_googleapi, gmail_manager):
        """Test starring an email."""
        mock_service = MagicMock()
        mock_service.users.return_value.messages.return_value.modify.return_value.execute.return_value = {}
        mock_googleapi.discovery.build.return_value = mock_service
        
        result = gmail_manager.star("msg123")
        
        assert result is not None


class TestGmailManagerErrorHandling:
    """Test error handling in gmail_manager."""

    @pytest.fixture
    def gmail_manager(self):
        """Create a fresh gmail_manager instance for testing."""
        from actions.gmail_manager import gmail_manager
        return gmail_manager

    @patch('actions.gmail_manager.googleapiclient', side_effect=Exception("API error"))
    def test_api_error(self, mock_googleapi, gmail_manager):
        """Test error handling when API fails."""
        with pytest.raises(Exception):
            gmail_manager.send("to@example.com", "Subject", "Body")

    def test_empty_recipient(self, gmail_manager):
        """Test handling of empty recipient."""
        with pytest.raises(ValueError):
            gmail_manager.send("", "Subject", "Body")

    def test_empty_subject(self, gmail_manager):
        """Test handling of empty subject."""
        with pytest.raises(ValueError):
            gmail_manager.send("to@example.com", "", "Body")

    def test_invalid_email_format(self, gmail_manager):
        """Test handling of invalid email format."""
        with pytest.raises(ValueError):
            gmail_manager.send("invalid-email", "Subject", "Body")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
