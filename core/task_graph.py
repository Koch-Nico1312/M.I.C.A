"""Dependency-aware task graph execution with progress, retry and cancellation."""

from __future__ import annotations

import asyncio
import threading
import uuid
from copy import deepcopy
from datetime import datetime
from typing import Any, Awaitable, Callable


Runner = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]


class TaskGraphExecutor:
    def __init__(self, max_parallel: int = 4):
        self.max_parallel = max(1, int(max_parallel))
        self._graphs: dict[str, dict[str, Any]] = {}
        self._cancelled: set[str] = set()
        self._lock = threading.RLock()

    def create(self, steps: list[dict[str, Any]], *, name: str = "Task graph") -> dict[str, Any]:
        graph_id = f"graph-{uuid.uuid4().hex[:10]}"
        normalized = []
        known: set[str] = set()
        for index, raw in enumerate(steps):
            step_id = str(raw.get("id") or f"step-{index + 1}")
            if step_id in known:
                raise ValueError(f"duplicate step id: {step_id}")
            known.add(step_id)
            normalized.append(
                {
                    "id": step_id,
                    "tool": str(raw.get("tool") or raw.get("name") or "").strip(),
                    "args": dict(raw.get("args") or {}),
                    "depends_on": [str(item) for item in raw.get("depends_on", [])],
                    "reads": sorted({str(item) for item in raw.get("reads", [])}),
                    "writes": sorted({str(item) for item in raw.get("writes", [])}),
                    "max_retries": max(0, int(raw.get("max_retries", 0) or 0)),
                    "attempts": 0,
                    "status": "pending",
                    "result": None,
                    "error": None,
                }
            )
        for step in normalized:
            missing = set(step["depends_on"]) - known
            if missing:
                raise ValueError(f"unknown dependencies for {step['id']}: {sorted(missing)}")
            if not step["tool"]:
                raise ValueError(f"missing tool for {step['id']}")
        self._assert_acyclic(normalized)
        graph = {
            "id": graph_id,
            "name": str(name or "Task graph"),
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "steps": normalized,
        }
        with self._lock:
            self._graphs[graph_id] = graph
        return deepcopy(graph)

    async def execute(self, graph_id: str, runner: Runner) -> dict[str, Any]:
        graph = self._require(graph_id)
        graph["status"] = "running"
        semaphore = asyncio.Semaphore(self.max_parallel)

        async def run_step(step: dict[str, Any]) -> None:
            async with semaphore:
                if graph_id in self._cancelled:
                    step["status"] = "cancelled"
                    return
                step["status"] = "running"
                while step["attempts"] <= step["max_retries"]:
                    step["attempts"] += 1
                    try:
                        result = await runner(step["tool"], dict(step["args"]))
                        step["result"] = result
                        if result.get("success", True):
                            step["status"] = "completed"
                            step["error"] = None
                            return
                        step["error"] = str(result.get("error") or result.get("result") or "failed")
                    except Exception as exc:
                        step["error"] = str(exc)
                    if step["attempts"] <= step["max_retries"]:
                        step["status"] = "retrying"
                        await asyncio.sleep(0)
                step["status"] = "failed"

        while True:
            if graph_id in self._cancelled:
                for step in graph["steps"]:
                    if step["status"] == "pending":
                        step["status"] = "cancelled"
                graph["status"] = "cancelled"
                break
            pending = [step for step in graph["steps"] if step["status"] == "pending"]
            if not pending:
                break
            completed = {step["id"] for step in graph["steps"] if step["status"] == "completed"}
            failed = {step["id"] for step in graph["steps"] if step["status"] in {"failed", "cancelled", "blocked"}}
            ready = [
                step
                for step in pending
                if set(step["depends_on"]) <= completed and not (set(step["depends_on"]) & failed)
            ]
            for step in pending:
                if set(step["depends_on"]) & failed:
                    step["status"] = "blocked"
                    step["error"] = "dependency failed"
            batch = self._compatible_batch(ready)
            if not batch:
                if any(step["status"] == "pending" for step in graph["steps"]):
                    raise RuntimeError("task graph made no progress")
                break
            await asyncio.gather(*(run_step(step) for step in batch))
            graph["updated_at"] = datetime.now().isoformat()

        statuses = {step["status"] for step in graph["steps"]}
        if graph["status"] != "cancelled":
            graph["status"] = "failed" if statuses & {"failed", "blocked"} else "completed"
        graph["updated_at"] = datetime.now().isoformat()
        return deepcopy(graph)

    def cancel(self, graph_id: str) -> dict[str, Any]:
        self._require(graph_id)
        self._cancelled.add(graph_id)
        return self.get(graph_id)

    def retry_failed(self, graph_id: str) -> dict[str, Any]:
        graph = self._require(graph_id)
        self._cancelled.discard(graph_id)
        for step in graph["steps"]:
            if step["status"] in {"failed", "blocked", "cancelled"}:
                step["status"] = "pending"
                step["error"] = None
        graph["status"] = "pending"
        graph["updated_at"] = datetime.now().isoformat()
        return deepcopy(graph)

    def get(self, graph_id: str) -> dict[str, Any]:
        return deepcopy(self._require(graph_id))

    def list(self, limit: int = 20) -> dict[str, Any]:
        with self._lock:
            graphs = list(self._graphs.values())[-max(1, int(limit)) :]
            return {"items": deepcopy(list(reversed(graphs)))}

    def _require(self, graph_id: str) -> dict[str, Any]:
        with self._lock:
            graph = self._graphs.get(graph_id)
            if graph is None:
                raise ValueError("unknown task graph")
            return graph

    def _compatible_batch(self, ready: list[dict[str, Any]]) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []
        reads: set[str] = set()
        writes: set[str] = set()
        for step in ready:
            step_reads = set(step["reads"])
            step_writes = set(step["writes"])
            if step_writes & (reads | writes) or step_reads & writes:
                continue
            selected.append(step)
            reads.update(step_reads)
            writes.update(step_writes)
            if len(selected) >= self.max_parallel:
                break
        return selected or ready[:1]

    @staticmethod
    def _assert_acyclic(steps: list[dict[str, Any]]) -> None:
        dependencies = {step["id"]: set(step["depends_on"]) for step in steps}
        resolved: set[str] = set()
        while len(resolved) < len(steps):
            ready = {name for name, deps in dependencies.items() if name not in resolved and deps <= resolved}
            if not ready:
                raise ValueError("task graph contains a cycle")
            resolved.update(ready)


_task_graph_executor: TaskGraphExecutor | None = None


def get_task_graph_executor() -> TaskGraphExecutor:
    global _task_graph_executor
    if _task_graph_executor is None:
        _task_graph_executor = TaskGraphExecutor()
    return _task_graph_executor
