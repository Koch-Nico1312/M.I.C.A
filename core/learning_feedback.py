"""Feedback store for learning signals that require review."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paths import project_path


FEEDBACK_PATH = project_path("data", "learning_feedback.json")


@dataclass
class FeedbackRecord:
    id: str
    rating: str
    target: str
    comment: str = ""
    correction: str = ""
    category: str = "general"
    context: dict[str, Any] = field(default_factory=dict)
    status: str = "pending_review"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class LearningFeedbackStore:
    def __init__(self, path: Path = FEEDBACK_PATH):
        self.path = path
        self._records: list[FeedbackRecord] = []
        self._load()

    def add(
        self,
        rating: str,
        target: str,
        *,
        comment: str = "",
        correction: str = "",
        category: str = "general",
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        record = FeedbackRecord(
            id=f"fb-{uuid.uuid4().hex[:8]}",
            rating=str(rating or "neutral"),
            target=str(target or ""),
            comment=str(comment or ""),
            correction=str(correction or ""),
            category=str(category or "general"),
            context=context or {},
        )
        self._records.insert(0, record)
        self._records = self._records[:500]
        self._save()
        return asdict(record)

    def list(self) -> dict[str, Any]:
        records = [asdict(record) for record in self._records]
        return {
            "records": records,
            "counts": {
                "total": len(records),
                "positive": sum(1 for item in records if item["rating"] == "positive"),
                "negative": sum(1 for item in records if item["rating"] == "negative"),
                "pending_review": sum(1 for item in records if item["status"] == "pending_review"),
            },
        }

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self._records = [FeedbackRecord(**item) for item in raw.get("records", [])]
        except Exception:
            self._records = []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.list(), ensure_ascii=False, indent=2), encoding="utf-8")


_store: LearningFeedbackStore | None = None


def get_learning_feedback_store() -> LearningFeedbackStore:
    global _store
    if _store is None:
        _store = LearningFeedbackStore()
    return _store
