"""
Integration tests for session management system
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta


class TestSessionIntegration:
    """Integration tests for session management system components."""

    @pytest.fixture
    def session_manager(self):
        """Create a fresh SessionManager instance for testing."""
        from core.session_manager import SessionManager
        return SessionManager()

    def test_session_lifecycle(self, session_manager):
        """Test complete session lifecycle."""
        # Create session
        session = session_manager.create_session()
        session_id = session.session_id
        
        # Add messages
        session_manager.add_message(session_id, "user", "Hello M.I.C.A")
        session_manager.add_message(session_id, "assistant", "Hi there!")
        
        # Get session
        retrieved = session_manager.get_session(session_id)
        
        # End session
        session_manager.end_session(session_id)
        
        assert session_id is not None
        assert len(retrieved.messages) == 2
        assert retrieved.ended_at is not None

    def test_multi_user_sessions(self, session_manager):
        """Test managing multiple user sessions."""
        # Create sessions for different users
        user1_session = session_manager.create_session(user_id="user1")
        user2_session = session_manager.create_session(user_id="user2")
        
        # Add messages to each
        session_manager.add_message(user1_session.session_id, "user1", "Hello from user 1")
        session_manager.add_message(user2_session.session_id, "user2", "Hello from user 2")
        
        # Verify isolation
        retrieved1 = session_manager.get_session(user1_session.session_id)
        retrieved2 = session_manager.get_session(user2_session.session_id)
        
        assert retrieved1.messages[0].content == "Hello from user 1"
        assert retrieved2.messages[0].content == "Hello from user 2"

    def test_session_persistence(self, session_manager):
        """Test session persistence across restarts."""
        # Create session
        session = session_manager.create_session()
        session_manager.add_message(session.session_id, "user", "Test message")
        
        # Save sessions
        session_manager.save_sessions()
        
        # Load sessions
        session_manager.load_sessions()
        
        # Verify persistence
        retrieved = session_manager.get_session(session.session_id)
        assert len(retrieved.messages) > 0

    def test_session_timeout(self, session_manager):
        """Test session timeout handling."""
        session_manager.session_timeout_minutes = 30
        
        # Create old session
        old_session = session_manager.create_session()
        old_session.created_at = datetime.now() - timedelta(minutes=40)
        
        # Create new session
        new_session = session_manager.create_session()
        
        # Cleanup old sessions
        session_manager.cleanup_old_sessions(max_age_minutes=30)
        
        # Old session should be removed
        assert old_session.session_id not in session_manager.sessions
        assert new_session.session_id in session_manager.sessions

    def test_session_with_memory(self, session_manager):
        """Test session integration with memory system."""
        from memory.memory_manager import MemoryManager
        
        memory = MemoryManager()
        
        # Create session
        session = session_manager.create_session()
        session_manager.add_message(session.session_id, "user", "Remember this")
        
        # Store in memory
        session_data = session_manager.get_session(session.session_id)
        memory.update_memory("session_memory", session_data.to_dict())
        
        # Retrieve from memory
        retrieved = memory.load_memory("session_memory")
        
        assert retrieved is not None

    def test_session_statistics(self, session_manager):
        """Test session statistics calculation."""
        # Create multiple sessions
        for i in range(5):
            session = session_manager.create_session()
            session_manager.add_message(session.session_id, "user", f"Message {i}")
        
        # Get statistics
        stats = session_manager.get_statistics()
        
        assert stats is not None
        assert stats['total_sessions'] >= 5
        assert stats['total_messages'] >= 5

    def test_session_search(self, session_manager):
        """Test searching within sessions."""
        # Create session with messages
        session = session_manager.create_session()
        session_manager.add_message(session.session_id, "user", "Python programming")
        session_manager.add_message(session.session_id, "assistant", "Python is great")
        session_manager.add_message(session.session_id, "user", "JavaScript too")
        
        # Search for "Python"
        results = session_manager.search_sessions("Python")
        
        assert results is not None
        assert len(results) > 0

    def test_session_export_import(self, session_manager):
        """Test exporting and importing sessions."""
        # Create session
        session = session_manager.create_session()
        session_manager.add_message(session.session_id, "user", "Test message")
        
        # Export session
        exported = session_manager.export_session(session.session_id)
        
        # Import session
        imported_id = session_manager.import_session(exported)
        
        # Verify import
        imported = session_manager.get_session(imported_id)
        assert imported is not None
        assert len(imported.messages) == 1


class TestSessionErrorHandling:
    """Error handling tests for session management."""

    @pytest.fixture
    def session_manager(self):
        """Create a fresh SessionManager instance for testing."""
        from core.session_manager import SessionManager
        return SessionManager()

    def test_invalid_session_id(self, session_manager):
        """Test handling of invalid session ID."""
        result = session_manager.get_session("invalid_id")
        assert result is None

    def test_add_message_to_invalid_session(self, session_manager):
        """Test adding message to invalid session."""
        result = session_manager.add_message("invalid_id", "user", "Test")
        assert result is False

    def test_corrupted_session_data(self, session_manager):
        """Test handling of corrupted session data."""
        # Try to import invalid data
        with pytest.raises(Exception):
            session_manager.import_session({"invalid": "data"})


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
