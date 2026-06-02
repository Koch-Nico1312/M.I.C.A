"""
Performance Tracker System for Mark-XXXIX
==========================================
Provides real-time performance tracking, status updates, and metrics aggregation.
Focuses on user-visible performance feedback and bottleneck detection.
"""

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from core.logger import get_logger

logger = get_logger(__name__)


class TaskStatus(Enum):
    """Status of a tracked task."""

    PENDING = "pending"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ActivityType(Enum):
    """Type of activity being tracked."""

    MODEL_CALL = "model_call"
    TOOL_EXECUTION = "tool_execution"
    FILE_OPERATION = "file_operation"
    NETWORK_REQUEST = "network_request"
    UI_UPDATE = "ui_update"
    BACKGROUND_TASK = "background_task"


@dataclass
class TaskProgress:
    """Progress information for a running task."""

    task_id: str
    task_name: str
    status: TaskStatus
    progress_percent: float = 0.0
    current_step: str = ""
    total_steps: int = 0
    current_step_index: int = 0
    estimated_remaining_seconds: Optional[float] = None
    start_time: datetime = field(default_factory=datetime.now)
    last_update: datetime = field(default_factory=datetime.now)
    error_message: Optional[str] = None


@dataclass
class ActivitySnapshot:
    """Snapshot of current system activity."""

    timestamp: datetime
    active_tasks: List[str]
    current_activity: Optional[str] = None
    activity_type: Optional[ActivityType] = None
    model_active: bool = False
    tool_active: bool = False
    background_job_active: bool = False
    waiting_for_input: bool = False


@dataclass
class PerformanceAlert:
    """Alert for performance issues."""

    alert_type: str
    severity: str  # info, warning, critical
    message: str
    timestamp: datetime
    affected_component: Optional[str] = None
    suggested_action: Optional[str] = None


class PerformanceTracker:
    """
    Tracks performance metrics and provides real-time status updates.
    Focuses on user-visible feedback and bottleneck detection.
    """

    def __init__(
        self,
        max_active_tasks: int = 100,
        max_history_size: int = 1000,
        alert_threshold_ms: float = 5000.0,  # Alert on operations > 5s
        slow_operation_threshold_ms: float = 2000.0,  # Consider > 2s as slow
    ):
        """
        Initialize the performance tracker.

        Args:
            max_active_tasks: Maximum number of active tasks to track
            max_history_size: Maximum size of activity history
            alert_threshold_ms: Threshold for performance alerts
            slow_operation_threshold_ms: Threshold for slow operation detection
        """
        self.max_active_tasks = max_active_tasks
        self.max_history_size = max_history_size
        self.alert_threshold_ms = alert_threshold_ms
        self.slow_operation_threshold_ms = slow_operation_threshold_ms

        self.active_tasks: Dict[str, TaskProgress] = {}
        self.activity_history: deque = deque(maxlen=max_history_size)
        self.performance_alerts: List[PerformanceAlert] = []

        self._status_callback: Optional[Callable[[TaskProgress], None]] = None
        self._alert_callback: Optional[Callable[[PerformanceAlert], None]] = None
        self._lock = threading.RLock()

        logger.info("Performance tracker initialized")

    def set_status_callback(self, callback: Callable[[TaskProgress], None]):
        """
        Set callback for status updates.

        Args:
            callback: Function to call when task status changes
        """
        with self._lock:
            self._status_callback = callback
            logger.info("Status callback set")

    def set_alert_callback(self, callback: Callable[[PerformanceAlert], None]):
        """
        Set callback for performance alerts.

        Args:
            callback: Function to call when performance alert is triggered
        """
        with self._lock:
            self._alert_callback = callback
            logger.info("Alert callback set")

    def start_task(
        self,
        task_id: str,
        task_name: str,
        total_steps: int = 0,
        estimated_duration_seconds: Optional[float] = None,
    ) -> TaskProgress:
        """
        Start tracking a new task.

        Args:
            task_id: Unique identifier for the task
            task_name: Human-readable task name
            total_steps: Total number of steps (for progress tracking)
            estimated_duration_seconds: Estimated duration in seconds

        Returns:
            TaskProgress object for the new task
        """
        with self._lock:
            progress = TaskProgress(
                task_id=task_id,
                task_name=task_name,
                status=TaskStatus.RUNNING,
                total_steps=total_steps,
                estimated_remaining_seconds=estimated_duration_seconds,
            )

            self.active_tasks[task_id] = progress

            # Trim old tasks if needed
            if len(self.active_tasks) > self.max_active_tasks:
                oldest_id = next(iter(self.active_tasks))
                del self.active_tasks[oldest_id]

            logger.info(f"Task started: {task_name} (ID: {task_id})")

            # Trigger callback
            if self._status_callback:
                try:
                    self._status_callback(progress)
                except Exception as e:
                    logger.error(f"Status callback failed: {e}")

            return progress

    def update_task_progress(
        self,
        task_id: str,
        progress_percent: Optional[float] = None,
        current_step: Optional[str] = None,
        current_step_index: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> Optional[TaskProgress]:
        """
        Update progress for a running task.

        Args:
            task_id: Task identifier
            progress_percent: Progress percentage (0-100)
            current_step: Description of current step
            current_step_index: Current step index
            error_message: Error message if task failed

        Returns:
            Updated TaskProgress or None if task not found
        """
        with self._lock:
            if task_id not in self.active_tasks:
                logger.warning(f"Task not found: {task_id}")
                return None

            progress = self.active_tasks[task_id]

            if progress_percent is not None:
                progress.progress_percent = min(100.0, max(0.0, progress_percent))

            if current_step is not None:
                progress.current_step = current_step

            if current_step_index is not None:
                progress.current_step_index = current_step_index

            if error_message is not None:
                progress.status = TaskStatus.FAILED
                progress.error_message = error_message

            progress.last_update = datetime.now()

            # Update estimated remaining time
            if progress.progress_percent > 0 and progress.estimated_remaining_seconds:
                elapsed = (progress.last_update - progress.start_time).total_seconds()
                total_estimated = elapsed / (progress.progress_percent / 100.0)
                progress.estimated_remaining_seconds = max(0.0, total_estimated - elapsed)

            logger.debug(
                f"Task progress updated: {progress.task_name} - {progress.progress_percent:.1f}%"
            )

            # Trigger callback
            if self._status_callback:
                try:
                    self._status_callback(progress)
                except Exception as e:
                    logger.error(f"Status callback failed: {e}")

            return progress

    def complete_task(self, task_id: str, success: bool = True) -> Optional[TaskProgress]:
        """
        Mark a task as completed.

        Args:
            task_id: Task identifier
            success: Whether the task completed successfully

        Returns:
            Completed TaskProgress or None if task not found
        """
        with self._lock:
            if task_id not in self.active_tasks:
                logger.warning(f"Task not found: {task_id}")
                return None

            progress = self.active_tasks[task_id]
            progress.status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
            progress.progress_percent = 100.0
            progress.last_update = datetime.now()

            # Add to history
            duration = (progress.last_update - progress.start_time).total_seconds()
            self.activity_history.append(
                {
                    "task_id": task_id,
                    "task_name": progress.task_name,
                    "status": progress.status.value,
                    "duration_seconds": duration,
                    "timestamp": progress.last_update.isoformat(),
                }
            )

            # Remove from active tasks
            del self.active_tasks[task_id]

            logger.info(f"Task completed: {progress.task_name} - {duration:.2f}s")

            # Trigger callback
            if self._status_callback:
                try:
                    self._status_callback(progress)
                except Exception as e:
                    logger.error(f"Status callback failed: {e}")

            return progress

    def get_active_tasks(self) -> List[TaskProgress]:
        """Get list of all active tasks."""
        with self._lock:
            return list(self.active_tasks.values())

    def get_task(self, task_id: str) -> Optional[TaskProgress]:
        """Get a specific task by ID."""
        with self._lock:
            return self.active_tasks.get(task_id)

    def create_activity_snapshot(self) -> ActivitySnapshot:
        """
        Create a snapshot of current system activity.

        Returns:
            ActivitySnapshot with current state
        """
        with self._lock:
            active_task_names = [t.task_name for t in self.active_tasks.values()]

            # Determine current activity
            current_activity = None
            activity_type = None

            if self.active_tasks:
                # Get most recently updated task
                latest_task = max(self.active_tasks.values(), key=lambda t: t.last_update)
                current_activity = latest_task.current_step or latest_task.task_name

                # Determine activity type from task name
                task_name_lower = latest_task.task_name.lower()
                if "model" in task_name_lower or "llm" in task_name_lower:
                    activity_type = ActivityType.MODEL_CALL
                elif "tool" in task_name_lower or "action" in task_name_lower:
                    activity_type = ActivityType.TOOL_EXECUTION
                elif "file" in task_name_lower or "download" in task_name_lower:
                    activity_type = ActivityType.FILE_OPERATION
                elif "network" in task_name_lower or "api" in task_name_lower:
                    activity_type = ActivityType.NETWORK_REQUEST
                else:
                    activity_type = ActivityType.BACKGROUND_TASK

            return ActivitySnapshot(
                timestamp=datetime.now(),
                active_tasks=active_task_names,
                current_activity=current_activity,
                activity_type=activity_type,
                model_active=activity_type == ActivityType.MODEL_CALL,
                tool_active=activity_type == ActivityType.TOOL_EXECUTION,
                background_job_active=len(self.active_tasks) > 0,
                waiting_for_input=len(self.active_tasks) == 0,
            )

    def record_slow_operation(
        self, operation_type: str, duration_ms: float, component: Optional[str] = None
    ):
        """
        Record a slow operation and potentially trigger an alert.

        Args:
            operation_type: Type of operation
            duration_ms: Duration in milliseconds
            component: Component that performed the operation
        """
        if duration_ms >= self.alert_threshold_ms:
            alert = PerformanceAlert(
                alert_type="slow_operation",
                severity="warning" if duration_ms < self.alert_threshold_ms * 2 else "critical",
                message=f"Slow operation detected: {operation_type} took {duration_ms:.2f}ms",
                timestamp=datetime.now(),
                affected_component=component,
                suggested_action="Consider caching or optimizing this operation",
            )

            self.performance_alerts.append(alert)

            # Trim old alerts
            if len(self.performance_alerts) > 100:
                self.performance_alerts = self.performance_alerts[-100:]

            logger.warning(f"Slow operation: {operation_type} - {duration_ms:.2f}ms")

            # Trigger alert callback
            if self._alert_callback:
                try:
                    self._alert_callback(alert)
                except Exception as e:
                    logger.error(f"Alert callback failed: {e}")

    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get a summary of current performance state.

        Returns:
            Dictionary with performance summary
        """
        with self._lock:
            snapshot = self.create_activity_snapshot()

            return {
                "timestamp": snapshot.timestamp.isoformat(),
                "active_tasks": len(self.active_tasks),
                "current_activity": snapshot.current_activity,
                "activity_type": snapshot.activity_type.value if snapshot.activity_type else None,
                "model_active": snapshot.model_active,
                "tool_active": snapshot.tool_active,
                "background_job_active": snapshot.background_job_active,
                "waiting_for_input": snapshot.waiting_for_input,
                "recent_alerts": len(self.performance_alerts),
                "history_size": len(self.activity_history),
            }

    def get_recent_alerts(self, limit: int = 10) -> List[PerformanceAlert]:
        """
        Get recent performance alerts.

        Args:
            limit: Maximum number of alerts to return

        Returns:
            List of recent alerts
        """
        with self._lock:
            return self.performance_alerts[-limit:]


# Global instance
_performance_tracker: Optional[PerformanceTracker] = None


def get_performance_tracker() -> PerformanceTracker:
    """Get the global performance tracker instance."""
    global _performance_tracker
    if _performance_tracker is None:
        _performance_tracker = PerformanceTracker()
    return _performance_tracker


def track_task_decorator(task_name: str, total_steps: int = 0):
    """
    Decorator to automatically track task execution.

    Args:
        task_name: Name of the task
        total_steps: Total number of steps
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            tracker = get_performance_tracker()
            task_id = f"{task_name}_{int(time.time() * 1000)}"

            # Start task
            tracker.start_task(task_id, task_name, total_steps)

            try:
                result = func(*args, **kwargs)
                tracker.complete_task(task_id, success=True)
                return result
            except Exception as e:
                tracker.update_task_progress(task_id, error_message=str(e))
                tracker.complete_task(task_id, success=False)
                raise

        return wrapper

    return decorator
