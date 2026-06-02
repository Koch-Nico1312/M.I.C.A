"""
Performance system initializer for JARVIS AI Assistant.

This module handles initialization of performance tracking, monitoring,
and background task management.

Example:
    >>> from startup.performance_initializer import initialize_performance_system
    >>> 
    >>> # Initialize performance system
    >>> def get_action_loader():
    ...     return action_loader_instance
    >>> 
    >>> perf_tracker, perf_monitor = initialize_performance_system(get_action_loader)
    >>> 
    >>> # Performance tracking is now active
    >>> perf_tracker.start_operation("test_operation")
    >>> # ... do work ...
    >>> perf_tracker.end_operation("test_operation")
"""

from config.config_loader import get_config
from core.action_loader import get_action_loader
from core.background_task_manager import get_background_task_manager
from core.logger import get_logger
from core.memory_manager import get_memory_manager
from core.performance_monitor import get_performance_monitor
from core.performance_tracker import get_performance_tracker

logger = get_logger(__name__)


def initialize_performance_system(action_loader_func):
    """
    Initialize the performance tracking and monitoring system.
    
    Args:
        action_loader_func: Function to get the action loader instance
        
    Returns:
        tuple: (perf_tracker, perf_monitor) or (None, None) if disabled
    """
    config = get_config()

    if not config.get("performance.enabled", True):
        logger.info("Performance tracking disabled by configuration")
        return None, None

    perf_tracker = get_performance_tracker()
    perf_monitor = get_performance_monitor()

    # Configure thresholds
    slow_threshold = config.get("performance.slow_operation_threshold_ms", 2000)
    alert_threshold = config.get("performance.alert_threshold_ms", 5000)
    perf_tracker.slow_operation_threshold_ms = slow_threshold
    perf_tracker.alert_threshold_ms = alert_threshold

    # Start resource monitoring if enabled
    if config.get("performance.resource_monitoring", True):
        resource_interval = config.get("performance.resource_interval_seconds", 60)
        perf_monitor.resource_interval_seconds = resource_interval
        perf_monitor.start_monitoring()

    # Start background task manager if enabled
    if config.get("performance.background_tasks_enabled", True):
        bg_manager = get_background_task_manager()
        bg_workers = config.get("performance.background_workers", 4)
        bg_manager.max_workers = bg_workers
        bg_manager.start()

    # Initialize action loader for lazy loading
    if config.get("performance.flags.lazy_load_actions", False):
        action_loader = action_loader_func()
        # Preload critical actions
        critical_actions = [
            "file_processor",
            "web_search",
            "computer_control",
            "gmail_manager",
            "calendar_manager",
        ]
        action_loader.preload_actions(critical_actions)

    # Initialize memory manager
    if config.get("performance.flags.reduce_memory_footprint", False):
        memory_manager = get_memory_manager()
        memory_manager.start_gc_thread()
        logger.info("Memory manager started with GC thread")

    logger.info("Performance tracking system initialized")
    return perf_tracker, perf_monitor
