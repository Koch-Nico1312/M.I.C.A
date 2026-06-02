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
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import google.generativeai as genai

from agent.executor import AgentExecutor
from agent.planner import create_plan


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


@dataclass
class AgentResult:
    """Result from a sub-agent."""

    task_id: str
    agent_type: AgentType
    success: bool
    result: Optional[str] = None
    error: Optional[str] = None
    execution_time: float = 0.0


class SubAgent:
    """A specialized sub-agent for handling specific task types."""

    def __init__(self, agent_type: AgentType, speak: Callable | None = None):
        self.agent_type = agent_type
        self.speak = speak
        self.executor = AgentExecutor()

    def execute_task(self, task: AgentTask) -> AgentResult:
        """Execute a delegated task."""
        start_time = time.time()

        try:
            print(f"[{self.agent_type.value.upper()} Agent] 🎯 Executing: {task.goal}")

            if self.speak:
                self.speak(f"Delegating to {self.agent_type.value} agent.")

            # Execute using the standard executor
            result = self.executor.execute(goal=task.goal, speak=self.speak)

            execution_time = time.time() - start_time

            return AgentResult(
                task_id=task.task_id,
                agent_type=self.agent_type,
                success=True,
                result=result,
                execution_time=execution_time,
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
        agent = SubAgent(task.agent_type, self.speak)
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
            }
        elif task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            return {
                "task_id": task_id,
                "status": task.status,
                "agent_type": task.agent_type.value,
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
    "get_orchestrator",
]
