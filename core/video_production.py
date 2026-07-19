"""Persistent, approval-gated video production state for M.I.C.A."""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paths import project_path


VIDEO_PRODUCTION_PATH = project_path("data", "video_productions.json")
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
MAX_EVAL_PASSES = 3


def _now() -> str:
    return datetime.now().isoformat()


@dataclass
class VideoProduction:
    id: str
    name: str
    source_dir: str
    edit_dir: str
    status: str = "draft"
    stage: str = "inventory"
    sources: list[str] = field(default_factory=list)
    strategy: str = ""
    specifications: dict[str, Any] = field(default_factory=dict)
    approved_at: str | None = None
    artifacts: dict[str, str] = field(default_factory=dict)
    evaluation_passes: list[dict[str, Any]] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)


class VideoProductionManager:
    def __init__(self, path: Path = VIDEO_PRODUCTION_PATH):
        self.path = path
        self._lock = threading.RLock()
        self._projects: dict[str, VideoProduction] = {}
        self._load()

    def create(self, source_dir: str, *, name: str = "") -> dict[str, Any]:
        source = Path(str(source_dir or "")).expanduser().resolve(strict=True)
        if not source.is_dir():
            raise ValueError("video source path must be a directory")
        sources = sorted(
            str(item)
            for item in source.iterdir()
            if item.is_file() and item.suffix.lower() in VIDEO_EXTENSIONS
        )
        if not sources:
            raise ValueError("video source directory contains no supported footage")
        project = VideoProduction(
            id=f"video-{uuid.uuid4().hex[:10]}",
            name=str(name or source.name).strip(),
            source_dir=str(source),
            edit_dir=str(source / "edit"),
            sources=sources,
        )
        self._event(project, "created", f"Inventoried {len(sources)} source file(s).")
        with self._lock:
            self._projects[project.id] = project
            self._save()
        return asdict(project)

    def list(self) -> dict[str, Any]:
        with self._lock:
            return {"projects": [asdict(item) for item in self._projects.values()]}

    def get(self, project_id: str) -> dict[str, Any]:
        with self._lock:
            return asdict(self._require(project_id))

    def propose(
        self,
        project_id: str,
        strategy: str,
        specifications: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        strategy = str(strategy or "").strip()
        if not strategy:
            raise ValueError("plain-English video strategy is required")
        with self._lock:
            project = self._require(project_id)
            project.strategy = strategy
            project.specifications = self._normalize_specifications(specifications or {})
            project.status = "awaiting_approval"
            project.stage = "strategy"
            project.approved_at = None
            self._event(project, "strategy_proposed", strategy)
            self._save()
            return asdict(project)

    def approve(self, project_id: str, approved: bool, *, note: str = "") -> dict[str, Any]:
        with self._lock:
            project = self._require(project_id)
            if project.status != "awaiting_approval":
                raise ValueError("video strategy is not awaiting approval")
            project.status = "approved" if approved else "changes_requested"
            project.approved_at = _now() if approved else None
            self._event(project, "approved" if approved else "rejected", note)
            self._save()
            return asdict(project)

    def record_stage(
        self,
        project_id: str,
        stage: str,
        *,
        artifacts: dict[str, str] | None = None,
        note: str = "",
    ) -> dict[str, Any]:
        with self._lock:
            project = self._require_approved(project_id)
            project.stage = str(stage or "").strip()
            project.status = "in_progress"
            for key, value in (artifacts or {}).items():
                if value:
                    project.artifacts[str(key)] = str(value)
            self._event(project, "stage_completed", note or project.stage)
            self._save()
            return asdict(project)

    def record_evaluation(
        self,
        project_id: str,
        *,
        passed: bool,
        issues: list[str] | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            project = self._require_approved(project_id)
            if len(project.evaluation_passes) >= MAX_EVAL_PASSES:
                raise ValueError("self-evaluation limit reached; unresolved issues require user review")
            issue_list = [str(item).strip() for item in (issues or []) if str(item).strip()]
            accepted = bool(passed) and not issue_list
            record = {
                "pass": len(project.evaluation_passes) + 1,
                "passed": accepted,
                "issues": issue_list,
                "evidence": dict(evidence or {}),
                "checked_at": _now(),
            }
            project.evaluation_passes.append(record)
            project.stage = "verified" if accepted else "revision_required"
            project.status = "verified" if accepted else "in_progress"
            self._event(project, "self_eval_passed" if accepted else "self_eval_failed", "; ".join(issue_list))
            self._save()
            return asdict(project)

    def finalize(self, project_id: str, final_path: str) -> dict[str, Any]:
        final = Path(str(final_path or "")).expanduser().resolve(strict=True)
        with self._lock:
            project = self._require_approved(project_id)
            latest = project.evaluation_passes[-1] if project.evaluation_passes else None
            if not latest or not latest.get("passed"):
                raise ValueError("final video requires a passing self-evaluation")
            edit_dir = Path(project.edit_dir).resolve()
            if edit_dir not in final.parents:
                raise ValueError("final video must remain inside the production edit directory")
            project.artifacts["final"] = str(final)
            project.stage = "final"
            project.status = "completed"
            self._event(project, "finalized", str(final))
            self._save()
            return asdict(project)

    @staticmethod
    def _normalize_specifications(raw: dict[str, Any]) -> dict[str, Any]:
        return {
            "target": str(raw.get("target") or "").strip(),
            "aspect": str(raw.get("aspect") or "source").strip(),
            "pacing": str(raw.get("pacing") or "").strip(),
            "subtitles": bool(raw.get("subtitles", False)),
            "grade": str(raw.get("grade") or "none").strip(),
            "must_keep": [str(item) for item in raw.get("must_keep", []) if item],
            "must_cut": [str(item) for item in raw.get("must_cut", []) if item],
        }

    def _require(self, project_id: str) -> VideoProduction:
        project = self._projects.get(project_id)
        if project is None:
            raise ValueError("unknown video production")
        return project

    def _require_approved(self, project_id: str) -> VideoProduction:
        project = self._require(project_id)
        if not project.approved_at:
            raise ValueError("video strategy must be approved before execution")
        return project

    @staticmethod
    def _event(project: VideoProduction, event: str, note: str) -> None:
        project.updated_at = _now()
        project.history.append({"event": event, "note": str(note or ""), "timestamp": project.updated_at})
        project.history = project.history[-100:]

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            allowed = VideoProduction.__dataclass_fields__
            for item in raw.get("projects", []):
                project = VideoProduction(**{key: value for key, value in item.items() if key in allowed})
                self._projects[project.id] = project
        except Exception:
            self._projects = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.list(), ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)


_manager: VideoProductionManager | None = None


def get_video_production_manager() -> VideoProductionManager:
    global _manager
    if _manager is None:
        _manager = VideoProductionManager()
    return _manager
