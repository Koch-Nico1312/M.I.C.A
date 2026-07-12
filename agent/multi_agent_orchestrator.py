"""
Multi-Agent Orchestrator from OpenSwarm
========================================
Implements multi-agent delegation for complex tasks.
Allows the main Jarvis agent to spawn specialized sub-agents that work asynchronously.
"""

import json
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import google.generativeai as genai

from agent.executor import AgentExecutor
from agent.planner import create_plan
from agent.role_profiles import get_role_profile


class AgentType(Enum):
    """Types of specialized agents."""

    DEEP_RESEARCH = "deep_research"
    DATA_ANALYST = "data_analyst"
    CODE_EXPERT = "code_expert"
    WEB_SCRAPER = "web_scraper"
    FILE_MANAGER = "file_manager"
    GENERAL = "general"


@dataclass
class AgentTask:
    """A task to be delegated to a sub-agent."""

    task_id: str
    agent_type: AgentType
    goal: str
    context: str = ""
    priority: int = 5
    dependencies: List[str] = field(default_factory=list)
    status: str = "pending"
    result: Optional[str] = None
    error: Optional[str] = None
    profile_id: str = ""


@dataclass
class AgentResult:
    """Result from a sub-agent."""

    task_id: str
    agent_type: AgentType
    success: bool
    result: Optional[str] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    profile_id: str = ""
    model_intent: str = ""
    allowed_tools: tuple[str, ...] = ()


@dataclass
class CrewRole:
    """CrewAI-inspired role definition for a Jarvis-native crew."""

    name: str
    agent_type: AgentType
    goal: str
    backstory: str = ""
    allow_delegation: bool = False


@dataclass
class CrewTask:
    """Crew task with role assignment, dependencies, and approval gates."""

    id: str
    description: str
    role: str
    expected_output: str = ""
    depends_on: list[str] = field(default_factory=list)
    requires_human_input: bool = False
    status: str = "pending"
    result: str = ""


@dataclass
class CrewCheckpoint:
    """Durable crew checkpoint for pause/resume and audit."""

    timestamp: str
    status: str
    note: str
    tasks: list[dict[str, Any]]


@dataclass
class CrewFlow:
    """Jarvis-native crew/flow record inspired by CrewAI patterns."""

    id: str
    goal: str
    roles: list[CrewRole]
    tasks: list[CrewTask]
    process: str = "sequential"
    status: str = "ready"
    checkpoints: list[CrewCheckpoint] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


class SubAgent:
    """A specialized sub-agent for handling specific task types."""

    def __init__(self, agent_type: AgentType, speak: Callable | None = None, profile_id: str = ""):
        self.agent_type = agent_type
        self.speak = speak
        self.executor = AgentExecutor()
        self.profile = get_role_profile(profile_id, agent_type=agent_type.value)

    def execute_task(self, task: AgentTask) -> AgentResult:
        """Execute a delegated task."""
        start_time = time.time()

        try:
            print(f"[{self.agent_type.value.upper()} Agent] 🎯 Executing: {task.goal}")

            if self.speak:
                self.speak(f"Delegating to {self.agent_type.value} agent.")

            delegated_goal = (
                f"{self.profile.system_prompt}\n\nDelegated goal: {task.goal}\n"
                f"Context: {task.context}\nExpected output: {self.profile.expected_output}"
            )
            result = self.executor.execute(
                goal=delegated_goal,
                speak=self.speak,
                allowed_tools=set(self.profile.allowed_tools),
                system_prompt=self.profile.system_prompt,
                model_intent=self.profile.model_intent,
            )

            execution_time = time.time() - start_time

            return AgentResult(
                task_id=task.task_id,
                agent_type=self.agent_type,
                success=True,
                result=result,
                execution_time=execution_time,
                profile_id=self.profile.id,
                model_intent=self.profile.model_intent,
                allowed_tools=self.profile.allowed_tools,
            )

        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)
            print(f"[{self.agent_type.value.upper()} Agent] ❌ Failed: {error_msg}")

            return AgentResult(
                task_id=task.task_id,
                agent_type=self.agent_type,
                success=False,
                error=error_msg,
                execution_time=execution_time,
                profile_id=self.profile.id,
                model_intent=self.profile.model_intent,
                allowed_tools=self.profile.allowed_tools,
            )


class MultiAgentOrchestrator:
    """
    Orchestrates multiple agents to work on complex tasks in parallel.
    Implements the OpenSwarm multi-agent delegation pattern.
    """

    def __init__(self, max_workers: int = 3, speak: Callable | None = None):
        self.max_workers = max_workers
        self.speak = speak
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.active_tasks: Dict[str, AgentTask] = {}
        self.completed_results: Dict[str, AgentResult] = {}
        self.crews: Dict[str, CrewFlow] = {}
        self.task_counter = 0

    def _generate_task_id(self) -> str:
        """Generate a unique task ID."""
        self.task_counter += 1
        return f"task_{self.task_counter}"

    def _determine_agent_type(self, goal: str) -> AgentType:
        """Determine the best agent type for a given goal."""
        goal_lower = goal.lower()

        # Research-related tasks
        if any(
            keyword in goal_lower
            for keyword in ["research", "search", "find information", "investigate", "analyze data"]
        ):
            return AgentType.DEEP_RESEARCH

        # Data analysis tasks
        elif any(
            keyword in goal_lower
            for keyword in ["analyze", "data", "statistics", "calculate", "spreadsheet", "table"]
        ):
            return AgentType.DATA_ANALYST

        # Code-related tasks
        elif any(
            keyword in goal_lower
            for keyword in ["code", "programming", "debug", "implement", "function", "script"]
        ):
            return AgentType.CODE_EXPERT

        # Web scraping tasks
        elif any(
            keyword in goal_lower
            for keyword in ["scrape", "crawl", "extract from web", "download from"]
        ):
            return AgentType.WEB_SCRAPER

        # File management tasks
        elif any(
            keyword in goal_lower
            for keyword in ["file", "folder", "directory", "organize", "delete", "move"]
        ):
            return AgentType.FILE_MANAGER

        # Default to general agent
        else:
            return AgentType.GENERAL

    def create_crew(
        self,
        goal: str,
        *,
        roles: list[dict[str, Any]] | None = None,
        tasks: list[dict[str, Any]] | None = None,
        process: str = "sequential",
    ) -> CrewFlow:
        """Create a CrewAI-inspired Jarvis-native crew flow."""
        goal = str(goal or "").strip()
        if not goal:
            raise ValueError("goal is required")

        role_defs = self._build_crew_roles(goal, roles)
        task_defs = self._build_crew_tasks(goal, role_defs, tasks)
        flow = CrewFlow(
            id=f"crew-{uuid.uuid4().hex[:8]}",
            goal=goal,
            roles=role_defs,
            tasks=task_defs,
            process=process if process in {"sequential", "hierarchical"} else "sequential",
        )
        flow.checkpoints.append(self._checkpoint(flow, "created", "Crew flow created."))
        self.crews[flow.id] = flow
        return flow

    def run_crew(self, crew_id: str, *, stop_before_human_input: bool = True) -> CrewFlow:
        """Run ready crew tasks and checkpoint progress."""
        flow = self._require_crew(crew_id)
        flow.status = "running"
        for task in flow.tasks:
            if task.status != "pending":
                continue
            if not self._crew_dependencies_done(flow, task):
                continue
            if task.requires_human_input and stop_before_human_input:
                task.status = "waiting_for_human"
                flow.status = "waiting_for_human"
                flow.checkpoints.append(
                    self._checkpoint(flow, "waiting_for_human", f"Task requires human input: {task.id}")
                )
                flow.updated_at = datetime.now().isoformat()
                return flow

            role = self._role_for_task(flow, task)
            delegated = AgentTask(
                task_id=task.id,
                agent_type=role.agent_type,
                goal=f"{task.description}\nExpected output: {task.expected_output}".strip(),
                context=f"Crew goal: {flow.goal}\nRole: {role.name}\nBackstory: {role.backstory}",
                profile_id={"planner": "planner", "reviewer": "review"}.get(role.name.lower(), ""),
            )
            result = self.execute_task_sync(delegated)
            task.status = "completed" if result.success else "failed"
            task.result = result.result or result.error or ""
            flow.checkpoints.append(
                self._checkpoint(flow, task.status, f"Task {task.id}: {task.status}")
            )
            if not result.success:
                flow.status = "blocked"
                flow.updated_at = datetime.now().isoformat()
                return flow

        flow.status = "completed" if all(task.status == "completed" for task in flow.tasks) else "running"
        flow.updated_at = datetime.now().isoformat()
        flow.checkpoints.append(self._checkpoint(flow, flow.status, "Crew run advanced."))
        return flow

    def approve_crew_task(self, crew_id: str, task_id: str, note: str = "") -> CrewFlow:
        """Release a human-input gate for a crew task."""
        flow = self._require_crew(crew_id)
        task = next((item for item in flow.tasks if item.id == task_id), None)
        if not task:
            raise ValueError("unknown crew task")
        if task.status == "waiting_for_human":
            task.status = "pending"
            task.requires_human_input = False
            flow.status = "ready"
            flow.checkpoints.append(self._checkpoint(flow, "approved", note or f"Approved {task_id}"))
            flow.updated_at = datetime.now().isoformat()
        return flow

    def get_crew(self, crew_id: str) -> dict[str, Any]:
        return self._crew_to_dict(self._require_crew(crew_id))

    def _build_crew_roles(self, goal: str, roles: list[dict[str, Any]] | None) -> list[CrewRole]:
        if roles:
            built = []
            for role in roles:
                agent_type = str(role.get("agent_type") or role.get("type") or "general")
                try:
                    typed = AgentType(agent_type)
                except ValueError:
                    typed = self._determine_agent_type(str(role.get("goal") or goal))
                built.append(
                    CrewRole(
                        name=str(role.get("name") or typed.value),
                        agent_type=typed,
                        goal=str(role.get("goal") or goal),
                        backstory=str(role.get("backstory") or ""),
                        allow_delegation=bool(role.get("allow_delegation", False)),
                    )
                )
            return built
        return [
            CrewRole("Planner", AgentType.GENERAL, "Break the goal into safe, checkable work."),
            CrewRole("Specialist", self._determine_agent_type(goal), "Execute the core task."),
            CrewRole("Reviewer", AgentType.CODE_EXPERT, "Check outputs and risks before completion."),
        ]

    def _build_crew_tasks(
        self,
        goal: str,
        roles: list[CrewRole],
        tasks: list[dict[str, Any]] | None,
    ) -> list[CrewTask]:
        if tasks:
            return [
                CrewTask(
                    id=str(task.get("id") or f"crew-task-{index + 1}"),
                    description=str(task.get("description") or task.get("goal") or ""),
                    role=str(task.get("role") or roles[min(index, len(roles) - 1)].name),
                    expected_output=str(task.get("expected_output") or ""),
                    depends_on=list(task.get("depends_on") or ([] if index == 0 else [f"crew-task-{index}"])),
                    requires_human_input=bool(task.get("requires_human_input", False)),
                )
                for index, task in enumerate(tasks)
                if str(task.get("description") or task.get("goal") or "").strip()
            ]
        return [
            CrewTask("crew-task-1", f"Plan: {goal}", roles[0].name, "A concise task plan."),
            CrewTask(
                "crew-task-2",
                f"Execute: {goal}",
                roles[1].name,
                "A concrete result for the user goal.",
                depends_on=["crew-task-1"],
            ),
            CrewTask(
                "crew-task-3",
                f"Review: {goal}",
                roles[2].name,
                "Risks, verification notes, and final readiness.",
                depends_on=["crew-task-2"],
                requires_human_input=True,
            ),
        ]

    def _role_for_task(self, flow: CrewFlow, task: CrewTask) -> CrewRole:
        return next((role for role in flow.roles if role.name == task.role), flow.roles[0])

    def _crew_dependencies_done(self, flow: CrewFlow, task: CrewTask) -> bool:
        done = {item.id for item in flow.tasks if item.status == "completed"}
        return all(dep in done for dep in task.depends_on)

    def _checkpoint(self, flow: CrewFlow, status: str, note: str) -> CrewCheckpoint:
        return CrewCheckpoint(
            timestamp=datetime.now().isoformat(),
            status=status,
            note=note,
            tasks=[
                {
                    "id": task.id,
                    "role": task.role,
                    "status": task.status,
                    "requires_human_input": task.requires_human_input,
                }
                for task in flow.tasks
            ],
        )

    def _require_crew(self, crew_id: str) -> CrewFlow:
        flow = self.crews.get(crew_id)
        if not flow:
            raise ValueError("unknown crew")
        return flow

    def _crew_to_dict(self, flow: CrewFlow) -> dict[str, Any]:
        return {
            "id": flow.id,
            "goal": flow.goal,
            "process": flow.process,
            "status": flow.status,
            "created_at": flow.created_at,
            "updated_at": flow.updated_at,
            "roles": [
                {
                    "name": role.name,
                    "agent_type": role.agent_type.value,
                    "goal": role.goal,
                    "backstory": role.backstory,
                    "allow_delegation": role.allow_delegation,
                }
                for role in flow.roles
            ],
            "tasks": [
                {
                    "id": task.id,
                    "description": task.description,
                    "role": task.role,
                    "expected_output": task.expected_output,
                    "depends_on": task.depends_on,
                    "requires_human_input": task.requires_human_input,
                    "status": task.status,
                    "result": task.result,
                }
                for task in flow.tasks
            ],
            "checkpoints": [
                {
                    "timestamp": checkpoint.timestamp,
                    "status": checkpoint.status,
                    "note": checkpoint.note,
                    "tasks": checkpoint.tasks,
                }
                for checkpoint in flow.checkpoints
            ],
        }

    def delegate_task(self, goal: str, context: str = "", priority: int = 5) -> str:
        """
        Delegate a task to an appropriate sub-agent.

        Returns the task ID for tracking.
        """
        task_id = self._generate_task_id()
        agent_type = self._determine_agent_type(goal)

        task = AgentTask(
            task_id=task_id, agent_type=agent_type, goal=goal, context=context, priority=priority
        )

        self.active_tasks[task_id] = task
        print(f"[Orchestrator] 📋 Delegated task {task_id} to {agent_type.value} agent")

        return task_id

    def delegate_complex_task(self, main_goal: str) -> List[str]:
        """
        Break down a complex task into sub-tasks and delegate them.

        Returns list of task IDs.
        """
        # Create a plan for the complex task
        plan = create_plan(main_goal)
        task_ids = []

        for step in plan.get("steps", []):
            step_goal = step.get("description", "")
            if step_goal:
                task_id = self.delegate_task(step_goal)
                task_ids.append(task_id)

        print(f"[Orchestrator] 🎯 Delegated {len(task_ids)} sub-tasks for complex goal")
        return task_ids

    def execute_task_sync(self, task: AgentTask) -> AgentResult:
        """Execute a task synchronously."""
        agent = SubAgent(task.agent_type, self.speak, task.profile_id)
        return agent.execute_task(task)

    def execute_all_async(
        self, task_ids: List[str], timeout: float = 300.0
    ) -> Dict[str, AgentResult]:
        """
        Execute all delegated tasks asynchronously.

        Returns a dictionary mapping task IDs to results.
        """
        futures = {}
        results = {}

        # Submit all tasks to the executor
        for task_id in task_ids:
            if task_id not in self.active_tasks:
                continue

            task = self.active_tasks[task_id]
            future = self.executor.submit(self.execute_task_sync, task)
            futures[future] = task_id

        # Wait for all tasks to complete
        for future in as_completed(futures, timeout=timeout):
            task_id = futures[future]
            try:
                result = future.result()
                results[task_id] = result
                self.completed_results[task_id] = result

                # Update task status
                if task_id in self.active_tasks:
                    self.active_tasks[task_id].status = "completed" if result.success else "failed"
                    self.active_tasks[task_id].result = result.result
                    self.active_tasks[task_id].error = result.error

            except Exception as e:
                error_msg = str(e)
                results[task_id] = AgentResult(
                    task_id=task_id,
                    agent_type=self.active_tasks[task_id].agent_type,
                    success=False,
                    error=error_msg,
                )
                print(f"[Orchestrator] ❌ Task {task_id} raised exception: {error_msg}")

        return results

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get the status of a specific task."""
        if task_id in self.completed_results:
            result = self.completed_results[task_id]
            return {
                "task_id": task_id,
                "status": "completed" if result.success else "failed",
                "result": result.result,
                "error": result.error,
                "execution_time": result.execution_time,
                "profile_id": result.profile_id,
                "model_intent": result.model_intent,
                "allowed_tools": list(result.allowed_tools),
            }
        elif task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            return {
                "task_id": task_id,
                "status": task.status,
                "agent_type": task.agent_type.value,
                "profile_id": task.profile_id or get_role_profile(agent_type=task.agent_type.value).id,
                "goal": task.goal,
            }
        else:
            return {"task_id": task_id, "status": "not_found"}

    def get_all_statuses(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all tasks."""
        statuses = {}
        for task_id in self.active_tasks:
            statuses[task_id] = self.get_task_status(task_id)
        return statuses

    def combine_results(self, task_ids: List[str], main_goal: str) -> str:
        """
        Combine results from multiple sub-tasks into a cohesive summary.
        """
        results_text = []

        for task_id in task_ids:
            status = self.get_task_status(task_id)
            if status.get("status") == "completed":
                result = status.get("result", "")
                if result:
                    results_text.append(f"- {result}")

        if not results_text:
            return "All sub-tasks failed to complete."

        combined = "\n".join(results_text)

        # Use AI to create a cohesive summary
        try:

            def get_base_dir() -> Path:
                if getattr(sys, "frozen", False):
                    return Path(sys.executable).parent
                return Path(__file__).resolve().parent.parent

            BASE_DIR = get_base_dir()
            API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

            with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
                api_key = json.load(f)["gemini_api_key"]

            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name="gemini-2.5-flash-lite")

            prompt = f"""
Main Goal: {main_goal}

Results from sub-tasks:
{combined}

Create a concise, natural summary of what was accomplished. Address the user as 'sir'.
"""
            response = model.generate_content(prompt)
            summary = response.text.strip()

            if self.speak:
                self.speak(summary)

            return summary

        except Exception as e:
            print(f"[Orchestrator] ⚠️ Summary generation failed: {e}")
            return combined

    def shutdown(self):
        """Shutdown the orchestrator and clean up resources."""
        self.executor.shutdown(wait=True)
        print("[Orchestrator] 🔒 Shutdown complete")


# Global instance management
_orchestrator: Optional[MultiAgentOrchestrator] = None
_orchestrator_lock = threading.Lock()


def get_orchestrator(speak: Callable | None = None) -> MultiAgentOrchestrator:
    """Get the global multi-agent orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        with _orchestrator_lock:
            if _orchestrator is None:
                _orchestrator = MultiAgentOrchestrator(speak=speak)
    return _orchestrator


__all__ = [
    "MultiAgentOrchestrator",
    "SubAgent",
    "AgentTask",
    "AgentResult",
    "AgentType",
    "CrewRole",
    "CrewTask",
    "CrewFlow",
    "CrewCheckpoint",
    "get_orchestrator",
]
