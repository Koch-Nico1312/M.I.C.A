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
    role: str = "general"
    expected_output: str = ""
    requires_human_input: bool = False
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
    process: str = "sequential"
    checkpoints: list[VerificationRecord] = field(default_factory=list)
    budget: dict[str, Any] = field(default_factory=dict)
    origin_id: str = ""
    origin_relation: str = ""


def _now() -> str:
    return datetime.now().isoformat()


class TaskPipelineManager:
    def __init__(self, path: Path = PIPELINE_PATH):
        self.path = path
        self._lock = threading.RLock()
        self._pipelines: dict[str, TaskPipeline] = {}
        self._load()

    def create_pipeline(
        self,
        goal: str,
        steps: list[str] | None = None,
        budget: dict[str, Any] | None = None,
        *,
        origin_id: str = "",
        origin_relation: str = "",
    ) -> TaskPipeline:
        goal = str(goal or "").strip()
        if not goal:
            raise ValueError("goal is required")
        step_titles = [step.strip() for step in (steps or []) if str(step).strip()]
        if not step_titles:
            step_titles = self._derive_steps(goal)
        now = _now()
        normalized_budget = self._normalize_budget(budget)
        step_limit = normalized_budget.get("max_steps", 8)
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
                    role=self._role_for_step(title),
                    expected_output=self._expected_output_for_step(title),
                    requires_human_input=index == len(step_titles[:step_limit]) - 1 and self._looks_risky(goal),
                )
                for index, title in enumerate(step_titles[:step_limit])
            ],
            requires_approval=self._looks_risky(goal),
            checkpoints=[VerificationRecord(timestamp=now, status="created", note="Pipeline created.")],
            budget=normalized_budget,
            origin_id=str(origin_id or ""),
            origin_relation=str(origin_relation or ""),
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

    def restore(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        raw_items = snapshot.get("pipelines", []) if isinstance(snapshot, dict) else []
        restored: dict[str, TaskPipeline] = {}
        for raw in raw_items:
            if not isinstance(raw, dict) or not raw.get("id") or not raw.get("goal"):
                continue
            pipeline = self._from_dict(raw)
            restored[pipeline.id] = pipeline
        with self._lock:
            self._pipelines = restored
            self._save()
            return {"pipelines": self.list_pipelines()}

    def advance(self, pipeline_id: str, note: str = "") -> dict[str, Any]:
        with self._lock:
            pipeline = self._require(pipeline_id)
            if pipeline.status == "paused":
                raise ValueError("pipeline is paused")
            if self._budget_exceeded(pipeline):
                pipeline.status = "budget_exceeded"
                pipeline.updated_at = _now()
                pipeline.checkpoints.append(VerificationRecord(timestamp=pipeline.updated_at, status="budget_exceeded", note="Persönliche Laufgrenze erreicht."))
                self._save()
                return self._to_dict(pipeline)
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
            pipeline.checkpoints.append(
                VerificationRecord(timestamp=_now(), status=pipeline.status, note=f"Advanced {next_step.id}.")
            )
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
            pipeline.checkpoints.append(
                VerificationRecord(timestamp=_now(), status=status, note=f"Verified {step_id}: {note}")
            )
            pipeline.updated_at = _now()
            self._save()
            return self._to_dict(pipeline)

    def clone(self, pipeline_id: str, relation: str = "duplicate") -> dict[str, Any]:
        with self._lock:
            source = self._require(pipeline_id)
            relation = relation if relation in {"duplicate", "rerun"} else "duplicate"
            clone = self.create_pipeline(
                source.goal,
                steps=[step.title for step in source.steps],
                budget=dict(source.budget),
                origin_id=source.id,
                origin_relation=relation,
            )
            clone.checkpoints.append(VerificationRecord(
                timestamp=_now(), status=relation,
                note="Lauf erneut gestartet." if relation == "rerun" else "Aufgabe dupliziert.",
            ))
            clone.updated_at = _now()
            self._save()
            return self._to_dict(clone)

    def delete(self, pipeline_id: str) -> dict[str, Any]:
        with self._lock:
            pipeline = self._require(pipeline_id)
            removed = self._to_dict(pipeline)
            del self._pipelines[pipeline_id]
            self._save()
            return removed

    def retry_step(self, pipeline_id: str, step_id: str, note: str = "") -> dict[str, Any]:
        with self._lock:
            pipeline = self._require(pipeline_id)
            index = self._step_index(pipeline, step_id)
            target = pipeline.steps[index]
            if target.status not in {"failed", "blocked"}:
                raise ValueError("only failed or blocked steps can be retried")
            for step in pipeline.steps[index:]:
                step.status = "pending"
            now = _now()
            target.verification.append(VerificationRecord(timestamp=now, status="retry", note=note or "Schritt für erneuten Versuch zurückgesetzt."))
            pipeline.status = "ready"
            pipeline.updated_at = now
            pipeline.checkpoints.append(VerificationRecord(timestamp=now, status="retry", note=f"Retry ab {step_id}: {note or 'erneuter Versuch'}"))
            self._save()
            return self._to_dict(pipeline)

    def rollback_to_step(self, pipeline_id: str, step_id: str, note: str = "") -> dict[str, Any]:
        with self._lock:
            pipeline = self._require(pipeline_id)
            index = self._step_index(pipeline, step_id)
            checkpoint_step = pipeline.steps[index]
            if checkpoint_step.status != "completed":
                raise ValueError("rollback target must be a completed step")
            for step in pipeline.steps[index + 1:]:
                step.status = "pending"
            now = _now()
            pipeline.status = "ready" if index + 1 < len(pipeline.steps) else "completed"
            pipeline.updated_at = now
            pipeline.checkpoints.append(VerificationRecord(timestamp=now, status="rollback", note=f"Rücksprung auf {step_id}: {note or checkpoint_step.title}"))
            self._save()
            return self._to_dict(pipeline)

    @staticmethod
    def _step_index(pipeline: TaskPipeline, step_id: str) -> int:
        for index, step in enumerate(pipeline.steps):
            if step.id == step_id:
                return index
        raise ValueError("unknown step")

    def pause(self, pipeline_id: str) -> dict[str, Any]:
        return self._set_status(pipeline_id, "paused")

    def resume(self, pipeline_id: str) -> dict[str, Any]:
        with self._lock:
            pipeline = self._require(pipeline_id)
            if self._budget_exceeded(pipeline):
                raise ValueError("Laufgrenze erreicht; Budget vor dem Fortsetzen erhöhen")
        return self._set_status(pipeline_id, "ready")

    @staticmethod
    def _normalize_budget(budget: dict[str, Any] | None) -> dict[str, Any]:
        raw = budget if isinstance(budget, dict) else {}
        return {
            "max_steps": max(1, min(50, int(raw.get("max_steps", 8)))),
            "max_minutes": max(1, min(1440, int(raw.get("max_minutes", 60)))),
            "max_agent_calls": max(1, min(500, int(raw.get("max_agent_calls", 20)))),
            "stop_on_limit": bool(raw.get("stop_on_limit", True)),
        }

    @staticmethod
    def _budget_usage(pipeline: TaskPipeline) -> dict[str, Any]:
        completed = len([step for step in pipeline.steps if step.status == "completed"])
        try:
            elapsed = max(0, int((datetime.now() - datetime.fromisoformat(pipeline.created_at)).total_seconds() / 60))
        except ValueError:
            elapsed = 0
        return {"completed_steps": completed, "elapsed_minutes": elapsed, "agent_calls": completed}

    def _budget_exceeded(self, pipeline: TaskPipeline) -> bool:
        budget = pipeline.budget or self._normalize_budget(None)
        if not budget.get("stop_on_limit", True):
            return False
        usage = self._budget_usage(pipeline)
        return usage["elapsed_minutes"] >= int(budget.get("max_minutes", 60)) or usage["agent_calls"] >= int(budget.get("max_agent_calls", 20))

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
    def _role_for_step(title: str) -> str:
        raw = title.lower()
        if any(token in raw for token in ("plan", "zerlegen", "kontext")):
            return "planner"
        if any(token in raw for token in ("verifiz", "review", "pruef", "prüf")):
            return "reviewer"
        if any(token in raw for token in ("code", "implement", "datei", "file")):
            return "specialist"
        return "executor"

    @staticmethod
    def _expected_output_for_step(title: str) -> str:
        role = TaskPipelineManager._role_for_step(title)
        outputs = {
            "planner": "A concise plan with dependencies and risk notes.",
            "reviewer": "Verification notes, failures, and readiness signal.",
            "specialist": "A concrete implementation artifact or change summary.",
            "executor": "A completed step result with evidence.",
        }
        return outputs[role]

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
                pipeline = self._from_dict(item)
                self._pipelines[pipeline.id] = pipeline
        except Exception:
            self._pipelines = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"pipelines": [self._to_dict(item) for item in self._pipelines.values()]}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    @classmethod
    def _to_dict(cls, pipeline: TaskPipeline) -> dict[str, Any]:
        payload = asdict(pipeline)
        payload["budget_usage"] = cls._budget_usage(pipeline)
        payload["budget_exceeded"] = cls._budget_exceeded_for_payload(pipeline)
        return payload

    @classmethod
    def _budget_exceeded_for_payload(cls, pipeline: TaskPipeline) -> bool:
        budget = pipeline.budget or cls._normalize_budget(None)
        if not budget.get("stop_on_limit", True):
            return False
        usage = cls._budget_usage(pipeline)
        return usage["elapsed_minutes"] >= int(budget.get("max_minutes", 60)) or usage["agent_calls"] >= int(budget.get("max_agent_calls", 20))

    @staticmethod
    def _from_dict(item: dict[str, Any]) -> TaskPipeline:
        steps = [
            PipelineStep(
                id=step["id"], title=step["title"], status=step.get("status", "pending"),
                depends_on=list(step.get("depends_on", [])), role=step.get("role", "general"),
                expected_output=step.get("expected_output", ""),
                requires_human_input=bool(step.get("requires_human_input", False)),
                verification=[VerificationRecord(**record) for record in step.get("verification", []) if isinstance(record, dict)],
            )
            for step in item.get("steps", []) if isinstance(step, dict) and step.get("id") and step.get("title")
        ]
        return TaskPipeline(
            id=item["id"], goal=item["goal"], status=item.get("status", "ready"),
            created_at=item.get("created_at", _now()), updated_at=item.get("updated_at", _now()), steps=steps,
            requires_approval=bool(item.get("requires_approval", False)), process=item.get("process", "sequential"),
            checkpoints=[VerificationRecord(**record) for record in item.get("checkpoints", []) if isinstance(record, dict)],
            budget=TaskPipelineManager._normalize_budget(item.get("budget")),
            origin_id=str(item.get("origin_id") or ""),
            origin_relation=str(item.get("origin_relation") or ""),
        )


_manager: TaskPipelineManager | None = None
_manager_lock = threading.Lock()


def get_task_pipeline_manager() -> TaskPipelineManager:
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = TaskPipelineManager()
    return _manager
