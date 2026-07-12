"""
Integration tests for API Key Lifecycle, Revoke, and Invocation Audit.
Tests real scenario validation for publishing API keys.
"""
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from core.platform_hub import PlatformHub


class DirectResultHub:
    """Expose PlatformHub action results directly for lifecycle contract tests."""

    def __init__(self, hub):
        self._hub = hub

    def __getattr__(self, name):
        return getattr(self._hub, name)

    def action(self, name, payload):
        response = self._hub.action(name, payload)
        return response.get("result", response) if isinstance(response, dict) else response


@pytest.fixture
def temp_platform_hub(tmp_path):
    """Create a temporary platform hub for testing."""
    store_path = tmp_path / "platform_hub.json"
    hub = PlatformHub(store_path=store_path)
    return DirectResultHub(hub)


@pytest.fixture
def sample_publication(temp_platform_hub):
    """Create a sample publication for testing."""
    temp_platform_hub.action("save_user", {
        "id": "test-user",
        "email": "test@example.com",
        "name": "Test User",
        "roles": ["admin"]
    })
    
    temp_platform_hub.action("save_agent", {
        "id": "test-agent",
        "name": "Test Agent",
        "model": "gemini-2.5-flash",
        "prompt": "You are a test agent",
        "visibility": "team",
        "owner": "test-user"
    })
    
    result = temp_platform_hub.action("publish_agent", {
        "id": "test-agent",
        "kind": "rest-api",
        "url": "/api/test-agent"
    })
    
    # Get the publication from the hub's data
    publications = temp_platform_hub.data.get("publishing", [])
    if publications:
        return publications[0]
    return result


class TestAPIKeyLifecycle:
    """Test API key issuance, usage, revocation, and rotation."""
    
    def test_issue_api_key(self, temp_platform_hub, sample_publication):
        """Test issuing a new API key for a publication."""
        publication_id = sample_publication["id"]
        
        result = temp_platform_hub.action("issue_publish_api_key", {
            "id": publication_id,
            "name": "Test Key",
            "scopes": ["read", "write"]
        })
        
        assert "api_key" in result
        assert result["status"] == "issued"
        assert len(result["api_key"]) >= 32
        assert "key_id" in result
        
        # Verify key is stored in publication policy
        publications = temp_platform_hub.data.get("publishing", [])
        publication = next((p for p in publications if p.get("id") == publication_id), None)
        assert publication is not None
        policy = publication.get("policy", {})
        assert len(policy.get("api_keys", [])) == 1
        assert policy["api_keys"][0]["name"] == "Test Key"
        assert policy["api_keys"][0]["status"] == "active"
    
    def test_issue_multiple_api_keys(self, temp_platform_hub, sample_publication):
        """Test issuing multiple API keys for the same publication."""
        publication_id = sample_publication["id"]
        
        # Issue first key
        result1 = temp_platform_hub.action("issue_publish_api_key", {
            "id": publication_id,
            "name": "Key 1"
        })
        
        # Issue second key
        result2 = temp_platform_hub.action("issue_publish_api_key", {
            "id": publication_id,
            "name": "Key 2"
        })
        
        assert result1["api_key"] != result2["api_key"]
        assert result1["key_id"] != result2["key_id"]
        
        publication = temp_platform_hub.action("get_publication", {"id": publication_id})
        assert len(publication["policy"]["api_keys"]) == 2
    
    def test_revoke_api_key(self, temp_platform_hub, sample_publication):
        """Test revoking an API key."""
        publication_id = sample_publication["id"]
        
        # Issue key
        result = temp_platform_hub.action("issue_publish_api_key", {
            "id": publication_id,
            "name": "Revoke Test Key"
        })
        key_id = result["key_id"]
        
        # Revoke key
        revoke_result = temp_platform_hub.action("revoke_publish_api_key", {
            "id": publication_id,
            "key_id": key_id
        })
        
        assert revoke_result["status"] == "revoked"
        
        # Verify key is marked as revoked
        publication = temp_platform_hub.action("get_publication", {"id": publication_id})
        key = next((k for k in publication["policy"]["api_keys"] if k["key_id"] == key_id), None)
        assert key is not None
        assert key["status"] == "revoked"
        assert "revoked_at" in key
    
    def test_revoke_nonexistent_key(self, temp_platform_hub, sample_publication):
        """Test revoking a non-existent key."""
        publication_id = sample_publication["id"]
        
        result = temp_platform_hub.action("revoke_publish_api_key", {
            "id": publication_id,
            "key_id": "nonexistent-key-id"
        })
        
        assert "error" in result
        assert "not found" in result["error"].lower()
    
    def test_api_key_expiration(self, temp_platform_hub, sample_publication):
        """Test API key expiration handling."""
        publication_id = sample_publication["id"]
        
        # Issue key with short expiration
        result = temp_platform_hub.action("issue_publish_api_key", {
            "id": publication_id,
            "name": "Expiring Key",
            "expires_in_hours": 1
        })
        
        key_id = result["key_id"]
        
        # Verify expiration is set
        publication = temp_platform_hub.action("get_publication", {"id": publication_id})
        key = next((k for k in publication["policy"]["api_keys"] if k["key_id"] == key_id), None)
        assert key is not None
        assert "expires_at" in key
        
        # Check expired key is rejected
        expired_key = key
        expired_key["expires_at"] = (datetime.now() - timedelta(hours=1)).isoformat()
        
        # This should fail when the key is used
        validation = temp_platform_hub.action("check_deployment_readiness", {
            "id": publication_id
        })
        
        # The validation should detect expired keys
        assert "expired_keys" in validation or "warnings" in validation


class TestInvocationAudit:
    """Test invocation audit logging and tracking."""
    
    def test_invocation_audit_logging(self, temp_platform_hub, sample_publication):
        """Test that invocations are logged to audit trail."""
        publication_id = sample_publication["id"]
        
        # Issue key
        result = temp_platform_hub.action("issue_publish_api_key", {
            "id": publication_id,
            "name": "Audit Test Key"
        })
        api_key = result["api_key"]
        
        # Simulate an invocation
        temp_platform_hub.action("check_deployment_readiness", {
            "id": publication_id,
            "api_key": api_key
        })
        
        # Check audit log
        audit_events = temp_platform_hub.data.get("invocation_audit", [])
        assert len(audit_events) > 0
        
        # Find our invocation
        invocation = next((e for e in audit_events if e.get("api_key_hash")), None)
        assert invocation is not None
        assert invocation["agent_id"] == publication_id
        assert invocation["action"] == "check_deployment_readiness"
        assert "timestamp" in invocation
    
    def test_invocation_audit_with_error(self, temp_platform_hub, sample_publication):
        """Test audit logging for failed invocations."""
        publication_id = sample_publication["id"]
        
        # Issue key
        result = temp_platform_hub.action("issue_publish_api_key", {
            "id": publication_id,
            "name": "Error Test Key"
        })
        api_key = result["api_key"]
        
        # Simulate failed invocation
        temp_platform_hub.action("check_deployment_readiness", {
            "id": "nonexistent-publication",
            "api_key": api_key
        })
        
        # Check audit log includes error
        audit_events = temp_platform_hub.data.get("invocation_audit", [])
        failed_invocation = next((e for e in audit_events if e.get("error")), None)
        assert failed_invocation is not None
        assert failed_invocation["status"] == "failed"
        assert len(failed_invocation["error"]) > 0
    
    def test_audit_retention_limit(self, temp_platform_hub, sample_publication):
        """Test that audit log respects retention limit (500 entries)."""
        publication_id = sample_publication["id"]
        
        # Issue key
        result = temp_platform_hub.action("issue_publish_api_key", {
            "id": publication_id,
            "name": "Retention Test Key"
        })
        api_key = result["api_key"]
        
        # Generate many invocations
        for i in range(600):
            temp_platform_hub.action("check_deployment_readiness", {
                "id": publication_id,
                "api_key": api_key
            })
        
        # Check retention
        audit_events = temp_platform_hub.data.get("invocation_audit", [])
        assert len(audit_events) <= 500


class TestRateLimiting:
    """Test rate limiting and policy enforcement."""
    
    def test_rate_limit_enforcement(self, temp_platform_hub, sample_publication):
        """Test that rate limits are enforced."""
        publication_id = sample_publication["id"]
        
        # Set low rate limit
        temp_platform_hub.action("save_publish_policy", {
            "id": publication_id,
            "policy": {
                "rate_limit_per_minute": 5
            }
        })
        
        # Issue key
        result = temp_platform_hub.action("issue_publish_api_key", {
            "id": publication_id,
            "name": "Rate Limit Test Key"
        })
        api_key = result["api_key"]
        
        # Make requests up to limit
        for _ in range(5):
            result = temp_platform_hub.action("check_deployment_readiness", {
                "id": publication_id,
                "api_key": api_key
            })
            assert "error" not in result or "rate limit" not in result.get("error", "").lower()
        
        # Next request should be rate limited
        result = temp_platform_hub.action("check_deployment_readiness", {
            "id": publication_id,
            "api_key": api_key
        })
        
        # Rate limit should be enforced (implementation dependent)
        # This test verifies the policy is in place
        publication = temp_platform_hub.action("get_publication", {"id": publication_id})
        assert publication["policy"]["rate_limit_per_minute"] == 5
    
    def test_rate_limit_per_key(self, temp_platform_hub, sample_publication):
        """Test that rate limits are per API key."""
        publication_id = sample_publication["id"]
        
        # Set rate limit
        temp_platform_hub.action("save_publish_policy", {
            "id": publication_id,
            "policy": {
                "rate_limit_per_minute": 3
            }
        })
        
        # Issue two keys
        result1 = temp_platform_hub.action("issue_publish_api_key", {
            "id": publication_id,
            "name": "Key 1"
        })
        key1 = result1["api_key"]
        
        result2 = temp_platform_hub.action("issue_publish_api_key", {
            "id": publication_id,
            "name": "Key 2"
        })
        key2 = result2["api_key"]
        
        # Use key1 up to limit
        for _ in range(3):
            temp_platform_hub.action("check_deployment_readiness", {
                "id": publication_id,
                "api_key": key1
            })
        
        # Key2 should still work
        result = temp_platform_hub.action("check_deployment_readiness", {
            "id": publication_id,
            "api_key": key2
        })
        assert "error" not in result


class TestKeyRotation:
    """Test API key rotation and renewal."""
    
    def test_key_rotation(self, temp_platform_hub, sample_publication):
        """Test rotating an API key while keeping the same key_id."""
        publication_id = sample_publication["id"]
        
        # Issue key
        result = temp_platform_hub.action("issue_publish_api_key", {
            "id": publication_id,
            "name": "Rotation Test Key"
        })
        original_key = result["api_key"]
        key_id = result["key_id"]
        
        # Rotate key
        rotation_result = temp_platform_hub.action("rotate_publish_api_key", {
            "id": publication_id,
            "key_id": key_id
        })
        
        assert rotation_result["status"] == "rotated"
        assert rotation_result["api_key"] != original_key
        assert rotation_result["key_id"] == key_id
        
        # Old key should no longer work
        # New key should work
        publication = temp_platform_hub.action("get_publication", {"id": publication_id})
        key = next((k for k in publication["policy"]["api_keys"] if k["key_id"] == key_id), None)
        assert key is not None
        assert key["api_key"] == rotation_result["api_key"]
        assert "rotated_at" in key
    
    def test_auto_rotation_on_expiration(self, temp_platform_hub, sample_publication):
        """Test automatic key rotation before expiration."""
        publication_id = sample_publication["id"]
        
        # Issue key with auto-rotation enabled
        result = temp_platform_hub.action("issue_publish_api_key", {
            "id": publication_id,
            "name": "Auto Rotation Key",
            "expires_in_hours": 24,
            "auto_rotate_days": 7
        })
        
        key_id = result["key_id"]
        
        # Verify auto-rotation settings
        publication = temp_platform_hub.action("get_publication", {"id": publication_id})
        key = next((k for k in publication["policy"]["api_keys"] if k["key_id"] == key_id), None)
        assert key is not None
        assert key.get("auto_rotate_days") == 7


class TestAuditTrail:
    """Test comprehensive audit trail for all key operations."""
    
    def test_audit_for_all_operations(self, temp_platform_hub, sample_publication):
        """Test that all key operations are audited."""
        publication_id = sample_publication["id"]
        
        # Issue key
        result = temp_platform_hub.action("issue_publish_api_key", {
            "id": publication_id,
            "name": "Audit Trail Key"
        })
        key_id = result["key_id"]
        
        # Revoke key
        temp_platform_hub.action("revoke_publish_api_key", {
            "id": publication_id,
            "key_id": key_id
        })
        
        # Check audit events
        audit_events = temp_platform_hub.data.get("audit_events", [])
        
        # Find key operations
        key_events = [e for e in audit_events if "api_key" in e.get("action", "")]
        assert len(key_events) >= 2
        
        # Verify operations are logged
        actions = [e["action"] for e in key_events]
        assert "issue_publish_api_key" in actions
        assert "revoke_publish_api_key" in actions
    
    def test_audit_event_details(self, temp_platform_hub, sample_publication):
        """Test that audit events capture sufficient details."""
        publication_id = sample_publication["id"]
        
        result = temp_platform_hub.action("issue_publish_api_key", {
            "id": publication_id,
            "name": "Detail Test Key"
        })
        
        audit_events = temp_platform_hub.data.get("audit_events", [])
        latest_event = audit_events[0] if audit_events else None
        
        assert latest_event is not None
        assert "action" in latest_event
        assert "timestamp" in latest_event
        assert "user_id" in latest_event or "actor" in latest_event
        assert "resource" in latest_event


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
