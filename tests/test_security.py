"""
Tests for the security module.
"""

import tempfile
from pathlib import Path

import pytest

from core.approval_flow import get_approval_flow
from core.security import (
    CodeSandbox,
    InputValidator,
    RateLimiter,
    SecureFileOperations,
    get_api_key_manager,
    get_rate_limiter,
)


def test_input_validator_text():
    """Test text input validation."""
    validator = InputValidator()

    # Valid input
    is_valid, error = validator.validate_text("Hello, world!")
    assert is_valid is True
    assert error is None

    # Input too long
    long_text = "a" * 20000
    is_valid, error = validator.validate_text(long_text)
    assert is_valid is False
    assert "too long" in error.lower()


def test_input_validator_dangerous_patterns():
    """Test detection of dangerous patterns."""
    validator = InputValidator()

    # Script tag
    is_valid, error = validator.validate_text("<script>alert('xss')</script>")
    assert is_valid is False
    assert "dangerous" in error.lower()

    # JavaScript protocol
    is_valid, error = validator.validate_text("javascript:alert('xss')")
    assert is_valid is False


def test_input_validator_file_path():
    """Test file path validation."""
    validator = InputValidator()

    # Valid path
    is_valid, error = validator.validate_file_path("/tmp/test.txt")
    assert is_valid is True

    # Path traversal
    is_valid, error = validator.validate_file_path("../../../etc/passwd")
    assert is_valid is False
    assert "traversal" in error.lower()


def test_input_validator_command():
    """Test command validation."""
    validator = InputValidator()

    # Safe command
    is_valid, error = validator.validate_command("ls -la")
    assert is_valid is True

    # Dangerous command with shell metacharacter
    is_valid, error = validator.validate_command("ls; rm -rf /")
    assert is_valid is False


def test_rate_limiter():
    """Test rate limiting."""
    limiter = RateLimiter(max_requests=5, window_seconds=60)

    # First 5 requests should be allowed
    for i in range(5):
        is_allowed, retry_after = limiter.is_allowed("test_user")
        assert is_allowed is True
        assert retry_after is None

    # 6th request should be rate limited
    is_allowed, retry_after = limiter.is_allowed("test_user")
    assert is_allowed is False
    assert retry_after is not None


def test_rate_limiter_reset():
    """Test rate limiter reset."""
    limiter = RateLimiter(max_requests=3, window_seconds=60)

    # Use up limit
    for i in range(3):
        limiter.is_allowed("test_user")

    # Should be rate limited
    is_allowed, _ = limiter.is_allowed("test_user")
    assert is_allowed is False

    # Reset
    limiter.reset("test_user")

    # Should be allowed again
    is_allowed, _ = limiter.is_allowed("test_user")
    assert is_allowed is True


def test_code_sandbox_validation():
    """Test code sandbox validation."""
    sandbox = CodeSandbox()

    # Safe code
    safe_code = "x = 1 + 1\nprint(x)"
    is_safe, error = sandbox.validate_code(safe_code)
    assert is_safe is True

    # Dangerous code with eval
    dangerous_code = "eval('print(1)')"
    is_safe, error = sandbox.validate_code(dangerous_code)
    assert is_safe is False
    assert "dangerous" in error.lower()


def test_code_sandbox_execution():
    """Test safe code execution."""
    sandbox = CodeSandbox()

    safe_code = "result = 2 + 2"
    success, result, error = sandbox.execute_safe_code(safe_code)
    assert success is True


def test_global_rate_limiter():
    """Test global rate limiter instance."""
    limiter1 = get_rate_limiter()
    limiter2 = get_rate_limiter()
    assert limiter1 is limiter2


def test_secure_file_operations():
    """Test secure file operations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        secure_ops = SecureFileOperations(allowed_base_dirs=[base_dir])

        # Safe write
        success, error = secure_ops.safe_write(str(base_dir / "test.txt"), "test content")
        assert success is True

        # Safe read
        success, content, error = secure_ops.safe_read(str(base_dir / "test.txt"))
        assert success is True
        assert content == "test content"

        # Path outside allowed directory
        success, error = secure_ops.safe_write("/etc/passwd", "test")
        assert success is False


def test_approval_flow_integration():
    """Test that approval flow integrates with security."""
    approval_flow = get_approval_flow()

    # Test that approval flow is available
    assert approval_flow is not None

    # Test permission level
    current_level = approval_flow.get_permission_level()
    assert current_level in ["safe", "normal", "admin"]

    # Test that we can check actions
    is_allowed, message = approval_flow.check_and_request_approval(
        tool_name="file_controller", action="list", parameters={"path": "/tmp"}
    )
    # List should be allowed in normal mode
    assert is_allowed is True
