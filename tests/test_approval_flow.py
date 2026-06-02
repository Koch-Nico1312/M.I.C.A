"""
Tests for the approval flow system.
"""

import time

import pytest

from core.approval_flow import ApprovalFlow, ApprovalRequest, ApprovalStatus, get_approval_flow
from core.permission_profiles import PermissionLevel


def test_approval_flow_initialization():
    """Test approval flow initialization."""
    flow = ApprovalFlow()
    assert flow.get_permission_level() == PermissionLevel.NORMAL.value
    assert len(flow.get_pending_requests()) == 0


def test_permission_level_setting():
    """Test setting permission level."""
    flow = ApprovalFlow()

    flow.set_permission_level(PermissionLevel.SAFE.value)
    assert flow.get_permission_level() == PermissionLevel.SAFE.value

    flow.set_permission_level(PermissionLevel.ADMIN.value)
    assert flow.get_permission_level() == PermissionLevel.ADMIN.value


def test_safe_mode_blocks_destructive():
    """Test that safe mode blocks destructive actions."""
    flow = ApprovalFlow()
    flow.set_permission_level(PermissionLevel.SAFE.value)

    # Test delete action (should be blocked in safe mode)
    is_allowed, message = flow.check_and_request_approval(
        tool_name="file_controller", action="delete", parameters={"path": "/tmp/test"}
    )

    assert is_allowed is False
    assert "blocked" in message.lower()


def test_normal_mode_requires_confirmation():
    """Test that normal mode requires confirmation for destructive actions."""
    flow = ApprovalFlow()
    flow.set_permission_level(PermissionLevel.NORMAL.value)

    # Test delete action without confirmation
    is_allowed, message = flow.check_and_request_approval(
        tool_name="file_controller", action="delete", parameters={"path": "/tmp/test"}
    )

    assert is_allowed is False
    assert "confirmation required" in message.lower()


def test_normal_mode_with_confirmation():
    """Test that normal mode allows with confirmation."""
    flow = ApprovalFlow()
    flow.set_permission_level(PermissionLevel.NORMAL.value)

    # Test delete action with confirmation
    is_allowed, message = flow.check_and_request_approval(
        tool_name="file_controller",
        action="delete",
        parameters={"path": "/tmp/test", "confirmed": "yes"},
    )

    assert is_allowed is True


def test_admin_mode_allows_all():
    """Test that admin mode allows all actions."""
    flow = ApprovalFlow()
    flow.set_permission_level(PermissionLevel.ADMIN.value)

    # Test delete action without confirmation
    is_allowed, message = flow.check_and_request_approval(
        tool_name="file_controller", action="delete", parameters={"path": "/tmp/test"}
    )

    assert is_allowed is True


def test_approval_request_creation():
    """Test approval request creation."""
    request = ApprovalRequest(
        tool_name="file_controller",
        action="delete",
        parameters={"path": "/tmp/test"},
        permission_level="normal",
        reason="Destructive action",
    )

    assert request.tool_name == "file_controller"
    assert request.action == "delete"
    assert request.status == ApprovalStatus.PENDING
    assert request.can_undo is False


def test_approval_request_approve():
    """Test approving a request."""
    request = ApprovalRequest(
        tool_name="file_controller",
        action="delete",
        parameters={"path": "/tmp/test"},
        permission_level="normal",
    )

    request.approve()
    assert request.status == ApprovalStatus.APPROVED
    assert request._result is True


def test_approval_request_deny():
    """Test denying a request."""
    request = ApprovalRequest(
        tool_name="file_controller",
        action="delete",
        parameters={"path": "/tmp/test"},
        permission_level="normal",
    )

    request.deny()
    assert request.status == ApprovalStatus.DENIED
    assert request._result is False


def test_approval_request_timeout():
    """Test request timeout."""
    request = ApprovalRequest(
        tool_name="file_controller",
        action="delete",
        parameters={"path": "/tmp/test"},
        permission_level="normal",
    )

    # Wait with short timeout
    result = request.wait_for_decision(timeout=0.1)
    assert result is None
    assert request.status == ApprovalStatus.TIMEOUT


def test_global_approval_flow_instance():
    """Test global approval flow instance."""
    flow1 = get_approval_flow()
    flow2 = get_approval_flow()
    assert flow1 is flow2


def test_safe_mode_blocks_file_modifications():
    """Test that safe mode blocks file modifications."""
    flow = ApprovalFlow()
    flow.set_permission_level(PermissionLevel.SAFE.value)

    # Test various file modification actions
    for action in ["create_file", "write", "move", "copy", "rename"]:
        is_allowed, message = flow.check_and_request_approval(
            tool_name="file_controller", action=action, parameters={"path": "/tmp/test"}
        )
        assert is_allowed is False
        assert "blocked" in message.lower()


def test_normal_mode_allows_safe_actions():
    """Test that normal mode allows safe actions without confirmation."""
    flow = ApprovalFlow()
    flow.set_permission_level(PermissionLevel.NORMAL.value)

    # Test safe action (list)
    is_allowed, message = flow.check_and_request_approval(
        tool_name="file_controller", action="list", parameters={"path": "/tmp"}
    )

    assert is_allowed is True
