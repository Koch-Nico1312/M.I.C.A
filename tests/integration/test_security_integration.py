"""
Integration tests for security system
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile


class TestSecurityIntegration:
    """Integration tests for security system components."""

    @pytest.fixture
    def security(self):
        """Create a fresh Security instance for testing."""
        from core.security import Security
        return Security()

    def test_api_key_encryption(self, security):
        """Test API key encryption and decryption."""
        api_key = "test_api_key_12345"
        
        # Encrypt
        encrypted = security.encrypt_api_key(api_key)
        
        # Decrypt
        decrypted = security.decrypt_api_key(encrypted)
        
        assert decrypted == api_key
        assert encrypted != api_key

    def test_permission_checking(self):
        """Test permission checking system."""
        from core.permission_profiles import PermissionLevel, get_permission_profiles
        
        profiles = get_permission_profiles()
        
        # Check safe action
        allowed, reason = profiles.check_action("safe_action", PermissionLevel.SAFE.value)
        assert allowed is True
        
        # Check admin action with safe user
        allowed, reason = profiles.check_action("admin_action", PermissionLevel.SAFE.value)
        assert allowed is False

    def test_approval_flow_integration(self):
        """Test approval flow integration."""
        from core.approval_flow import get_approval_flow
        from core.permission_profiles import PermissionLevel
        
        approval = get_approval_flow()
        
        # Request approval for high-risk action
        approved, message = approval.check_and_request_approval(
            action="delete_file",
            parameters={"path": "/important/file.txt"},
            risk_level="high",
            user_level=PermissionLevel.NORMAL.value
        )
        
        assert approved is not None
        assert message is not None

    def test_action_history_security(self):
        """Test action history for security auditing."""
        from core.action_history import get_action_history
        
        history = get_action_history()
        
        # Record security-relevant action
        history.record_action(
            tool_name="file_controller",
            action="delete",
            parameters={"path": "/test/file.txt"},
            result="success",
            user="test_user",
            risk_level="high"
        )
        
        # Retrieve history
        retrieved = history.get_history()
        
        assert len(retrieved) > 0

    def test_audit_logging(self):
        """Test audit logging system."""
        from core.security import Security
        
        security = Security()
        
        # Log security event
        security.log_audit_event(
            event_type="action_execution",
            action="delete_file",
            user="test_user",
            result="success",
            risk_level="high"
        )
        
        # Retrieve audit log
        logs = security.get_audit_logs()
        
        assert logs is not None

    def test_api_key_rotation(self):
        """Test API key rotation mechanism."""
        from core.security import Security
        
        security = Security()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "api_keys.json"
            
            # Store initial key
            initial_key = "initial_key_123"
            security.store_api_key("gemini", initial_key, config_path)
            
            # Rotate key
            new_key = "new_key_456"
            security.rotate_api_key("gemini", new_key, config_path)
            
            # Verify new key
            stored_key = security.get_api_key("gemini", config_path)
            
            assert stored_key == new_key

    def test_data_retention_policy(self):
        """Test data retention policy enforcement."""
        from core.security import Security
        from datetime import datetime, timedelta
        
        security = Security()
        
        # Set retention policy
        security.set_retention_policy(days=30)
        
        # Add old data
        old_date = datetime.now() - timedelta(days=40)
        security.add_data("test_data", timestamp=old_date)
        
        # Clean up expired data
        security.cleanup_expired_data()
        
        # Should have removed old data
        remaining = security.get_data()
        assert len(remaining) == 0

    def test_rbac_integration(self):
        """Test Role-Based Access Control integration."""
        from core.security import Security
        from core.permission_profiles import PermissionLevel
        
        security = Security()
        
        # Define roles
        security.define_role("admin", ["all"])
        security.define_role("user", ["read", "write"])
        security.define_role("guest", ["read"])
        
        # Check permissions
        admin_access = security.check_role_permission("admin", "delete")
        guest_access = security.check_role_permission("guest", "delete")
        
        assert admin_access is True
        assert guest_access is False


class TestSecurityErrorHandling:
    """Error handling tests for security system."""

    @pytest.fixture
    def security(self):
        """Create a fresh Security instance for testing."""
        from core.security import Security
        return Security()

    def test_invalid_api_key_decryption(self, security):
        """Test handling of invalid encrypted key."""
        invalid_encrypted = "invalid_encrypted_string"
        
        with pytest.raises(Exception):
            security.decrypt_api_key(invalid_encrypted)

    def test_permission_denied_handling(self):
        """Test handling of permission denied scenarios."""
        from core.permission_profiles import PermissionLevel, get_permission_profiles
        
        profiles = get_permission_profiles()
        
        # Try admin action with safe user
        allowed, reason = profiles.check_action("admin_action", PermissionLevel.SAFE.value)
        
        assert allowed is False
        assert reason is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
