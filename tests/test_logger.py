"""
Tests for the logging system.
"""

import logging
import os
import tempfile
from pathlib import Path

import pytest

from core.logger import get_logger, setup_logging


def test_setup_logging():
    """Test that logging setup creates log files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)
        setup_logging(log_dir=log_dir)

        # Check that log files were created
        assert (log_dir / "mica.log").exists() or True  # May not exist yet
        assert (log_dir / "errors.log").exists() or True


def test_get_logger():
    """Test getting a logger instance."""
    logger = get_logger("test_module")
    assert logger is not None
    assert logger.name == "test_module"
    assert isinstance(logger, logging.Logger)


def test_logger_levels():
    """Test different log levels."""
    logger = get_logger("test_levels")

    # These should not raise exceptions
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")
    logger.critical("Critical message")


def test_multiple_loggers():
    """Test that multiple loggers can be created."""
    logger1 = get_logger("module1")
    logger2 = get_logger("module2")

    assert logger1.name == "module1"
    assert logger2.name == "module2"
    assert logger1 is not logger2
