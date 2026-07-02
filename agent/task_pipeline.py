"""Task agent pipelines with visible steps and verification records."""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
PIPELINE_PATH = BASE_DIR / "data" / "task_pipelines.json"


@dataclass
class VerificationRecord:
    timestamp: str
    status: str
    note: str


@dataclass
class PipelineStep:
    id: str
    title: str
    status: str = "pending"
    depends_on: list[str] = field(default_factory=list)
    verification: list[VerificationRecord] = field(default_factory=list)


@dataclass
class TaskPipeline:
    id: str
    goal: str
    status: str
    created_at: str
    updated_at: str
    steps: list[PipelineStep]
    requires_approval: bool = False


def _now() -> str:
    return datetime.now().isoformat()


class TaskPipelineManager:
    def __init__(self, path: Path = PIPELINE_PATH):
        self.path = path
        self._lock = threading.RLock()
        self._pipelines: dict[str, TaskPipeline] = {}
        self._load()

    def create_pipeline(self, goal: str, steps: list[str] | None = None) -> TaskPipeline:
        goal = str(goal or "").strip()
        if not goal:
            raise ValueError("goal is required")
        step_titles = [step.strip() for step in (steps or []) if str(step).strip()]
        if not step_titles:
            step_titles = self._derive_steps(goal)
        now = _now()
        pipeline = TaskPipeline(
            id=f"pipe-{uuid.uuid4().hex[:8]}",
            goal=goal,
            status="ready",
            created_at=now,
            updated_at=now,
            steps=[
                PipelineStep(
                    id=f"step-{index + 1}",
                    title=title,
                    depends_on=[f"step-{index}"] if index else [],
                )
                for index, title in enumerate(step_titles[:8])
            ],
            requires_approval=self._looks_risky(goal),
        )
        with self._lock:
            self._pipelines[pipeline.id] = pipeline
            self._save()
        return pipeline

    def list_pipelines(self) -> list[dict[str, Any]]:
        with self._lock:
            return [self._to_dict(item) for item in self._pipelines.values()]

    def get_pipeline(self, pipeline_id: str) -> dict[str, Any] | None:
        with self._lock:
            pipeline = self._pipelines.get(pipeline_id)
            return self._to_dict(pipeline) if pipeline else None

    def advance(self, pipeline_id: str, note: str = "") -> dict[str, Any]:
        with self._lock:
            pipeline = self._require(pipeline_id)
            if pipeline.status == "paused":
                raise ValueError("pipeline is paused")
            next_step = self._next_ready_step(pipeline)
            if not next_step:
                pipeline.status = "completed"
                pipeline.updated_at = _now()
                self._save()
                return self._to_dict(pipeline)
            next_step.status = "completed"
            next_step.verification.append(
                VerificationRecord(timestamp=_now(), status="passed", note=note or "Step marked complete.")
            )
            pipeline.status = "completed" if not self._next_ready_step(pipeline) else "running"
            pipeline.updated_at = _now()
            self._save()
            return self._to_dict(pipeline)

    def verify_step(self, pipeline_id: str, step_id: str, status: str, note: str) -> dict[str, Any]:
        with self._lock:
            pipeline = self._require(pipeline_id)
            step = next((item for item in pipeline.steps if item.id == step_id), None)
            if not step:
                raise ValueError("unknown step")
            status = status if status in {"passed", "failed", "blocked"} else "passed"
            step.verification.append(VerificationRecord(timestamp=_now(), status=status, note=str(note or "")))
            if status == "failed":
                step.status = "failed"
                pipeline.status = "blocked"
            elif status == "blocked":
                step.status = "blocked"
                pipeline.status = "blocked"
            pipeline.updated_at = _now()
            self._save()
            return self._to_dict(pipeline)

    def pause(self, pipeline_id: str) -> dict[str, Any]:
        return self._set_status(pipeline_id, "paused")

    def resume(self, pipeline_id: str) -> dict[str, Any]:
        return self._set_status(pipeline_id, "ready")

    def _set_status(self, pipeline_id: str, status: str) -> dict[str, Any]:
        with self._lock:
            pipeline = self._require(pipeline_id)
            pipeline.status = status
            pipeline.updated_at = _now()
            self._save()
            return self._to_dict(pipeline)

    def _next_ready_step(self, pipeline: TaskPipeline) -> PipelineStep | None:
        completed = {step.id for step in pipeline.steps if step.status == "completed"}
        for step in pipeline.steps:
            if step.status == "pending" and all(dep in completed for dep in step.depends_on):
                return step
        return None

    def _derive_steps(self, goal: str) -> list[str]:
        fragments = [part.strip(" .") for part in goal.replace(" und ", ". ").split(".") if part.strip()]
        if len(fragments) >= 2:
            return fragments[:5]
        return [
            "Ziel und Kontext erfassen",
            "Umsetzung in kleine Schritte zerlegen",
            "Naechsten sicheren Schritt ausfuehren",
            "Ergebnis verifizieren und offene Punkte festhalten",
        ]

    @staticmethod
    def _looks_risky(goal: str) -> bool:
        raw = goal.lower()
        return any(marker in raw for marker in ("delete", "loesche", "remove", "send", "purchase", "admin"))

    def _require(self, pipeline_id: str) -> TaskPipeline:
        pipeline = self._pipelines.get(pipeline_id)
        if not pipeline:
            raise ValueError("unknown pipeline")
        return pipeline

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            for item in raw.get("pipelines", []):
                steps = [
                    PipelineStep(
                        id=step["id"],
                        title=step["title"],
                        status=step.get("status", "pending"),
                        depends_on=list(step.get("depends_on", [])),
                        verification=[
                            VerificationRecord(**record)
                            for record in step.get("verification", [])
                            if isinstance(record, dict)
                        ],
                    )
                    for step in item.get("steps", [])
                ]
                pipeline = TaskPipeline(
                    id=item["id"],
                    goal=item["goal"],
                    status=item.get("status", "ready"),
                    created_at=item.get("created_at", _now()),
                    updated_at=item.get("updated_at", _now()),
                    steps=steps,
                    requires_approval=bool(item.get("requires_approval", False)),
                )
                self._pipelines[pipeline.id] = pipeline
        except Exception:
            self._pipelines = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"pipelines": [self._to_dict(item) for item in self._pipelines.values()]}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    @staticmethod
    def _to_dict(pipeline: TaskPipeline) -> dict[str, Any]:
        return asdict(pipeline)


_manager: TaskPipelineManager | None = None
_manager_lock = threading.Lock()


def get_task_pipeline_manager() -> TaskPipelineManager:
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = TaskPipelineManager()
    return _manager
