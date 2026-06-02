"""
Tests for actions.send_message module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestSendMessage:
    """Test cases for send_message action."""

    @pytest.fixture
    def send_message(self):
        """Create a fresh send_message instance for testing."""
        from actions.send_message import send_message
        return send_message

    @patch('actions.send_message.pywhatkit')
    def test_send_whatsapp_message(self, mock_pywhatkit, send_message):
        """Test sending a WhatsApp message."""
        mock_pywhatkit.sendwhatmsg_instantly.return_value = True
        
        result = send_message(
            platform="whatsapp",
            recipient="+1234567890",
            message="Test message"
        )
        
        assert result is not None

    @patch('actions.send_message.pywhatkit')
    def test_send_telegram_message(self, mock_telegram, send_message):
        """Test sending a Telegram message."""
        mock_telegram.send_message.return_value = MagicMock()
        
        result = send_message(
            platform="telegram",
            recipient="@username",
            message="Test message"
        )
        
        assert result is not None

    @patch('actions.send_message.smtplib')
    def test_send_email(self, mock_smtplib, send_message):
        """Test sending an email."""
        mock_smtp = MagicMock()
        mock_smtplib.SMTP.return_value.__enter__.return_value = mock_smtp
        
        result = send_message(
            platform="email",
            recipient="user@example.com",
            message="Test email",
            subject="Test Subject"
        )
        
        assert result is not None
        mock_smtp.send_message.assert_called_once()

    @patch('actions.send_message.pywhatkit')
    def test_send_with_delay(self, mock_pywhatkit, send_message):
        """Test sending message with delay."""
        mock_pywhatkit.sendwhatmsg.return_value = True
        
        result = send_message(
            platform="whatsapp",
            recipient="+1234567890",
            message="Test message",
            delay_minutes=5
        )
        
        assert result is not None

    def test_invalid_platform(self, send_message):
        """Test handling of invalid platform."""
        with pytest.raises(ValueError):
            send_message(
                platform="invalid_platform",
                recipient="+1234567890",
                message="Test"
            )

    def test_empty_message(self, send_message):
        """Test handling of empty message."""
        with pytest.raises(ValueError):
            send_message(
                platform="whatsapp",
                recipient="+1234567890",
                message=""
            )

    def test_empty_recipient(self, send_message):
        """Test handling of empty recipient."""
        with pytest.raises(ValueError):
            send_message(
                platform="whatsapp",
                recipient="",
                message="Test"
            )


class TestSendMessageErrorHandling:
    """Test error handling in send_message."""

    @pytest.fixture
    def send_message(self):
        """Create a fresh send_message instance for testing."""
        from actions.send_message import send_message
        return send_message

    @patch('actions.send_message.pywhatkit', side_effect=Exception("Send error"))
    def test_whatsapp_error(self, mock_pywhatkit, send_message):
        """Test error handling when WhatsApp send fails."""
        with pytest.raises(Exception):
            send_message(
                platform="whatsapp",
                recipient="+1234567890",
                message="Test"
            )

    @patch('actions.send_message.smtplib', side_effect=Exception("SMTP error"))
    def test_email_error(self, mock_smtplib, send_message):
        """Test error handling when email send fails."""
        with pytest.raises(Exception):
            send_message(
                platform="email",
                recipient="user@example.com",
                message="Test",
                subject="Subject"
            )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
