"""Project workspace registry for scoped M.I.C.A context."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paths import project_path


WORKSPACE_PATH = project_path("data", "project_workspaces.json")


@dataclass
class ProjectWorkspace:
    id: str
    name: str
    paths: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    active: bool = False
    archived: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class ProjectWorkspaceManager:
    def __init__(self, path: Path = WORKSPACE_PATH):
        self.path = path
        self._workspaces: dict[str, ProjectWorkspace] = {}
        self._load()

    def create(self, name: str, *, paths: list[str] | None = None, tags: list[str] | None = None) -> dict[str, Any]:
        workspace = ProjectWorkspace(
            id=f"proj-{uuid.uuid4().hex[:8]}",
            name=str(name or "Project").strip(),
            paths=[str(path) for path in paths or []],
            tags=[str(tag) for tag in tags or []],
        )
        if not any(item.active for item in self._workspaces.values()):
            workspace.active = True
        self._workspaces[workspace.id] = workspace
        self._save()
        return asdict(workspace)

    def set_active(self, workspace_id: str) -> dict[str, Any]:
        if workspace_id not in self._workspaces:
            raise ValueError("unknown project")
        for item in self._workspaces.values():
            item.active = item.id == workspace_id
        self._save()
        return self.snapshot()

    def add_note(self, workspace_id: str, note: str) -> dict[str, Any]:
        item = self._require(workspace_id)
        if note not in item.notes:
            item.notes.append(note)
        self._save()
        return asdict(item)

    def snapshot(self) -> dict[str, Any]:
        items = [asdict(item) for item in self._workspaces.values()]
        active = next((item for item in items if item.get("active")), None)
        return {"items": items, "active": active}

    def _require(self, workspace_id: str) -> ProjectWorkspace:
        item = self._workspaces.get(workspace_id)
        if not item:
            raise ValueError("unknown project")
        return item

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self._workspaces = {
                item["id"]: ProjectWorkspace(**item) for item in raw.get("items", [])
            }
        except Exception:
            self._workspaces = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")


_manager: ProjectWorkspaceManager | None = None


def get_project_workspace_manager() -> ProjectWorkspaceManager:
    global _manager
    if _manager is None:
        _manager = ProjectWorkspaceManager()
    return _manager
