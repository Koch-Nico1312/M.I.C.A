"""Persistent solo-project state for the M.I.C.A supervisor."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paths import project_path


PROJECT_STATE_PATH = project_path("data", "project_state.json")
VALID_TABS = {"hub", "tasks", "agents", "flows", "approvals", "activity"}
DEFAULT_DASHBOARD_WIDGETS = ["supervisor", "approvals", "runs", "models", "activity"]
VALID_DASHBOARD_WIDGETS = set(DEFAULT_DASHBOARD_WIDGETS)
DEFAULT_RUN_BUDGET = {"max_steps": 8, "max_minutes": 60, "max_agent_calls": 20, "stop_on_limit": True}
MAX_STATE_RECORDS = 200
VALID_CRITERION_STATUSES = {"pending", "passed", "failed", "blocked", "waived"}
VALID_DECISION_STATUSES = {"active", "superseded", "reversed"}


def _default_telos() -> dict[str, Any]:
    return {
        "mission": "",
        "beliefs": [],
        "values": [],
        "goals": [],
        "strategies": [],
        "problems": [],
        "challenges": [],
        "people": [],
        "projects": [],
    }


def _default_current_state() -> dict[str, Any]:
    return {"summary": "", "facts": [], "constraints": [], "risks": []}


def _default_ideal_state() -> dict[str, Any]:
    return {"summary": "", "outcomes": [], "metrics": [], "target_date": ""}


def _now() -> str:
    return datetime.now().isoformat()


@dataclass
class ProjectState:
    version: int = 2
    active_project_id: str = ""
    objective: str = ""
    focus: str = ""
    status: str = "ready"
    last_tab: str = "hub"
    pipeline_ids: list[str] = field(default_factory=list)
    agent_ids: list[str] = field(default_factory=list)
    artifact_ids: list[str] = field(default_factory=list)
    favorite_commands: list[str] = field(default_factory=list)
    recent_commands: list[str] = field(default_factory=list)
    saved_views: dict[str, dict[str, Any]] = field(default_factory=dict)
    dashboard_widgets: list[str] = field(default_factory=lambda: list(DEFAULT_DASHBOARD_WIDGETS))
    run_budget: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_RUN_BUDGET))
    checkpoint: str = ""
    telos: dict[str, Any] = field(default_factory=_default_telos)
    current_state: dict[str, Any] = field(default_factory=_default_current_state)
    ideal_state: dict[str, Any] = field(default_factory=_default_ideal_state)
    acceptance_criteria: list[dict[str, Any]] = field(default_factory=list)
    decisions: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    updated_at: str = field(default_factory=_now)


class ProjectStateManager:
    """Owns the small durable state needed to resume a personal project."""

    def __init__(self, path: Path = PROJECT_STATE_PATH):
        self.path = path
        self._lock = threading.RLock()
        self._state = ProjectState()
        self._load()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            snapshot = asdict(self._state)
            snapshot["completion"] = self.completion_report()
            return snapshot

    def update(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            for key in ("active_project_id", "objective", "focus", "status", "checkpoint"):
                if key in payload:
                    setattr(self._state, key, str(payload.get(key) or "").strip())
            if "last_tab" in payload:
                tab = str(payload.get("last_tab") or "hub")
                self._state.last_tab = tab if tab in VALID_TABS else "hub"
            for key in ("pipeline_ids", "agent_ids", "artifact_ids", "favorite_commands", "recent_commands"):
                if key in payload and isinstance(payload[key], list):
                    values = list(dict.fromkeys(str(item) for item in payload[key] if item))
                    setattr(self._state, key, values[-20:] if key == "recent_commands" else values)
            if "dashboard_widgets" in payload and isinstance(payload["dashboard_widgets"], list):
                self._state.dashboard_widgets = list(dict.fromkeys(
                    str(item) for item in payload["dashboard_widgets"] if str(item) in VALID_DASHBOARD_WIDGETS
                ))
            if "saved_views" in payload and isinstance(payload["saved_views"], dict):
                self._state.saved_views = {
                    str(key): value for key, value in payload["saved_views"].items()
                    if isinstance(value, dict)
                }
            if "run_budget" in payload and isinstance(payload["run_budget"], dict):
                raw_budget = payload["run_budget"]
                self._state.run_budget = {
                    "max_steps": max(1, min(50, int(raw_budget.get("max_steps", self._state.run_budget.get("max_steps", 8))))),
                    "max_minutes": max(1, min(1440, int(raw_budget.get("max_minutes", self._state.run_budget.get("max_minutes", 60))))),
                    "max_agent_calls": max(1, min(500, int(raw_budget.get("max_agent_calls", self._state.run_budget.get("max_agent_calls", 20))))),
                    "stop_on_limit": bool(raw_budget.get("stop_on_limit", self._state.run_budget.get("stop_on_limit", True))),
                }
            if "telos" in payload and isinstance(payload["telos"], dict):
                self._state.telos = self._merge_section(self._state.telos, payload["telos"])
            if "current_state" in payload and isinstance(payload["current_state"], dict):
                self._state.current_state = self._merge_section(self._state.current_state, payload["current_state"])
            if "ideal_state" in payload and isinstance(payload["ideal_state"], dict):
                self._state.ideal_state = self._merge_section(self._state.ideal_state, payload["ideal_state"])
            if "acceptance_criteria" in payload and isinstance(payload["acceptance_criteria"], list):
                self._state.acceptance_criteria = self._normalize_criteria(payload["acceptance_criteria"])
            if "decisions" in payload and isinstance(payload["decisions"], list):
                self._state.decisions = self._normalize_decisions(payload["decisions"])
            if "evidence" in payload and isinstance(payload["evidence"], list):
                self._state.evidence = self._normalize_evidence(payload["evidence"])
            if isinstance(payload.get("acceptance_criterion"), dict):
                self._upsert_criterion(payload["acceptance_criterion"])
            if isinstance(payload.get("decision"), dict):
                self._append_decision(payload["decision"])
            if isinstance(payload.get("evidence_record"), dict):
                self._append_evidence(payload["evidence_record"])
            self._state.updated_at = _now()
            self._save()
            return self.snapshot()

    def checkpoint(self, note: str, *, focus: str = "") -> dict[str, Any]:
        return self.update({"checkpoint": note, **({"focus": focus} if focus else {})})

    def set_acceptance_criterion(
        self,
        claim: str,
        *,
        criterion_id: str = "",
        status: str = "pending",
        evidence_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        return self.update(
            {
                "acceptance_criterion": {
                    "id": criterion_id,
                    "claim": claim,
                    "status": status,
                    "evidence_ids": evidence_ids or [],
                }
            }
        )

    def record_decision(
        self,
        summary: str,
        *,
        rationale: str = "",
        decision_id: str = "",
        status: str = "active",
    ) -> dict[str, Any]:
        return self.update(
            {
                "decision": {
                    "id": decision_id,
                    "summary": summary,
                    "rationale": rationale,
                    "status": status,
                }
            }
        )

    def record_evidence(
        self,
        claim: str,
        *,
        source: str,
        result: str = "passed",
        kind: str = "verification",
        evidence_id: str = "",
        criterion_id: str = "",
    ) -> dict[str, Any]:
        with self._lock:
            criterion = None
            if criterion_id:
                criterion = next(
                    (item for item in self._state.acceptance_criteria if item["id"] == criterion_id),
                    None,
                )
                if criterion is None:
                    raise ValueError(f"unknown acceptance criterion: {criterion_id}")
            record = self._append_evidence(
                {
                    "id": evidence_id,
                    "claim": claim,
                    "source": source,
                    "result": result,
                    "kind": kind,
                }
            )
            if criterion is not None:
                criterion["evidence_ids"] = list(
                    dict.fromkeys([*criterion.get("evidence_ids", []), record["id"]])
                )
                criterion["updated_at"] = _now()
            self._state.updated_at = _now()
            self._save()
            return self.snapshot()

    def completion_report(self) -> dict[str, Any]:
        with self._lock:
            criteria = self._state.acceptance_criteria
            counts = {status: 0 for status in sorted(VALID_CRITERION_STATUSES)}
            for item in criteria:
                counts[str(item.get("status") or "pending")] = counts.get(
                    str(item.get("status") or "pending"), 0
                ) + 1
            closable = bool(criteria) and all(
                item.get("status") in {"passed", "waived"} and bool(item.get("evidence_ids"))
                for item in criteria
            )
            return {
                "criteria_total": len(criteria),
                "counts": counts,
                "evidence_total": len(self._state.evidence),
                "decision_total": len(self._state.decisions),
                "ready_to_close": closable,
            }

    def reconcile(
        self,
        *,
        active_project_id: str = "",
        pipeline_ids: list[str] | None = None,
        agent_ids: list[str] | None = None,
        artifact_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        current = self.snapshot()
        return self.update(
            {
                "active_project_id": active_project_id or current["active_project_id"],
                "pipeline_ids": pipeline_ids if pipeline_ids is not None else current["pipeline_ids"],
                "agent_ids": agent_ids if agent_ids is not None else current["agent_ids"],
                "artifact_ids": artifact_ids if artifact_ids is not None else current["artifact_ids"],
            }
        )

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            allowed = ProjectState.__dataclass_fields__
            self._state = ProjectState(**{key: value for key, value in raw.items() if key in allowed})
            self._state.version = 2
            self._state.telos = self._merge_section(_default_telos(), self._state.telos)
            self._state.current_state = self._merge_section(_default_current_state(), self._state.current_state)
            self._state.ideal_state = self._merge_section(_default_ideal_state(), self._state.ideal_state)
            self._state.acceptance_criteria = self._normalize_criteria(self._state.acceptance_criteria)
            self._state.decisions = self._normalize_decisions(self._state.decisions)
            self._state.evidence = self._normalize_evidence(self._state.evidence)
        except Exception:
            self._state = ProjectState()

    @staticmethod
    def _merge_section(current: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
        merged = dict(current)
        for key, value in update.items():
            if isinstance(value, list):
                merged[str(key)] = list(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))
            elif isinstance(value, (str, int, float, bool)) or value is None:
                merged[str(key)] = value
        return merged

    @staticmethod
    def _record_id(prefix: str, raw_id: Any, seed: str) -> str:
        value = str(raw_id or "").strip()
        if value:
            return value
        import hashlib

        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
        return f"{prefix}-{digest}"

    @classmethod
    def _normalize_criteria(cls, items: list[Any]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for raw in items[-MAX_STATE_RECORDS:]:
            if not isinstance(raw, dict):
                continue
            claim = str(raw.get("claim") or raw.get("text") or "").strip()
            if not claim:
                continue
            status = str(raw.get("status") or "pending").strip().lower()
            status = status if status in VALID_CRITERION_STATUSES else "pending"
            normalized.append(
                {
                    "id": cls._record_id("isc", raw.get("id"), claim),
                    "claim": claim,
                    "status": status,
                    "evidence_ids": list(
                        dict.fromkeys(str(item) for item in raw.get("evidence_ids", []) if item)
                    ),
                    "updated_at": str(raw.get("updated_at") or _now()),
                }
            )
        return normalized

    @classmethod
    def _normalize_decisions(cls, items: list[Any]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for raw in items[-MAX_STATE_RECORDS:]:
            if not isinstance(raw, dict):
                continue
            summary = str(raw.get("summary") or raw.get("decision") or "").strip()
            if not summary:
                continue
            status = str(raw.get("status") or "active").strip().lower()
            normalized.append(
                {
                    "id": cls._record_id("decision", raw.get("id"), summary),
                    "summary": summary,
                    "rationale": str(raw.get("rationale") or "").strip(),
                    "status": status if status in VALID_DECISION_STATUSES else "active",
                    "made_at": str(raw.get("made_at") or _now()),
                }
            )
        return normalized

    @classmethod
    def _normalize_evidence(cls, items: list[Any]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for raw in items[-MAX_STATE_RECORDS:]:
            if not isinstance(raw, dict):
                continue
            claim = str(raw.get("claim") or "").strip()
            source = str(raw.get("source") or "").strip()
            if not claim or not source:
                continue
            collected_at = str(raw.get("collected_at") or _now())
            normalized.append(
                {
                    "id": cls._record_id("evidence", raw.get("id"), f"{claim}|{source}|{collected_at}"),
                    "claim": claim,
                    "source": source,
                    "result": str(raw.get("result") or "observed").strip().lower(),
                    "kind": str(raw.get("kind") or "verification").strip().lower(),
                    "collected_at": collected_at,
                }
            )
        return normalized

    def _upsert_criterion(self, raw: dict[str, Any]) -> dict[str, Any]:
        raw_id = str(raw.get("id") or "").strip()
        existing = next(
            (item for item in self._state.acceptance_criteria if raw_id and item["id"] == raw_id),
            None,
        )
        candidate = {**(existing or {}), **raw}
        normalized = self._normalize_criteria([candidate])
        if not normalized:
            raise ValueError("acceptance criterion requires a claim")
        item = normalized[0]
        for index, current in enumerate(self._state.acceptance_criteria):
            if current["id"] == item["id"]:
                self._state.acceptance_criteria[index] = item
                return item
        self._state.acceptance_criteria = [*self._state.acceptance_criteria, item][-MAX_STATE_RECORDS:]
        return item

    def _append_decision(self, raw: dict[str, Any]) -> dict[str, Any]:
        normalized = self._normalize_decisions([raw])
        if not normalized:
            raise ValueError("decision requires a summary")
        item = normalized[0]
        self._state.decisions = [*self._state.decisions, item][-MAX_STATE_RECORDS:]
        return item

    def _append_evidence(self, raw: dict[str, Any]) -> dict[str, Any]:
        normalized = self._normalize_evidence([raw])
        if not normalized:
            raise ValueError("evidence requires a claim and source")
        item = normalized[0]
        self._state.evidence = [*self._state.evidence, item][-MAX_STATE_RECORDS:]
        return item

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(asdict(self._state), ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)


_manager: ProjectStateManager | None = None
_manager_lock = threading.Lock()


def get_project_state_manager() -> ProjectStateManager:
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = ProjectStateManager()
    return _manager
