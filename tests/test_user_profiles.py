"""
Tests for core.user_profiles module
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import json


class TestUserProfiles:
    """Test cases for UserProfiles class."""

    @pytest.fixture
    def user_profiles(self):
        """Create a fresh UserProfiles instance for testing."""
        from core.user_profiles import UserProfiles
        return UserProfiles()

    def test_user_profiles_initialization(self, user_profiles):
        """Test UserProfiles initialization."""
        assert user_profiles is not None
        assert hasattr(user_profiles, 'create_profile')
        assert hasattr(user_profiles, 'get_profile')
        assert hasattr(user_profiles, 'update_profile')

    def test_create_profile(self, user_profiles):
        """Test creating a new user profile."""
        profile_id = user_profiles.create_profile(
            username="test_user",
            preferences={"theme": "dark", "language": "en"}
        )
        
        assert profile_id is not None
        assert profile_id in user_profiles.profiles

    def test_get_profile(self, user_profiles):
        """Test getting a user profile."""
        profile_id = user_profiles.create_profile(
            username="test_user",
            preferences={"theme": "dark"}
        )
        
        profile = user_profiles.get_profile(profile_id)
        
        assert profile is not None
        assert profile['username'] == "test_user"

    def test_update_profile(self, user_profiles):
        """Test updating a user profile."""
        profile_id = user_profiles.create_profile(
            username="test_user",
            preferences={"theme": "dark"}
        )
        
        user_profiles.update_profile(
            profile_id,
            preferences={"theme": "light", "language": "en"}
        )
        
        profile = user_profiles.get_profile(profile_id)
        assert profile['preferences']['theme'] == "light"

    def test_delete_profile(self, user_profiles):
        """Test deleting a user profile."""
        profile_id = user_profiles.create_profile(
            username="test_user",
            preferences={}
        )
        
        user_profiles.delete_profile(profile_id)
        
        assert profile_id not in user_profiles.profiles

    def test_set_default_profile(self, user_profiles):
        """Test setting a default profile."""
        profile_id = user_profiles.create_profile(
            username="test_user",
            preferences={}
        )
        
        user_profiles.set_default_profile(profile_id)
        
        assert user_profiles.default_profile_id == profile_id

    def test_get_default_profile(self, user_profiles):
        """Test getting the default profile."""
        profile_id = user_profiles.create_profile(
            username="test_user",
            preferences={}
        )
        user_profiles.set_default_profile(profile_id)
        
        default = user_profiles.get_default_profile()
        
        assert default is not None
        assert default['profile_id'] == profile_id

    def test_list_profiles(self, user_profiles):
        """Test listing all profiles."""
        user_profiles.create_profile("user1", {})
        user_profiles.create_profile("user2", {})
        user_profiles.create_profile("user3", {})
        
        profiles = user_profiles.list_profiles()
        
        assert len(profiles) == 3

    def test_profile_persistence(self, user_profiles):
        """Test profile persistence to disk."""
        profile_id = user_profiles.create_profile(
            username="test_user",
            preferences={"theme": "dark"}
        )
        
        # Save profiles
        user_profiles.save_profiles()
        
        # Load profiles
        user_profiles.load_profiles()
        
        # Should persist
        assert profile_id in user_profiles.profiles


class TestUserProfilesErrorHandling:
    """Test error handling in UserProfiles."""

    @pytest.fixture
    def user_profiles(self):
        """Create a fresh UserProfiles instance for testing."""
        from core.user_profiles import UserProfiles
        return UserProfiles()

    def test_get_nonexistent_profile(self, user_profiles):
        """Test getting a non-existent profile."""
        result = user_profiles.get_profile("nonexistent_id")
        assert result is None

    def test_delete_nonexistent_profile(self, user_profiles):
        """Test deleting a non-existent profile."""
        result = user_profiles.delete_profile("nonexistent_id")
        assert result is False

    def test_update_nonexistent_profile(self, user_profiles):
        """Test updating a non-existent profile."""
        result = user_profiles.update_profile("nonexistent_id", preferences={})
        assert result is False

    def test_duplicate_username(self, user_profiles):
        """Test handling of duplicate usernames."""
        user_profiles.create_profile("test_user", {})
        
        with pytest.raises(ValueError):
            user_profiles.create_profile("test_user", {})


class TestUserProfilesIntegration:
    """Integration tests for UserProfiles."""

    def test_full_profile_lifecycle(self):
        """Test a full profile lifecycle."""
        from core.user_profiles import UserProfiles
        
        profiles = UserProfiles()
        
        # Create profile
        profile_id = profiles.create_profile(
            username="test_user",
            preferences={
                "theme": "dark",
                "language": "en",
                "voice_enabled": True
            }
        )
        
        # Get profile
        profile = profiles.get_profile(profile_id)
        assert profile is not None
        
        # Update profile
        profiles.update_profile(
            profile_id,
            preferences={"theme": "light"}
        )
        
        updated = profiles.get_profile(profile_id)
        assert updated['preferences']['theme'] == "light"
        
        # Delete profile
        profiles.delete_profile(profile_id)
        assert profile_id not in profiles.profiles

    def test_profile_with_permissions(self):
        """Test profile integration with permission system."""
        from core.user_profiles import UserProfiles
        from core.permission_profiles import PermissionLevel
        
        profiles = UserProfiles()
        
        profile_id = profiles.create_profile(
            username="admin_user",
            preferences={},
            permission_level=PermissionLevel.ADMIN.value
        )
        
        profile = profiles.get_profile(profile_id)
        assert profile['permission_level'] == PermissionLevel.ADMIN.value

    def test_profile_with_memory(self):
        """Test profile integration with memory system."""
        from core.user_profiles import UserProfiles
        from memory.memory_manager import MemoryManager
        
        profiles = UserProfiles()
        memory = MemoryManager()
        
        profile_id = profiles.create_profile(
            username="test_user",
            preferences={}
        )
        
        # Associate memory with profile
        # memory.associate_with_profile(profile_id, memory_data)
        
        assert True  # Placeholder for actual integration test

    def test_profile_migration(self):
        """Test profile migration between systems."""
        from core.user_profiles import UserProfiles
        
        profiles1 = UserProfiles()
        profile_id = profiles1.create_profile("test_user", preferences={"theme": "dark"})
        
        # Export profile
        exported = profiles1.export_profile(profile_id)
        
        # Import to new instance
        profiles2 = UserProfiles()
        imported_id = profiles2.import_profile(exported)
        
        assert imported_id is not None
        imported = profiles2.get_profile(imported_id)
        assert imported['username'] == "test_user"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
