"""
Tests for the extended healthcheck functionality.
"""

from pathlib import Path

import pytest

from core.healthcheck import (
    _audio_status,
    _feature_status,
    _integration_status,
    _memory_status,
    build_runtime_report,
    format_runtime_report,
)


def test_audio_status():
    """Test audio status check."""
    status = _audio_status()

    assert "sounddevice_available" in status
    assert "input_devices" in status
    assert "output_devices" in status
    assert isinstance(status["input_devices"], int)
    assert isinstance(status["output_devices"], int)


def test_memory_status():
    """Test memory status check."""
    base_dir = Path(__file__).resolve().parent.parent
    status = _memory_status(base_dir)

    assert "memory_file_exists" in status
    assert "memory_file_size_kb" in status
    assert "backup_dir_exists" in status
    assert "backup_count" in status
    assert isinstance(status["backup_count"], int)


def test_integration_status():
    """Test integration status check."""
    base_dir = Path(__file__).resolve().parent.parent
    status = _integration_status(None, base_dir)

    assert "gmail" in status
    assert "obsidian" in status
    assert "vscode" in status
    assert "spotify" in status
    assert "mcp" in status


def test_integration_status_with_config():
    """Test integration status with config."""
    from config.config_loader import Config

    # Create a mock config
    class MockConfig:
        def get(self, key, default=None):
            if key == "gmail.enabled":
                return False
            elif key == "obsidian.enabled":
                return False
            elif key == "obsidian.vault_path":
                return ""
            elif key == "vscode.bridge_enabled":
                return False
            elif key == "vscode.port":
                return 0
            elif key == "spotify.enabled":
                return False
            elif key == "spotify.client_id":
                return ""
            return default

    base_dir = Path(__file__).resolve().parent.parent
    status = _integration_status(MockConfig(), base_dir)

    assert status["gmail"]["enabled"] is False
    assert status["vscode"]["enabled"] is False


def test_feature_status():
    """Test feature status check."""
    status = _feature_status(None)

    # Should return empty dict when config is None
    assert status == {}

    # Test with mock config
    class MockConfig:
        def get(self, key, default=None):
            if "enabled" in key:
                return False
            return default

    status = _feature_status(MockConfig())
    assert "ollama" in status
    assert "passive_vision" in status
    assert "rag" in status
    assert "hud" in status


def test_build_runtime_report_extended():
    """Test that build_runtime_report includes extended status."""
    base_dir = Path(__file__).resolve().parent.parent
    from config.config_loader import get_config

    try:
        config = get_config()
    except Exception:
        config = None

    report = build_runtime_report(base_dir, config=config)

    # Check for extended fields
    assert "audio" in report
    assert "memory" in report
    assert "integrations" in report

    # Check audio status structure
    assert "sounddevice_available" in report["audio"]

    # Check memory status structure
    assert "memory_file_exists" in report["memory"]

    # Check integration status structure
    assert "gmail" in report["integrations"]
    assert "vscode" in report["integrations"]


def test_format_runtime_report_verbose():
    """Test verbose format of runtime report."""
    base_dir = Path(__file__).resolve().parent.parent
    from config.config_loader import get_config

    try:
        config = get_config()
    except Exception:
        config = None

    report = build_runtime_report(base_dir, config=config)
    formatted = format_runtime_report(report, verbose=True)

    # Should contain extended information
    assert "Runtime ready:" in formatted
    assert "Gemini API key present:" in formatted

    # In verbose mode, should include extended sections if available
    lines = formatted.split("\n")
    assert len(lines) > 5


def test_format_runtime_report_basic():
    """Test basic format of runtime report."""
    base_dir = Path(__file__).resolve().parent.parent
    from config.config_loader import get_config

    try:
        config = get_config()
    except Exception:
        config = None

    report = build_runtime_report(base_dir, config=config)
    formatted = format_runtime_report(report, verbose=False)

    # Should contain basic information
    assert "Runtime ready:" in formatted
    assert "Gemini API key present:" in formatted
    assert "Registered tools:" in formatted


def test_memory_status_with_backups():
    """Test memory status when backups exist."""
    base_dir = Path(__file__).resolve().parent.parent
    status = _memory_status(base_dir)

    # Should not crash even if backup directory doesn't exist
    assert status["backup_count"] >= 0


def test_mcp_status():
    """Test MCP server status check."""
    base_dir = Path(__file__).resolve().parent.parent
    status = _integration_status(None, base_dir)

    # MCP status should be present
    assert "mcp" in status
    assert "config_exists" in status["mcp"]
    assert "server_count" in status["mcp"]
    assert isinstance(status["mcp"]["server_count"], int)
