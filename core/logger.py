"""
Centralized logging configuration for JARVIS AI Assistant.

This module provides a unified logging system with:
- Console and file handlers
- Rotating log files to prevent disk overflow
- Structured log format with timestamps and levels
- Module-specific loggers for different components
- Optional async logging with queue handler
"""

import logging
import queue
import sys
import threading
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from pathlib import Path
from typing import Optional

from core.metrics_collector import get_metrics_collector
from core.paths import project_path
from core.performance_flags import get_performance_flags


def setup_logging(
    log_level: str = "INFO",
    log_dir: Optional[Path] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
) -> None:
    """
    Configure the logging system for JARVIS.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files (defaults to ./logs)
        max_bytes: Maximum size of each log file before rotation
        backup_count: Number of backup log files to keep
    """
    if log_dir is None:
        log_dir = project_path("logs")

    log_dir.mkdir(parents=True, exist_ok=True)

    # Convert log level string to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Clear any existing handlers and close them so temporary log files can be removed.
    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        try:
            handler.flush()
        except Exception:
            pass
        try:
            handler.close()
        except Exception:
            pass
        root_logger.removeHandler(handler)
    root_logger.setLevel(numeric_level)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)

    # File handler for general logs
    general_log = log_dir / "jarvis.log"
    file_handler = RotatingFileHandler(
        general_log,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
        delay=True,
    )
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)

    # Separate error log
    error_log = log_dir / "errors.log"
    error_handler = RotatingFileHandler(
        error_log,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
        delay=True,
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    # Check if async logging is enabled
    perf_flags = get_performance_flags()
    metrics = get_metrics_collector()

    if perf_flags.is_enabled("async_logging"):
        # Use QueueHandler for async logging
        log_queue = queue.Queue(-1)  # Unlimited size queue
        queue_handler = QueueHandler(log_queue)

        # Create QueueListener with background thread
        queue_listener = QueueListener(
            log_queue, console_handler, file_handler, error_handler, respect_handler_level=True
        )
        queue_listener.start()

        # Add queue handler to root logger instead of direct handlers
        root_logger.addHandler(queue_handler)

        metrics.start_operation("async_logging_setup")
        metrics.end_operation("async_logging_setup", {"enabled": True})
        print("[Logger] Async logging enabled with QueueHandler")
    else:
        # Original synchronous logging
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(error_handler)

    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.

    Args:
        name: Name of the module (typically __name__)

    Returns:
        Logger instance configured for the module
    """
    return logging.getLogger(name)


# Initialize logging on module import
setup_logging()
