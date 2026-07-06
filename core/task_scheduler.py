"""
Task Scheduler for M.I.C.A AI Assistant.

This module provides a task scheduling system for executing actions at specific times
or on recurring schedules.
"""

import schedule
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from core.logger import get_logger

logger = get_logger(__name__)


class ScheduledTask:
    """Represents a scheduled task."""
    
    def __init__(
        self,
        task_id: str,
        name: str,
        action: Callable,
        schedule_type: str,
        schedule_value: str,
        parameters: Optional[Dict[str, Any]] = None,
        enabled: bool = True
    ):
        self.task_id = task_id
        self.name = name
        self.action = action
        self.schedule_type = schedule_type  # 'once', 'daily', 'weekly', 'interval'
        self.schedule_value = schedule_value  # time string, day name, or interval seconds
        self.parameters = parameters or {}
        self.enabled = enabled
        self.last_run: Optional[datetime] = None
        self.next_run: Optional[datetime] = None
        self.run_count = 0
        self._job: Optional[schedule.Job] = None
    
    def execute(self):
        """Execute the scheduled task."""
        if not self.enabled:
            logger.info(f"Task {self.task_id} is disabled, skipping")
            return
        
        try:
            logger.info(f"Executing task: {self.name} (ID: {self.task_id})")
            result = self.action(**self.parameters)
            self.last_run = datetime.now()
            self.run_count += 1
            logger.info(f"Task {self.task_id} completed successfully")
            return result
        except Exception as e:
            logger.error(f"Task {self.task_id} failed: {e}")
            raise


class TaskScheduler:
    """
    Task scheduler for M.I.C.A.
    
    Supports:
    - One-time tasks
    - Daily recurring tasks
    - Weekly recurring tasks
    - Interval-based tasks
    """
    
    def __init__(self):
        self._tasks: Dict[str, ScheduledTask] = {}
        self._running = False
        self._scheduler_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
    
    def schedule_task(
        self,
        task_id: str,
        name: str,
        action: Callable,
        schedule_type: str,
        schedule_value: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> ScheduledTask:
        """
        Schedule a new task.
        
        Args:
            task_id: Unique identifier for the task
            name: Human-readable task name
            action: Callable to execute
            schedule_type: Type of schedule ('once', 'daily', 'weekly', 'interval')
            schedule_value: Schedule value (time string, day name, or interval seconds)
            parameters: Parameters to pass to the action
            
        Returns:
            ScheduledTask: The created task
        """
        if task_id in self._tasks:
            raise ValueError(f"Task with ID {task_id} already exists")
        
        task = ScheduledTask(
            task_id=task_id,
            name=name,
            action=action,
            schedule_type=schedule_type,
            schedule_value=schedule_value,
            parameters=parameters
        )
        
        # Schedule the task
        if schedule_type == "once":
            task._job = schedule.every().day.at(schedule_value).do(task.execute)
        elif schedule_type == "daily":
            task._job = schedule.every().day.at(schedule_value).do(task.execute)
        elif schedule_type == "weekly":
            task._job = schedule.every().week.__getattribute__(schedule_value.lower()).do(task.execute)
        elif schedule_type == "interval":
            task._job = schedule.every(int(schedule_value)).seconds.do(task.execute)
        else:
            raise ValueError(f"Invalid schedule type: {schedule_type}")
        
        self._tasks[task_id] = task
        logger.info(f"Scheduled task: {name} ({schedule_type} at {schedule_value})")
        
        return task
    
    def unschedule_task(self, task_id: str) -> bool:
        """
        Unschedule a task.
        
        Args:
            task_id: ID of the task to unschedule
            
        Returns:
            bool: True if task was unscheduled, False if not found
        """
        if task_id not in self._tasks:
            return False
        
        task = self._tasks[task_id]
        if task._job:
            schedule.cancel_job(task._job)
        
        del self._tasks[task_id]
        logger.info(f"Unscheduled task: {task_id}")
        return True
    
    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """Get a task by ID."""
        return self._tasks.get(task_id)
    
    def get_all_tasks(self) -> List[ScheduledTask]:
        """Get all scheduled tasks."""
        return list(self._tasks.values())
    
    def enable_task(self, task_id: str) -> bool:
        """Enable a task."""
        task = self.get_task(task_id)
        if task:
            task.enabled = True
            logger.info(f"Enabled task: {task_id}")
            return True
        return False
    
    def disable_task(self, task_id: str) -> bool:
        """Disable a task."""
        task = self.get_task(task_id)
        if task:
            task.enabled = False
            logger.info(f"Disabled task: {task_id}")
            return True
        return False
    
    def run_task_now(self, task_id: str) -> Any:
        """Run a task immediately, regardless of schedule."""
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        logger.info(f"Running task now: {task_id}")
        return task.execute()
    
    def start(self):
        """Start the task scheduler."""
        if self._running:
            logger.warning("Task scheduler is already running")
            return
        
        self._running = True
        self._stop_event.clear()
        
        def run_scheduler():
            while self._running and not self._stop_event.is_set():
                schedule.run_pending()
                time.sleep(1)
        
        self._scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        self._scheduler_thread.start()
        logger.info("Task scheduler started")
    
    def stop(self):
        """Stop the task scheduler."""
        if not self._running:
            return
        
        self._running = False
        self._stop_event.set()
        
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5)
        
        logger.info("Task scheduler stopped")
    
    def is_running(self) -> bool:
        """Check if the scheduler is running."""
        return self._running
    
    def clear_all(self):
        """Clear all scheduled tasks."""
        for task_id in list(self._tasks.keys()):
            self.unschedule_task(task_id)
        logger.info("Cleared all scheduled tasks")


# Global task scheduler instance
_task_scheduler: Optional[TaskScheduler] = None


def get_task_scheduler() -> TaskScheduler:
    """
    Get the global task scheduler instance.
    
    Returns:
        TaskScheduler: The global task scheduler
    """
    global _task_scheduler
    if _task_scheduler is None:
        _task_scheduler = TaskScheduler()
    return _task_scheduler
