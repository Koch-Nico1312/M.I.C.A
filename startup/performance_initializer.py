"""
Performance system initializer for M.I.C.A AI Assistant.

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
from config.startup_config import get_startup_setting
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

    if not get_startup_setting("performance.enabled"):
        logger.info("Performance tracking disabled by configuration")
        return None, None

    perf_tracker = get_performance_tracker()
    perf_monitor = get_performance_monitor()

    # Configure thresholds
    slow_threshold = get_startup_setting("performance.slow_operation_threshold_ms")
    alert_threshold = get_startup_setting("performance.alert_threshold_ms")
    perf_tracker.slow_operation_threshold_ms = slow_threshold
    perf_tracker.alert_threshold_ms = alert_threshold

    # Start resource monitoring if enabled
    if get_startup_setting("performance.resource_monitoring"):
        resource_interval = config.get("performance.resource_interval_seconds", 60)
        perf_monitor.resource_interval_seconds = resource_interval
        perf_monitor.start_monitoring()

    # Start background task manager if enabled
    if get_startup_setting("performance.background_tasks_enabled"):
        bg_manager = get_background_task_manager()
        bg_workers = get_startup_setting("performance.background_workers")
        bg_manager.max_workers = bg_workers
        bg_manager.start()

    # Initialize action loader for lazy loading
    if (
        get_startup_setting("performance.flags.lazy_load_actions")
        and get_startup_setting("performance.preload_critical_actions")
    ):
        action_loader = action_loader_func()
        # Preload critical actions
        critical_actions = config.get("performance.critical_actions", ["web_search"])
        if action_loader is not None:
            action_loader.preload_actions(critical_actions)

    # Initialize memory manager
    if get_startup_setting("performance.flags.reduce_memory_footprint"):
        memory_manager = get_memory_manager()
        memory_manager.start_gc_thread()
        logger.info("Memory manager started with GC thread")

    logger.info("Performance tracking system initialized")
    return perf_tracker, perf_monitor
