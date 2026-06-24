"""
Morning Routine System for Mark-XXXIX
=====================================
Manages automated morning skin check workflows with reminders and notifications.
"""

import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from datetime import time as dt_time
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.local_analyzer import get_local_analyzer
from core.logger import get_logger
from core.paths import project_path

logger = get_logger(__name__)


class RoutineMode(Enum):
    """Mode for morning routine."""

    OFF = "off"
    MANUAL = "manual"
    SEMI_AUTOMATIC = "semi_automatic"
    FULL_AUTOMATIC = "full_automatic"


class RoutineStatus(Enum):
    """Status of the morning routine."""

    IDLE = "idle"
    WAITING_FOR_PHOTO = "waiting_for_photo"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class RoutineConfig:
    """Configuration for morning routine."""

    mode: RoutineMode = RoutineMode.MANUAL
    reminder_time: str = "08:00"  # HH:MM format
    reminder_window_minutes: int = 60
    photo_directory: Optional[str] = None
    auto_analyze: bool = True
    send_reminder_if_missed: bool = True
    reminder_delay_minutes: int = 120  # Reminder 2 hours after scheduled time
    quiet_hours_start: str = "22:00"
    quiet_hours_end: str = "07:00"


@dataclass
class RoutineExecution:
    """Record of a routine execution."""

    date: str
    scheduled_time: str
    actual_time: Optional[str] = None
    status: RoutineStatus = RoutineStatus.IDLE
    photo_path: Optional[str] = None
    analysis_result: Optional[Dict[str, Any]] = None
    reminder_sent: bool = False
    notes: List[str] = field(default_factory=list)


class MorningRoutine:
    """
    Manages automated morning skin check workflow.
    Integrates with local analyzer and reminder system.
    """

    def __init__(self, config: Optional[RoutineConfig] = None):
        """
        Initialize the morning routine system.

        Args:
            config: Routine configuration
        """
        self.config = config or RoutineConfig()
        self.status = RoutineStatus.IDLE
        self.current_execution: Optional[RoutineExecution] = None
        self.execution_history: List[RoutineExecution] = []
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.is_running = False
        self.enable_reminders = True
        self.notification_callback: Optional[Callable[[str], None]] = None

        self._lock = threading.Lock()
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Integration
        self.local_analyzer = get_local_analyzer()
        self.status_callback: Optional[Callable[[RoutineStatus, str], None]] = None

        # Persistence
        self.persistence_file = project_path("data", "morning_routine.json")
        self.persistence_file.parent.mkdir(parents=True, exist_ok=True)
        self._load_history()

        logger.info(f"Morning routine initialized (mode: {self.config.mode.value})")

    # ------------------------------------------------------------------
    # General routine/task API
    # ------------------------------------------------------------------
    def add_task(self, task_name: str, task_type: str, scheduled_time: dt_time) -> str:
        if not isinstance(task_name, str) or not task_name.strip():
            raise ValueError("task_name must be a non-empty string")
        if not isinstance(task_type, str) or not task_type.strip():
            raise ValueError("task_type must be a non-empty string")
        task_id = uuid.uuid4().hex
        self.tasks[task_id] = {
            "id": task_id,
            "task_name": task_name,
            "task_type": task_type,
            "scheduled_time": scheduled_time.strftime("%H:%M"),
            "status": "pending",
            "result": None,
        }
        return task_id

    def start_routine(self) -> None:
        self.is_running = True

    def stop_routine(self) -> None:
        self.is_running = False

    def _execute_task_internal(self, task: Dict[str, Any]) -> Dict[str, Any]:
        task_type = task.get("task_type")
        if task_type == "skin_analysis":
            return {"message": "Skin check queued", "task_type": task_type}
        if task_type == "weather":
            return {"message": "Weather check ready", "task_type": task_type}
        if task_type == "calendar":
            return {"message": "Calendar review ready", "task_type": task_type}
        return {"message": f"Completed {task.get('task_name')}", "task_type": task_type}

    def execute_task(self, task_id: str) -> Dict[str, Any]:
        if task_id not in self.tasks:
            raise KeyError(task_id)
        task = self.tasks[task_id]
        try:
            result = self._execute_task_internal(task)
            task["status"] = "completed"
            task["result"] = result
            return result
        except Exception as exc:
            task["status"] = "failed"
            task["result"] = {"error": str(exc)}
            return task["result"]

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        if task_id not in self.tasks:
            raise KeyError(task_id)
        return dict(self.tasks[task_id])

    def skip_task(self, task_id: str) -> None:
        if task_id not in self.tasks:
            raise KeyError(task_id)
        self.tasks[task_id]["status"] = "skipped"

    def complete_task(self, task_id: str) -> None:
        if task_id not in self.tasks:
            raise KeyError(task_id)
        self.tasks[task_id]["status"] = "completed"

    def get_routine_summary(self) -> Dict[str, Any]:
        counts: Dict[str, int] = {}
        for task in self.tasks.values():
            status = task.get("status", "pending")
            counts[status] = counts.get(status, 0) + 1
        return {"total_tasks": len(self.tasks), "statuses": counts, "is_running": self.is_running}

    def set_notification_callback(self, callback: Callable[[str], None]) -> None:
        self.notification_callback = callback

    def trigger_reminder(self, task_id: str) -> bool:
        if task_id not in self.tasks:
            raise KeyError(task_id)
        if self.notification_callback:
            self.notification_callback(f"Routine reminder: {self.tasks[task_id]['task_name']}")
        return True

    def execute_skin_check(self) -> Dict[str, Any]:
        return {"analysis": "Skin check requires a submitted photo.", "recommendations": []}

    def save_configuration(self) -> None:
        self._save_history()

    def load_configuration(self) -> None:
        self._load_history()

    def run_quick_command(
        self,
        command: str,
        *,
        meeting_title: Optional[str] = None,
        focus_minutes: int = 50,
    ) -> Dict[str, Any]:
        """Run common day/session routine flows without external services."""
        normalized = " ".join(str(command or "").lower().split())
        briefing_text = ""
        session_text = ""

        if normalized in {"start my day", "start day", "morning"}:
            from core.daily_briefing import get_daily_briefing

            briefing_text = get_daily_briefing().generate_morning_briefing()
            action = "start_day"
            next_steps = ["Review top focus", "Check calendar conflicts", "Start first work block"]
        elif normalized in {"wrap up", "evening", "end day"}:
            from core.daily_briefing import get_daily_briefing
            from memory.memory_manager import remember_daily_summary

            briefing_text = get_daily_briefing().generate_evening_briefing()
            remember_daily_summary(datetime.now().date().isoformat(), briefing_text[:500])
            action = "wrap_up"
            next_steps = ["Resolve open ends", "Save decisions", "Pick tomorrow's first task"]
        elif normalized in {"meeting prep", "prepare meeting"}:
            action = "meeting_prep"
            title = meeting_title or "next meeting"
            next_steps = [f"Review context for {title}", "List desired outcomes", "Capture questions"]
        elif normalized in {"focus mode", "focus"}:
            action = "focus_mode"
            next_steps = [f"Start {focus_minutes}-minute focus block", "Silence non-urgent inputs"]
        elif normalized in {"summarize last hour", "last hour"}:
            from core.session_manager import get_session_manager

            action = "summarize_last_hour"
            session_text = get_session_manager().summarize_last_hour()
            next_steps = ["Continue the most recent thread"]
        elif normalized in {"what changed since yesterday", "changed since yesterday"}:
            from core.session_manager import get_session_manager

            action = "changed_since_yesterday"
            changes = get_session_manager().what_changed_since_yesterday()
            session_text = (
                f"{changes['activity_count']} activities, "
                f"{len(changes['files'])} files, {len(changes['open_ends'])} open ends."
            )
            next_steps = changes["open_ends"][:5] or ["No unresolved changes recorded"]
        else:
            action = "unknown"
            next_steps = ["Available: start my day, wrap up, meeting prep, focus mode, summarize last hour, what changed since yesterday"]

        return {
            "command": normalized,
            "action": action,
            "briefing": briefing_text,
            "session_summary": session_text,
            "next_steps": next_steps,
        }

    def set_status_callback(self, callback: Callable[[RoutineStatus, str], None]):
        """
        Set callback for status updates.

        Args:
            callback: Function to call when status changes
        """
        with self._lock:
            self.status_callback = callback
            logger.info("Status callback set")

    def start_monitoring(self):
        """Start the background monitoring thread."""
        with self._lock:
            if self._running:
                logger.warning("Morning routine monitoring already running")
                return

            self._running = True
            self._stop_event.clear()
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop, name="MorningRoutineMonitor", daemon=True
            )
            self._monitor_thread.start()
            logger.info("Morning routine monitoring started")

    def stop_monitoring(self):
        """Stop the background monitoring thread."""
        with self._lock:
            if not self._running:
                return

            self._stop_event.set()
            if self._monitor_thread:
                self._monitor_thread.join(timeout=5.0)

            self._running = False
            logger.info("Morning routine monitoring stopped")

    def _monitor_loop(self):
        """Background monitoring loop."""
        while not self._stop_event.is_set():
            try:
                current_time = datetime.now()
                current_time_str = current_time.strftime("%H:%M")

                # Check if it's reminder time
                if current_time_str == self.config.reminder_time:
                    self._trigger_reminder()

                # Check for missed reminder
                if self.config.send_reminder_if_missed:
                    self._check_missed_reminder(current_time)

                # Wait before next check
                self._stop_event.wait(timeout=60)  # Check every minute

            except Exception as e:
                logger.error(f"Monitor loop error: {e}")

    def _trigger_reminder(self):
        """Trigger the morning routine reminder."""
        with self._lock:
            if self.config.mode == RoutineMode.OFF:
                return

            today = datetime.now().strftime("%Y-%m-%d")

            # Check if already executed today
            if any(exec.date == today for exec in self.execution_history):
                logger.info(f"Morning routine already executed today: {today}")
                return

            # Create new execution record
            execution = RoutineExecution(
                date=today,
                scheduled_time=self.config.reminder_time,
                actual_time=datetime.now().strftime("%H:%M"),
                status=RoutineStatus.WAITING_FOR_PHOTO,
            )
            self.current_execution = execution
            self.status = RoutineStatus.WAITING_FOR_PHOTO

            # Trigger callback
            if self.status_callback:
                try:
                    self.status_callback(
                        RoutineStatus.WAITING_FOR_PHOTO,
                        f"Morning routine reminder at {self.config.reminder_time}",
                    )
                except Exception as e:
                    logger.error(f"Status callback failed: {e}")

            logger.info(f"Morning routine reminder triggered: {today}")

    def _check_missed_reminder(self, current_time: datetime):
        """Check if reminder was missed and send follow-up."""
        with self._lock:
            if not self.current_execution:
                return

            if self.current_execution.status != RoutineStatus.WAITING_FOR_PHOTO:
                return

            # Calculate time since scheduled reminder
            scheduled_dt = datetime.strptime(self.current_execution.scheduled_time, "%H:%M")
            scheduled_dt = scheduled_dt.replace(
                year=current_time.year, month=current_time.month, day=current_time.day
            )

            time_diff = (current_time - scheduled_dt).total_seconds()

            # If past the delay threshold and no photo received
            if time_diff > (self.config.reminder_delay_minutes * 60):
                self._send_followup_reminder()

    def _send_followup_reminder(self):
        """Send a follow-up reminder for missed photo."""
        if not self.current_execution:
            return

        message = (
            "Morgenroutine: Du hast das Hautfoto noch nicht hochgeladen. "
            "Möchtest du es jetzt nachholen?"
        )

        try:
            from actions.reminder import create_reminder

            # Use the reminder system
            create_reminder(
                task_name="morning_skin_check_followup", message=message, delay_minutes=0
            )

            self.current_execution.reminder_sent = True
            self.current_execution.notes.append("Follow-up reminder sent")

            logger.info("Follow-up reminder sent for missed morning routine")

        except Exception as e:
            logger.error(f"Failed to send follow-up reminder: {e}")

    def submit_photo(self, photo_path: Path) -> bool:
        """
        Submit a photo for morning routine analysis.

        Args:
            photo_path: Path to the photo file

        Returns:
            True if photo accepted
        """
        with self._lock:
            if not self.current_execution:
                logger.warning("No active routine execution to submit photo to")
                return False

            if not photo_path.exists():
                logger.error(f"Photo file not found: {photo_path}")
                return False

            self.current_execution.photo_path = str(photo_path)
            self.current_execution.status = RoutineStatus.ANALYZING
            self.status = RoutineStatus.ANALYZING

            # Trigger callback
            if self.status_callback:
                try:
                    self.status_callback(
                        RoutineStatus.ANALYZING, f"Analyzing photo: {photo_path.name}"
                    )
                except Exception as e:
                    logger.error(f"Status callback failed: {e}")

            # Perform analysis in background
            threading.Thread(target=self._analyze_photo, args=(photo_path,), daemon=True).start()

            return True

    def _analyze_photo(self, photo_path: Path):
        """Analyze the submitted photo."""
        try:
            # Use local analyzer for skin analysis
            result = self.local_analyzer.analyze_skin_image(photo_path)

            with self._lock:
                if self.current_execution:
                    self.current_execution.analysis_result = result
                    self.current_execution.status = RoutineStatus.COMPLETED
                    self.status = RoutineStatus.COMPLETED
                    self.execution_history.append(self.current_execution)
                    self._save_history()

                    # Trigger callback
                    if self.status_callback:
                        try:
                            self.status_callback(RoutineStatus.COMPLETED, "Skin analysis completed")
                        except Exception as e:
                            logger.error(f"Status callback failed: {e}")

            logger.info(f"Photo analysis completed: {photo_path}")

        except Exception as e:
            logger.error(f"Photo analysis failed: {e}")

            with self._lock:
                if self.current_execution:
                    self.current_execution.status = RoutineStatus.FAILED
                    self.current_execution.notes.append(f"Analysis error: {str(e)}")
                    self.status = RoutineStatus.FAILED

                    # Trigger callback
                    if self.status_callback:
                        try:
                            self.status_callback(RoutineStatus.FAILED, f"Analysis failed: {str(e)}")
                        except Exception as e:
                            logger.error(f"Status callback failed: {e}")

    def skip_today(self):
        """Skip today's routine."""
        with self._lock:
            if not self.current_execution:
                logger.warning("No active routine execution to skip")
                return

            self.current_execution.status = RoutineStatus.SKIPPED
            self.current_execution.notes.append("Skipped by user")
            self.execution_history.append(self.current_execution)
            self._save_history()

            self.status = RoutineStatus.SKIPPED
            self.current_execution = None

            logger.info("Morning routine skipped for today")

    def get_current_status(self) -> Dict[str, Any]:
        """
        Get current routine status.

        Returns:
            Dictionary with status information
        """
        with self._lock:
            return {
                "status": self.status.value,
                "mode": self.config.mode.value,
                "current_execution": (
                    self.current_execution.to_dict() if self.current_execution else None
                ),
                "reminder_time": self.config.reminder_time,
                "today_completed": any(
                    exec.date == datetime.now().strftime("%Y-%m-%d")
                    and exec.status == RoutineStatus.COMPLETED
                    for exec in self.execution_history
                ),
            }

    def get_history(self, days: int = 7) -> List[RoutineExecution]:
        """
        Get routine execution history.

        Args:
            days: Number of days to look back

        Returns:
            List of routine executions
        """
        with self._lock:
            cutoff = datetime.now().timestamp() - (days * 24 * 3600)
            recent = []

            for exec in reversed(self.execution_history):
                exec_date = datetime.strptime(exec.date, "%Y-%m-%d").timestamp()
                if exec_date >= cutoff:
                    recent.append(exec)
                else:
                    break

            return recent

    def _load_history(self):
        """Load execution history from persistence."""
        try:
            if not self.persistence_file.exists():
                return

            with open(self.persistence_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            for exec_data in data.get("executions", []):
                execution = RoutineExecution(**exec_data)
                self.execution_history.append(execution)

            logger.info(f"Loaded {len(self.execution_history)} routine executions from history")

        except Exception as e:
            logger.error(f"Failed to load routine history: {e}")

    def _save_history(self):
        """Save execution history to persistence."""
        try:
            data = {
                "saved_at": datetime.now().isoformat(),
                "config": {
                    "mode": self.config.mode.value,
                    "reminder_time": self.config.reminder_time,
                },
                "executions": [
                    {
                        "date": exec.date,
                        "scheduled_time": exec.scheduled_time,
                        "actual_time": exec.actual_time,
                        "status": exec.status.value,
                        "photo_path": exec.photo_path,
                        "analysis_result": exec.analysis_result,
                        "reminder_sent": exec.reminder_sent,
                        "notes": exec.notes,
                    }
                    for exec in self.execution_history
                ],
            }

            with open(self.persistence_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)

            logger.debug("Routine history saved")

        except Exception as e:
            logger.error(f"Failed to save routine history: {e}")


# Global instance
_morning_routine: Optional[MorningRoutine] = None


def get_morning_routine(config: Optional[RoutineConfig] = None) -> MorningRoutine:
    """Get the global morning routine instance."""
    global _morning_routine
    if _morning_routine is None:
        _morning_routine = MorningRoutine(config)
    return _morning_routine
