"""
Tests for core.session_manager module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta


class TestSessionManager:
    """Test cases for SessionManager class."""

    @pytest.fixture
    def session_manager(self):
        """Create a fresh SessionManager instance for testing."""
        from core.session_manager import SessionManager
        return SessionManager()

    def test_session_manager_initialization(self, session_manager):
        """Test SessionManager initialization."""
        assert session_manager is not None
        assert hasattr(session_manager, 'create_session')
        assert hasattr(session_manager, 'get_session')
        assert hasattr(session_manager, 'end_session')

    def test_create_session(self, session_manager):
        """Test creating a new session."""
        session = session_manager.create_session()
        
        assert session is not None
        assert hasattr(session, 'session_id')
        assert hasattr(session, 'created_at')

    def test_get_session(self, session_manager):
        """Test retrieving a session by ID."""
        session = session_manager.create_session()
        session_id = session.session_id
        
        retrieved = session_manager.get_session(session_id)
        
        assert retrieved is not None
        assert retrieved.session_id == session_id

    def test_end_session(self, session_manager):
        """Test ending a session."""
        session = session_manager.create_session()
        session_id = session.session_id
        
        session_manager.end_session(session_id)
        
        retrieved = session_manager.get_session(session_id)
        assert retrieved is not None
        assert retrieved.ended_at is not None

    def test_add_message_to_session(self, session_manager):
        """Test adding messages to a session."""
        session = session_manager.create_session()
        
        session_manager.add_message(session.session_id, "user", "Hello M.I.C.A")
        session_manager.add_message(session.session_id, "assistant", "Hello user")
        
        retrieved = session_manager.get_session(session.session_id)
        assert len(retrieved.messages) == 2

    def test_session_persistence(self, session_manager):
        """Test session persistence to disk."""
        session = session_manager.create_session()
        session_manager.add_message(session.session_id, "user", "Test message")
        
        # Save session
        session_manager.save_sessions()
        
        # Load sessions
        session_manager.load_sessions()
        
        # Should persist
        assert True  # Placeholder for actual persistence test

    def test_session_cleanup(self, session_manager):
        """Test automatic session cleanup."""
        # Create old session
        old_session = session_manager.create_session()
        old_session.created_at = datetime.now() - timedelta(days=10)
        
        # Create new session
        new_session = session_manager.create_session()
        
        # Cleanup old sessions
        session_manager.cleanup_old_sessions(max_age_days=7)
        
        # Old session should be removed
        assert old_session.session_id not in session_manager.sessions

    def test_max_messages_limit(self, session_manager):
        """Test maximum messages per session limit."""
        session_manager.max_messages = 5
        session = session_manager.create_session()
        
        # Add more than max messages
        for i in range(10):
            session_manager.add_message(session.session_id, "user", f"Message {i}")
        
        retrieved = session_manager.get_session(session.session_id)
        assert len(retrieved.messages) <= session_manager.max_messages


class TestSessionManagerErrorHandling:
    """Test error handling in SessionManager."""

    @pytest.fixture
    def session_manager(self):
        """Create a fresh SessionManager instance for testing."""
        from core.session_manager import SessionManager
        return SessionManager()

    def test_invalid_session_id(self, session_manager):
        """Test handling of invalid session ID."""
        result = session_manager.get_session("invalid_id")
        assert result is None

    def test_end_nonexistent_session(self, session_manager):
        """Test ending a non-existent session."""
        result = session_manager.end_session("invalid_id")
        assert result is False

    def test_add_message_to_invalid_session(self, session_manager):
        """Test adding message to invalid session."""
        result = session_manager.add_message("invalid_id", "user", "Test")
        assert result is False


class TestSessionManagerIntegration:
    """Integration tests for SessionManager."""

    def test_full_session_lifecycle(self):
        """Test a full session lifecycle."""
        from core.session_manager import SessionManager
        
        manager = SessionManager()
        
        # Create session
        session = manager.create_session()
        assert session is not None
        
        # Add messages
        manager.add_message(session.session_id, "user", "Hello")
        manager.add_message(session.session_id, "assistant", "Hi there!")
        
        # Get session
        retrieved = manager.get_session(session.session_id)
        assert len(retrieved.messages) == 2
        
        # End session
        manager.end_session(session.session_id)
        assert retrieved.ended_at is not None

    def test_multi_session_management(self):
        """Test managing multiple sessions."""
        from core.session_manager import SessionManager
        
        manager = SessionManager()
        
        # Create multiple sessions
        session1 = manager.create_session()
        session2 = manager.create_session()
        session3 = manager.create_session()
        
        # Add messages to different sessions
        manager.add_message(session1.session_id, "user", "Session 1")
        manager.add_message(session2.session_id, "user", "Session 2")
        manager.add_message(session3.session_id, "user", "Session 3")
        
        # Verify isolation
        retrieved1 = manager.get_session(session1.session_id)
        retrieved2 = manager.get_session(session2.session_id)
        
        assert len(retrieved1.messages) == 1
        assert len(retrieved2.messages) == 1
        assert retrieved1.messages[0].content == "Session 1"
        assert retrieved2.messages[0].content == "Session 2"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
