"""Record safe demonstrations and turn them into reusable local workflows."""

from __future__ import annotations

import json
import threading
import uuid
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paths import project_path


TEACH_MODE_PATH = project_path("data", "teach_workflows.json")
_UNSAFE_MARKERS = {"delete", "remove", "format", "shutdown", "registry", "payment", "purchase"}


class TeachMode:
    def __init__(self, path: Path = TEACH_MODE_PATH):
        self.path = path
        self._lock = threading.RLock()
        self._active: dict[str, Any] | None = None
        self._workflows: list[dict[str, Any]] = []
        self._load()

    def start(self, name: str) -> dict[str, Any]:
        with self._lock:
            self._active = {
                "id": f"lesson-{uuid.uuid4().hex[:8]}",
                "name": str(name or "Gelernter Ablauf").strip(),
                "started_at": datetime.now().isoformat(),
                "steps": [],
            }
            return deepcopy(self._active)

    def record(self, tool: str, args: dict[str, Any] | None = None, *, label: str = "") -> dict[str, Any]:
        with self._lock:
            if self._active is None:
                raise ValueError("teach mode is not recording")
            normalized_tool = str(tool or "").strip()
            if not normalized_tool:
                raise ValueError("tool is required")
            haystack = f"{normalized_tool} {json.dumps(args or {}, ensure_ascii=False)}".lower()
            if any(marker in haystack for marker in _UNSAFE_MARKERS):
                raise ValueError("unsafe demonstrations cannot be saved automatically")
            step = {
                "id": f"step-{len(self._active['steps']) + 1}",
                "tool": normalized_tool,
                "args": deepcopy(args or {}),
                "label": str(label or normalized_tool),
            }
            self._active["steps"].append(step)
            return deepcopy(step)

    def finish(self, *, save: bool = True) -> dict[str, Any]:
        with self._lock:
            if self._active is None:
                raise ValueError("teach mode is not recording")
            lesson = self._active
            self._active = None
            if not lesson["steps"]:
                raise ValueError("a learned workflow needs at least one step")
            lesson["created_at"] = datetime.now().isoformat()
            lesson["status"] = "ready"
            if save:
                self._workflows.insert(0, lesson)
                self._workflows = self._workflows[:100]
                self._save()
            return deepcopy(lesson)

    def cancel(self) -> None:
        with self._lock:
            self._active = None

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {"recording": self._active is not None, "active": deepcopy(self._active), "items": deepcopy(self._workflows)}

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self._workflows = list(raw.get("items", []))[:100]
        except Exception:
            self._workflows = []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps({"items": self._workflows}, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)


_teach_mode: TeachMode | None = None


def get_teach_mode() -> TeachMode:
    global _teach_mode
    if _teach_mode is None:
        _teach_mode = TeachMode()
    return _teach_mode
