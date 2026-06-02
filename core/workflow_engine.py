"""
Workflow Engine for Mark-XXXIX
==============================
Provides workflow orchestration, step execution, and queue management.
Supports pause, resume, cancel, and retry for complex multi-step tasks.
"""

import asyncio
import json
import queue
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from core.action_history import ActionStatus, get_action_history
from core.approval_flow import RiskLevel, get_approval_flow
from core.background_task_manager import TaskPriority, get_background_task_manager
from core.logger import get_logger
from core.metrics_collector import get_metrics_collector
from core.paths import project_path
from core.performance_flags import get_performance_flags
from core.performance_tracker import TaskStatus as PerfTaskStatus
from core.performance_tracker import get_performance_tracker
from core.permission_profiles import PermissionLevel, check_action

logger = get_logger(__name__)


class WorkflowStatus(Enum):
    """Status of a workflow."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(Enum):
    """Status of a workflow step."""

    PENDING = "pending"
    READY = "ready"  # Dependencies satisfied
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class WorkflowPriority(Enum):
    """Priority levels for workflows."""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


class ErrorClassification(Enum):
    """Classification of workflow errors."""

    CONFIGURATION = "configuration"
    USER = "user"
    NETWORK = "network"
    TOOL = "tool"
    SYSTEM = "system"
    UNKNOWN = "unknown"


@dataclass
class WorkflowStep:
    """Represents a single step in a workflow."""

    step_id: str
    name: str
    action: str  # Tool/action to execute
    parameters: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)  # Step IDs this step depends on
    expected_result: Optional[str] = None
    risk_level: str = "medium"  # low, medium, high
    requires_confirmation: bool = False
    retry_on_failure: bool = True
    max_retries: int = 3
    retry_count: int = 0
    status: StepStatus = StepStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: float = 0.0
    result: Optional[Any] = None
    error: Optional[str] = None
    error_classification: Optional[ErrorClassification] = None
    undo_data: Optional[Dict[str, Any]] = None  # Data for undo operation

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)


@dataclass
class Workflow:
    """Represents a complete workflow with multiple steps."""

    workflow_id: str
    name: str
    goal: str
    description: str
    steps: List[WorkflowStep] = field(default_factory=list)
    status: WorkflowStatus = WorkflowStatus.PENDING
    priority: WorkflowPriority = WorkflowPriority.NORMAL
    overall_risk_level: str = "medium"
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: float = 0.0
    current_step_index: int = 0
    result: Optional[Any] = None
    error: Optional[str] = None
    error_classification: Optional[ErrorClassification] = None
    retry_count: int = 0
    max_retries: int = 3

    def get_progress_percent(self) -> float:
        """Calculate overall progress percentage."""
        if not self.steps:
            return 0.0

        completed = sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)
        return (completed / len(self.steps)) * 100.0

    def get_current_step(self) -> Optional[WorkflowStep]:
        """Get the current running step."""
        for step in self.steps:
            if step.status == StepStatus.RUNNING:
                return step
        return None

    def get_ready_steps(self) -> List[WorkflowStep]:
        """Get steps whose dependencies are satisfied."""
        ready_steps = []
        completed_step_ids = {s.step_id for s in self.steps if s.status == StepStatus.COMPLETED}

        for step in self.steps:
            if step.status == StepStatus.PENDING:
                # Check if all dependencies are completed
                deps_satisfied = all(dep_id in completed_step_ids for dep_id in step.dependencies)
                if deps_satisfied:
                    ready_steps.append(step)

        return ready_steps

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data["steps"] = [s.to_dict() for s in self.steps]
        return data


class WorkflowEngine:
    """
    Manages workflow execution, queue, and control.
    Integrates with safety, performance, and history systems.
    """

    def __init__(self, max_concurrent_workflows: int = 2, persistence_dir: Optional[Path] = None):
        """
        Initialize the workflow engine.

        Args:
            max_concurrent_workflows: Maximum number of workflows running concurrently
            persistence_dir: Directory for workflow persistence
        """
        self.max_concurrent_workflows = max_concurrent_workflows
        self.max_parallel_steps = 4
        self.workflows: Dict[str, Workflow] = {}
        self.workflow_queue: queue.PriorityQueue = queue.PriorityQueue()
        self.active_workflows: Set[str] = set()

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._executor_thread: Optional[threading.Thread] = None
        self._async_loop: Optional[asyncio.AbstractEventLoop] = None

        # Persistence
        if persistence_dir is None:
            persistence_dir = project_path("data", "workflows")
        self.persistence_dir = Path(persistence_dir)
        self.persistence_dir.mkdir(parents=True, exist_ok=True)
        self.persistence_file = self.persistence_dir / "workflows.json"

        # Integration with existing systems
        self.approval_flow = get_approval_flow()
        self.action_history = get_action_history()
        self.performance_tracker = get_performance_tracker()
        self.background_manager = get_background_task_manager()

        # Load persisted workflows
        self._load_workflows()

        logger.info("Workflow engine initialized")

    def create_workflow(
        self,
        name: str,
        goal: str,
        description: str,
        steps: List[Dict[str, Any]],
        priority: WorkflowPriority = WorkflowPriority.NORMAL,
        overall_risk_level: str = "medium",
    ) -> Workflow:
        """
        Create a new workflow from definition.

        Args:
            name: Workflow name
            goal: Workflow goal
            description: Workflow description
            steps: List of step definitions
            priority: Workflow priority
            overall_risk_level: Overall risk level

        Returns:
            Created Workflow object
        """
        workflow_id = f"workflow_{int(time.time() * 1000)}"

        # Convert step definitions to WorkflowStep objects
        workflow_steps = []
        for i, step_def in enumerate(steps):
            step = WorkflowStep(
                step_id=f"{workflow_id}_step_{i}",
                name=step_def.get("name", f"Step {i+1}"),
                action=step_def.get("action", ""),
                parameters=step_def.get("parameters", {}),
                dependencies=step_def.get("dependencies", []),
                expected_result=step_def.get("expected_result"),
                risk_level=step_def.get("risk_level", "medium"),
                requires_confirmation=step_def.get("requires_confirmation", False),
                retry_on_failure=step_def.get("retry_on_failure", True),
                max_retries=step_def.get("max_retries", 3),
            )
            workflow_steps.append(step)

        workflow = Workflow(
            workflow_id=workflow_id,
            name=name,
            goal=goal,
            description=description,
            steps=workflow_steps,
            priority=priority,
            overall_risk_level=overall_risk_level,
        )

        with self._lock:
            self.workflows[workflow_id] = workflow

        logger.info(f"Workflow created: {name} (ID: {workflow_id}) with {len(steps)} steps")
        return workflow

    def submit_workflow(self, workflow: Workflow) -> str:
        """
        Submit a workflow for execution.

        Args:
            workflow: Workflow to submit

        Returns:
            Workflow ID
        """
        with self._lock:
            workflow.status = WorkflowStatus.QUEUED
            # Negative priority for max-heap behavior
            self.workflow_queue.put((-workflow.priority.value, workflow.workflow_id))

        logger.info(f"Workflow submitted: {workflow.name} (ID: {workflow.workflow_id})")
        return workflow.workflow_id

    def start_executor(self):
        """Start the workflow executor thread."""
        if self._executor_thread and self._executor_thread.is_alive():
            logger.warning("Workflow executor already running")
            return

        self._stop_event.clear()
        self._executor_thread = threading.Thread(
            target=self._executor_loop, name="WorkflowExecutor", daemon=True
        )
        self._executor_thread.start()
        logger.info("Workflow executor started")

    def stop_executor(self):
        """Stop the workflow executor thread."""
        if self._executor_thread and self._executor_thread.is_alive():
            self._stop_event.set()
            self._executor_thread.join(timeout=5.0)
            logger.info("Workflow executor stopped")

    def _executor_loop(self):
        """Main executor loop for processing workflows."""
        while not self._stop_event.is_set():
            try:
                # Get workflow from queue
                priority, workflow_id = self.workflow_queue.get(timeout=1.0)

                with self._lock:
                    if workflow_id not in self.workflows:
                        self.workflow_queue.task_done()
                        continue

                    workflow = self.workflows[workflow_id]

                    # Check if we can run this workflow
                    if len(self.active_workflows) >= self.max_concurrent_workflows:
                        # Re-queue for later
                        self.workflow_queue.put((priority, workflow_id))
                        self.workflow_queue.task_done()
                        time.sleep(0.5)
                        continue

                    if workflow.status != WorkflowStatus.QUEUED:
                        self.workflow_queue.task_done()
                        continue

                    # Mark as running
                    workflow.status = WorkflowStatus.RUNNING
                    workflow.started_at = datetime.now()
                    self.active_workflows.add(workflow_id)

                # Execute workflow
                try:
                    self._execute_workflow(workflow)
                except Exception as e:
                    logger.error(f"Workflow execution error: {e}")
                    with self._lock:
                        workflow.status = WorkflowStatus.FAILED
                        workflow.error = str(e)
                        workflow.error_classification = ErrorClassification.SYSTEM
                        workflow.completed_at = datetime.now()
                        self.active_workflows.discard(workflow_id)

                finally:
                    self.workflow_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Executor loop error: {e}")

    def _execute_workflow(self, workflow: Workflow):
        """
        Execute a workflow step by step.

        Args:
            workflow: Workflow to execute
        """
        perf_flags = get_performance_flags()
        metrics = get_metrics_collector()

        logger.info(f"Executing workflow: {workflow.name} (ID: {workflow.workflow_id})")

        # Track workflow in performance tracker
        task_id = self.performance_tracker.start_task(
            task_id=workflow.workflow_id, task_name=workflow.name, total_steps=len(workflow.steps)
        )

        try:
            if perf_flags.is_enabled("async_workflow_engine"):
                # Use async execution for parallel steps
                self._execute_workflow_async(workflow)
            else:
                # Original sequential execution
                self._execute_workflow_sequential(workflow)
        except Exception as e:
            logger.error(f"Workflow execution error: {e}")
            with self._lock:
                workflow.status = WorkflowStatus.FAILED
                workflow.error = str(e)
                workflow.error_classification = ErrorClassification.SYSTEM
                workflow.completed_at = datetime.now()
                self.active_workflows.discard(workflow_id)

    def _execute_workflow_sequential(self, workflow: Workflow):
        """
        Execute workflow steps sequentially (original implementation).

        Args:
            workflow: Workflow to execute
        """
        while workflow.status == WorkflowStatus.RUNNING and not self._stop_event.is_set():
            # Check for pause
            if workflow.status == WorkflowStatus.PAUSED:
                time.sleep(0.5)
                continue

            # Get ready steps
            ready_steps = workflow.get_ready_steps()

            if not ready_steps:
                # Check if all steps are completed
                if all(
                    s.status in [StepStatus.COMPLETED, StepStatus.SKIPPED] for s in workflow.steps
                ):
                    workflow.status = WorkflowStatus.COMPLETED
                    workflow.completed_at = datetime.now()
                    workflow.duration_ms = (
                        workflow.completed_at - workflow.started_at
                    ).total_seconds() * 1000
                    logger.info(f"Workflow completed: {workflow.name}")
                    break
                else:
                    # No ready steps but not all completed - likely failed dependencies
                    failed_steps = [s for s in workflow.steps if s.status == StepStatus.FAILED]
                    if failed_steps:
                        workflow.status = WorkflowStatus.FAILED
                        workflow.error = (
                            f"Failed dependencies: {', '.join(s.name for s in failed_steps)}"
                        )
                        workflow.error_classification = ErrorClassification.TOOL
                        workflow.completed_at = datetime.now()
                        logger.error(f"Workflow failed due to dependencies: {workflow.name}")
                        break
                    time.sleep(0.5)
                    continue

            # Execute first ready step
            step = ready_steps[0]
            self._execute_step(workflow, step)

    def _execute_workflow_async(self, workflow: Workflow):
        """
        Execute workflow steps with async parallel execution.

        Args:
            workflow: Workflow to execute
        """
        # Create asyncio event loop for this workflow
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(self._execute_workflow_async_loop(workflow))
        finally:
            loop.close()

    async def _execute_workflow_async_loop(self, workflow: Workflow):
        """
        Async loop for executing workflow steps in parallel.

        Args:
            workflow: Workflow to execute
        """
        metrics = get_metrics_collector()

        while workflow.status == WorkflowStatus.RUNNING and not self._stop_event.is_set():
            # Check for pause
            if workflow.status == WorkflowStatus.PAUSED:
                await asyncio.sleep(0.5)
                continue

            # Get ready steps
            ready_steps = workflow.get_ready_steps()

            if not ready_steps:
                # Check if all steps are completed
                if all(
                    s.status in [StepStatus.COMPLETED, StepStatus.SKIPPED] for s in workflow.steps
                ):
                    workflow.status = WorkflowStatus.COMPLETED
                    workflow.completed_at = datetime.now()
                    workflow.duration_ms = (
                        workflow.completed_at - workflow.started_at
                    ).total_seconds() * 1000
                    logger.info(f"Workflow completed (async): {workflow.name}")
                    break
                else:
                    # No ready steps but not all completed - likely failed dependencies
                    failed_steps = [s for s in workflow.steps if s.status == StepStatus.FAILED]
                    if failed_steps:
                        workflow.status = WorkflowStatus.FAILED
                        workflow.error = (
                            f"Failed dependencies: {', '.join(s.name for s in failed_steps)}"
                        )
                        workflow.error_classification = ErrorClassification.TOOL
                        workflow.completed_at = datetime.now()
                        logger.error(f"Workflow failed due to dependencies: {workflow.name}")
                        break
                    await asyncio.sleep(0.5)
                    continue

            # Execute ready steps in parallel (limited by max_parallel_steps)
            metrics.start_operation("parallel_step_execution")

            # Limit to max_parallel_steps
            steps_to_execute = ready_steps[: self.max_parallel_steps]

            # Create tasks for parallel execution
            tasks = []
            for step in steps_to_execute:
                task = asyncio.create_task(self._execute_step_async(workflow, step))
                tasks.append(task)

            # Wait for all tasks to complete
            await asyncio.gather(*tasks, return_exceptions=True)

            metrics.end_operation(
                "parallel_step_execution",
                {"steps_executed": len(steps_to_execute), "max_parallel": self.max_parallel_steps},
            )

            logger.debug(f"Executed {len(steps_to_execute)} steps in parallel")

    async def _execute_step_async(self, workflow: Workflow, step: WorkflowStep):
        """
        Execute a single workflow step asynchronously.

        Args:
            workflow: Workflow containing the step
            step: Step to execute
        """
        # Run the synchronous step execution in a thread pool
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._execute_step, workflow, step)

    def _execute_step(self, workflow: Workflow, step: WorkflowStep):
        """
        Execute a single workflow step.

        Args:
            workflow: Parent workflow
            step: Step to execute
        """
        logger.info(f"Executing step: {step.name} (ID: {step.step_id})")

        step.status = StepStatus.RUNNING
        step.started_at = datetime.now()

        try:
            # Check approval if required
            if step.requires_confirmation or step.risk_level == "high":
                is_allowed, message = self.approval_flow.check_and_request_approval(
                    tool_name=step.action, action=step.name, parameters=step.parameters
                )

                if not is_allowed:
                    step.status = StepStatus.FAILED
                    step.error = message
                    step.error_classification = ErrorClassification.USER
                    logger.warning(f"Step approval denied: {step.name} - {message}")
                    return

            # Check permission
            is_allowed, message = check_action(
                profile="normal", action=step.action, parameters=step.parameters
            )

            if not is_allowed:
                step.status = StepStatus.FAILED
                step.error = message
                step.error_classification = ErrorClassification.CONFIGURATION
                logger.error(f"Step permission denied: {step.name} - {message}")
                return

            # Execute the action (this would integrate with actual tool execution)
            # For now, simulate execution
            time.sleep(0.1)  # Simulate work

            step.status = StepStatus.COMPLETED
            step.completed_at = datetime.now()
            step.duration_ms = (step.completed_at - step.started_at).total_seconds() * 1000
            step.result = f"Completed: {step.expected_result or step.name}"

            logger.info(f"Step completed: {step.name} - {step.duration_ms:.2f}ms")

        except Exception as e:
            step.status = StepStatus.FAILED
            step.error = str(e)
            step.error_classification = self._classify_error(e)
            step.completed_at = datetime.now()
            logger.error(f"Step failed: {step.name} - {e}")

            # Retry if configured
            if step.retry_on_failure and step.retry_count < step.max_retries:
                step.retry_count += 1
                step.status = StepStatus.PENDING
                logger.info(
                    f"Retrying step: {step.name} (attempt {step.retry_count}/{step.max_retries})"
                )

    def _classify_error(self, error: Exception) -> ErrorClassification:
        """
        Classify an error for recovery suggestions.

        Args:
            error: Exception to classify

        Returns:
            ErrorClassification
        """
        error_str = str(error).lower()

        if "permission" in error_str or "access" in error_str:
            return ErrorClassification.CONFIGURATION
        elif "network" in error_str or "connection" in error_str:
            return ErrorClassification.NETWORK
        elif "timeout" in error_str:
            return ErrorClassification.NETWORK
        elif "file" in error_str or "path" in error_str:
            return ErrorClassification.SYSTEM
        elif "user" in error_str or "cancel" in error_str:
            return ErrorClassification.USER
        else:
            return ErrorClassification.TOOL

    def pause_workflow(self, workflow_id: str) -> bool:
        """
        Pause a running workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            True if paused
        """
        with self._lock:
            if workflow_id not in self.workflows:
                return False

            workflow = self.workflows[workflow_id]

            if workflow.status == WorkflowStatus.RUNNING:
                workflow.status = WorkflowStatus.PAUSED
                logger.info(f"Workflow paused: {workflow.name} (ID: {workflow_id})")
                return True

            return False

    def resume_workflow(self, workflow_id: str) -> bool:
        """
        Resume a paused workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            True if resumed
        """
        with self._lock:
            if workflow_id not in self.workflows:
                return False

            workflow = self.workflows[workflow_id]

            if workflow.status == WorkflowStatus.PAUSED:
                workflow.status = WorkflowStatus.RUNNING
                logger.info(f"Workflow resumed: {workflow.name} (ID: {workflow_id})")
                return True

            return False

    def cancel_workflow(self, workflow_id: str) -> bool:
        """
        Cancel a workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            True if cancelled
        """
        with self._lock:
            if workflow_id not in self.workflows:
                return False

            workflow = self.workflows[workflow_id]

            if workflow.status in [
                WorkflowStatus.PENDING,
                WorkflowStatus.QUEUED,
                WorkflowStatus.RUNNING,
                WorkflowStatus.PAUSED,
            ]:
                workflow.status = WorkflowStatus.CANCELLED
                workflow.completed_at = datetime.now()

                # Cancel running step
                current_step = workflow.get_current_step()
                if current_step:
                    current_step.status = StepStatus.CANCELLED

                self.active_workflows.discard(workflow_id)
                logger.info(f"Workflow cancelled: {workflow.name} (ID: {workflow_id})")
                return True

            return False

    def retry_workflow(self, workflow_id: str) -> bool:
        """
        Retry a failed workflow.

        Args:
            workflow_id: Workflow ID

        Returns:
            True if retry initiated
        """
        with self._lock:
            if workflow_id not in self.workflows:
                return False

            workflow = self.workflows[workflow_id]

            if (
                workflow.status == WorkflowStatus.FAILED
                and workflow.retry_count < workflow.max_retries
            ):
                # Reset failed steps
                for step in workflow.steps:
                    if step.status == StepStatus.FAILED:
                        step.status = StepStatus.PENDING
                        step.error = None
                        step.error_classification = None

                workflow.status = WorkflowStatus.QUEUED
                workflow.retry_count += 1

                # Re-queue
                self.workflow_queue.put((-workflow.priority.value, workflow_id))

                logger.info(f"Workflow retry initiated: {workflow.name} (ID: {workflow_id})")
                return True

            return False

    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """Get a workflow by ID."""
        with self._lock:
            return self.workflows.get(workflow_id)

    def get_all_workflows(self) -> List[Workflow]:
        """Get all workflows."""
        with self._lock:
            return list(self.workflows.values())

    def get_active_workflows(self) -> List[Workflow]:
        """Get all active workflows."""
        with self._lock:
            return [
                w
                for w in self.workflows.values()
                if w.status in [WorkflowStatus.RUNNING, WorkflowStatus.PAUSED]
            ]

    def get_queued_workflows(self) -> List[Workflow]:
        """Get all queued workflows."""
        with self._lock:
            return [w for w in self.workflows.values() if w.status == WorkflowStatus.QUEUED]

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get workflow engine statistics.

        Returns:
            Dictionary with statistics
        """
        with self._lock:
            total = len(self.workflows)
            pending = sum(1 for w in self.workflows.values() if w.status == WorkflowStatus.PENDING)
            queued = sum(1 for w in self.workflows.values() if w.status == WorkflowStatus.QUEUED)
            running = sum(1 for w in self.workflows.values() if w.status == WorkflowStatus.RUNNING)
            paused = sum(1 for w in self.workflows.values() if w.status == WorkflowStatus.PAUSED)
            completed = sum(
                1 for w in self.workflows.values() if w.status == WorkflowStatus.COMPLETED
            )
            failed = sum(1 for w in self.workflows.values() if w.status == WorkflowStatus.FAILED)
            cancelled = sum(
                1 for w in self.workflows.values() if w.status == WorkflowStatus.CANCELLED
            )

            return {
                "total_workflows": total,
                "pending": pending,
                "queued": queued,
                "running": running,
                "paused": paused,
                "completed": completed,
                "failed": failed,
                "cancelled": cancelled,
                "queue_size": self.workflow_queue.qsize(),
                "active_workflows": len(self.active_workflows),
            }

    def _load_workflows(self):
        """Load workflows from persistence file."""
        try:
            if not self.persistence_file.exists():
                logger.info("No persisted workflows found")
                return

            with open(self.persistence_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            for workflow_data in data.get("workflows", []):
                # Reconstruct workflow from data
                steps_data = workflow_data.get("steps", [])
                steps = []
                for step_data in steps_data:
                    step = WorkflowStep(**step_data)
                    steps.append(step)

                workflow_data["steps"] = steps
                workflow = Workflow(**workflow_data)
                self.workflows[workflow.workflow_id] = workflow

            logger.info(f"Loaded {len(self.workflows)} workflows from persistence")

        except Exception as e:
            logger.error(f"Failed to load workflows: {e}")

    def _save_workflows(self):
        """Save workflows to persistence file."""
        try:
            data = {
                "saved_at": datetime.now().isoformat(),
                "workflows": [w.to_dict() for w in self.workflows.values()],
            }

            with open(self.persistence_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)

            logger.debug(f"Saved {len(self.workflows)} workflows to persistence")

        except Exception as e:
            logger.error(f"Failed to save workflows: {e}")

    def save_workflow(self, workflow_id: str) -> bool:
        """
        Save a specific workflow to persistence.

        Args:
            workflow_id: Workflow ID

        Returns:
            True if saved successfully
        """
        with self._lock:
            if workflow_id not in self.workflows:
                return False

            self._save_workflows()
            return True

    def delete_workflow(self, workflow_id: str) -> bool:
        """
        Delete a workflow from memory and persistence.

        Args:
            workflow_id: Workflow ID

        Returns:
            True if deleted
        """
        with self._lock:
            if workflow_id not in self.workflows:
                return False

            workflow = self.workflows[workflow_id]

            # Don't delete active workflows
            if workflow.status in [WorkflowStatus.RUNNING, WorkflowStatus.QUEUED]:
                logger.warning(f"Cannot delete active workflow: {workflow_id}")
                return False

            del self.workflows[workflow_id]
            self._save_workflows()

            logger.info(f"Workflow deleted: {workflow_id}")
            return True

    def cleanup_old_workflows(self, max_age_hours: float = 168.0):
        """
        Remove old completed/failed workflows.

        Args:
            max_age_hours: Maximum age in hours to keep workflows
        """
        cutoff = datetime.now().timestamp() - (max_age_hours * 3600)

        with self._lock:
            to_remove = []
            for workflow_id, workflow in self.workflows.items():
                if workflow.status in [
                    WorkflowStatus.COMPLETED,
                    WorkflowStatus.FAILED,
                    WorkflowStatus.CANCELLED,
                ]:
                    if workflow.completed_at and workflow.completed_at.timestamp() < cutoff:
                        to_remove.append(workflow_id)

            for workflow_id in to_remove:
                del self.workflows[workflow_id]

            if to_remove:
                self._save_workflows()
                logger.info(f"Cleaned up {len(to_remove)} old workflows")


# Global instance
_workflow_engine: Optional[WorkflowEngine] = None


def get_workflow_engine() -> WorkflowEngine:
    """Get the global workflow engine instance."""
    global _workflow_engine
    if _workflow_engine is None:
        _workflow_engine = WorkflowEngine()
    return _workflow_engine
