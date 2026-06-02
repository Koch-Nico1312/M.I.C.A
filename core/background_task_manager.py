"""
Background Task Manager for Mark-XXXIX
=======================================
Manages long-running tasks in background threads to prevent UI blocking.
Provides progress tracking, cancellation, and result retrieval.
"""

import queue
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from core.logger import get_logger

logger = get_logger(__name__)


class TaskState(Enum):
    """State of a background task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    """Priority levels for tasks."""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class BackgroundTask:
    """Represents a background task."""

    task_id: str
    name: str
    func: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    state: TaskState = TaskState.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[Exception] = None
    progress_callback: Optional[Callable[[float, str], None]] = None
    cancel_event: threading.Event = field(default_factory=threading.Event)


class BackgroundTaskManager:
    """
    Manages background task execution with worker pool.
    Prevents UI blocking by running long tasks in separate threads.
    """

    def __init__(self, max_workers: int = 4):
        """
        Initialize the background task manager.

        Args:
            max_workers: Maximum number of concurrent worker threads
        """
        self.max_workers = max_workers
        self.tasks: Dict[str, BackgroundTask] = {}
        self.task_queue: queue.PriorityQueue = queue.PriorityQueue()
        self.workers: List[threading.Thread] = []
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

        logger.info(f"Background task manager initialized with {max_workers} workers")

    def start(self):
        """Start the worker threads."""
        with self._lock:
            if self.workers:
                logger.warning("Workers already started")
                return

            for i in range(self.max_workers):
                worker = threading.Thread(
                    target=self._worker_loop, name=f"BackgroundWorker-{i}", daemon=True
                )
                worker.start()
                self.workers.append(worker)

            logger.info(f"Started {len(self.workers)} worker threads")

    def stop(self):
        """Stop all worker threads."""
        with self._lock:
            self._stop_event.set()

            for worker in self.workers:
                worker.join(timeout=5.0)

            self.workers.clear()
            logger.info("Background task manager stopped")

    def _worker_loop(self):
        """Worker thread loop for processing tasks."""
        while not self._stop_event.is_set():
            try:
                # Get task from queue (priority, task_id)
                priority, task_id = self.task_queue.get(timeout=1.0)

                with self._lock:
                    if task_id not in self.tasks:
                        self.task_queue.task_done()
                        continue

                    task = self.tasks[task_id]
                    task.state = TaskState.RUNNING
                    task.started_at = datetime.now()

                logger.info(f"Worker started task: {task.name} (ID: {task_id})")

                # Execute task
                try:
                    result = task.func(*task.args, **task.kwargs)

                    with self._lock:
                        task.result = result
                        task.state = TaskState.COMPLETED
                        task.completed_at = datetime.now()

                    logger.info(f"Task completed: {task.name} (ID: {task_id})")

                except Exception as e:
                    with self._lock:
                        task.error = e
                        task.state = TaskState.FAILED
                        task.completed_at = datetime.now()

                    logger.error(f"Task failed: {task.name} (ID: {task_id}) - {e}")

                finally:
                    self.task_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Worker error: {e}")

    def submit_task(
        self,
        task_id: str,
        name: str,
        func: Callable,
        args: tuple = (),
        kwargs: dict = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> BackgroundTask:
        """
        Submit a task for background execution.

        Args:
            task_id: Unique identifier for the task
            name: Human-readable task name
            func: Function to execute
            args: Positional arguments for the function
            kwargs: Keyword arguments for the function
            priority: Task priority
            progress_callback: Callback for progress updates (progress_percent, message)

        Returns:
            BackgroundTask object
        """
        if kwargs is None:
            kwargs = {}

        task = BackgroundTask(
            task_id=task_id,
            name=name,
            func=func,
            args=args,
            kwargs=kwargs,
            priority=priority,
            progress_callback=progress_callback,
        )

        with self._lock:
            self.tasks[task_id] = task

        # Add to queue (negative priority for max-heap behavior)
        self.task_queue.put((-priority.value, task_id))

        logger.info(f"Task submitted: {name} (ID: {task_id}, Priority: {priority.name})")
        return task

    def get_task(self, task_id: str) -> Optional[BackgroundTask]:
        """
        Get a task by ID.

        Args:
            task_id: Task identifier

        Returns:
            BackgroundTask or None if not found
        """
        with self._lock:
            return self.tasks.get(task_id)

    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a running or pending task.

        Args:
            task_id: Task identifier

        Returns:
            True if task was cancelled
        """
        with self._lock:
            if task_id not in self.tasks:
                return False

            task = self.tasks[task_id]

            if task.state in [TaskState.PENDING, TaskState.RUNNING]:
                task.cancel_event.set()
                task.state = TaskState.CANCELLED
                task.completed_at = datetime.now()
                logger.info(f"Task cancelled: {task.name} (ID: {task_id})")
                return True

            return False

    def get_task_result(self, task_id: str, timeout: Optional[float] = None) -> Any:
        """
        Wait for task completion and return result.

        Args:
            task_id: Task identifier
            timeout: Maximum time to wait in seconds

        Returns:
            Task result or raises exception if failed
        """
        start_time = time.time()

        while True:
            task = self.get_task(task_id)

            if task is None:
                raise ValueError(f"Task not found: {task_id}")

            if task.state == TaskState.COMPLETED:
                return task.result

            if task.state == TaskState.FAILED:
                if task.error:
                    raise task.error
                raise RuntimeError(f"Task failed: {task.name}")

            if task.state == TaskState.CANCELLED:
                raise RuntimeError(f"Task was cancelled: {task.name}")

            if timeout and (time.time() - start_time) > timeout:
                raise TimeoutError(f"Task timeout: {task.name}")

            time.sleep(0.1)

    def get_all_tasks(self) -> List[BackgroundTask]:
        """Get all tasks."""
        with self._lock:
            return list(self.tasks.values())

    def get_active_tasks(self) -> List[BackgroundTask]:
        """Get all active (running or pending) tasks."""
        with self._lock:
            return [
                t for t in self.tasks.values() if t.state in [TaskState.PENDING, TaskState.RUNNING]
            ]

    def get_completed_tasks(self) -> List[BackgroundTask]:
        """Get all completed tasks."""
        with self._lock:
            return [t for t in self.tasks.values() if t.state == TaskState.COMPLETED]

    def cleanup_old_tasks(self, max_age_hours: float = 24.0):
        """
        Remove old completed/failed tasks.

        Args:
            max_age_hours: Maximum age in hours to keep tasks
        """
        cutoff = datetime.now().timestamp() - (max_age_hours * 3600)

        with self._lock:
            to_remove = []
            for task_id, task in self.tasks.items():
                if task.state in [TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED]:
                    if task.completed_at and task.completed_at.timestamp() < cutoff:
                        to_remove.append(task_id)

            for task_id in to_remove:
                del self.tasks[task_id]

            if to_remove:
                logger.info(f"Cleaned up {len(to_remove)} old tasks")

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get task manager statistics.

        Returns:
            Dictionary with statistics
        """
        with self._lock:
            total = len(self.tasks)
            pending = sum(1 for t in self.tasks.values() if t.state == TaskState.PENDING)
            running = sum(1 for t in self.tasks.values() if t.state == TaskState.RUNNING)
            completed = sum(1 for t in self.tasks.values() if t.state == TaskState.COMPLETED)
            failed = sum(1 for t in self.tasks.values() if t.state == TaskState.FAILED)
            cancelled = sum(1 for t in self.tasks.values() if t.state == TaskState.CANCELLED)

            return {
                "total_tasks": total,
                "pending": pending,
                "running": running,
                "completed": completed,
                "failed": failed,
                "cancelled": cancelled,
                "queue_size": self.task_queue.qsize(),
                "active_workers": len([w for w in self.workers if w.is_alive()]),
            }


# Global instance
_background_task_manager: Optional[BackgroundTaskManager] = None


def get_background_task_manager() -> BackgroundTaskManager:
    """Get the global background task manager instance."""
    global _background_task_manager
    if _background_task_manager is None:
        _background_task_manager = BackgroundTaskManager()
    return _background_task_manager


def run_in_background(
    name: str,
    priority: TaskPriority = TaskPriority.NORMAL,
    progress_callback: Optional[Callable[[float, str], None]] = None,
):
    """
    Decorator to run a function in the background.

    Args:
        name: Task name
        priority: Task priority
        progress_callback: Callback for progress updates
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            manager = get_background_task_manager()
            task_id = f"{name}_{int(time.time() * 1000)}"

            task = manager.submit_task(
                task_id=task_id,
                name=name,
                func=func,
                args=args,
                kwargs=kwargs,
                priority=priority,
                progress_callback=progress_callback,
            )

            return task_id

        return wrapper

    return decorator
