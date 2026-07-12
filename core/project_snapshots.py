"""Secret-free local snapshots for a personal M.I.C.A Agent Hub."""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.paths import project_path


SNAPSHOT_DIR = project_path("data", "project_snapshots")
SNAPSHOT_FORMAT = "mica-solo-project/v1"
SENSITIVE_KEY = re.compile(r"(secret|token|password|api[_-]?key|credential|authorization)", re.I)


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _sanitize(item) for key, item in value.items() if not SENSITIVE_KEY.search(str(key))}
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


class ProjectSnapshotManager:
    def __init__(self, directory: Path = SNAPSHOT_DIR):
        self.directory = directory
        self._lock = threading.RLock()

    def create(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now().isoformat()
        snapshot_id = f"snap-{uuid4().hex[:10]}"
        package = {
            "format": SNAPSHOT_FORMAT,
            "id": snapshot_id,
            "name": str(name or "Agent-Hub Snapshot").strip(),
            "created_at": now,
            "scope": ["project_state", "supervisor_automation", "project_workspaces", "task_pipelines"],
            "data": _sanitize(payload),
        }
        self._write(package)
        return self._metadata(package)

    def import_package(self, package: dict[str, Any]) -> dict[str, Any]:
        if package.get("format") != SNAPSHOT_FORMAT or not isinstance(package.get("data"), dict):
            raise ValueError("invalid M.I.C.A solo project snapshot")
        imported = _sanitize(package)
        imported["id"] = f"snap-{uuid4().hex[:10]}"
        imported["name"] = f"{str(package.get('name') or 'Imported Snapshot')} (Import)"
        imported["created_at"] = datetime.now().isoformat()
        self._write(imported)
        return self._metadata(imported)

    def list(self) -> dict[str, Any]:
        with self._lock:
            items = []
            if self.directory.exists():
                for path in self.directory.glob("snap-*.json"):
                    try:
                        items.append(self._metadata(json.loads(path.read_text(encoding="utf-8"))))
                    except Exception:
                        continue
            items.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
            return {"format": SNAPSHOT_FORMAT, "items": items}

    def export(self, snapshot_id: str) -> dict[str, Any]:
        return self._read(snapshot_id)

    def restore_payload(self, snapshot_id: str) -> dict[str, Any]:
        package = self._read(snapshot_id)
        data = package.get("data")
        if not isinstance(data, dict):
            raise ValueError("snapshot data is missing")
        return data

    def delete(self, snapshot_id: str) -> dict[str, Any]:
        path = self._path(snapshot_id)
        if not path.exists():
            raise ValueError("unknown snapshot")
        path.unlink()
        return {"deleted": True, "id": snapshot_id}

    def _path(self, snapshot_id: str) -> Path:
        safe_id = str(snapshot_id or "")
        if not re.fullmatch(r"snap-[a-f0-9]{10}", safe_id):
            raise ValueError("invalid snapshot id")
        return self.directory / f"{safe_id}.json"

    def _read(self, snapshot_id: str) -> dict[str, Any]:
        path = self._path(snapshot_id)
        if not path.exists():
            raise ValueError("unknown snapshot")
        package = json.loads(path.read_text(encoding="utf-8"))
        if package.get("format") != SNAPSHOT_FORMAT:
            raise ValueError("unsupported snapshot format")
        return package

    def _write(self, package: dict[str, Any]) -> None:
        with self._lock:
            self.directory.mkdir(parents=True, exist_ok=True)
            path = self._path(str(package["id"]))
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(path)

    @staticmethod
    def _metadata(package: dict[str, Any]) -> dict[str, Any]:
        data = package.get("data", {}) if isinstance(package.get("data"), dict) else {}
        pipelines = data.get("task_pipelines", {}).get("pipelines", []) if isinstance(data.get("task_pipelines"), dict) else []
        workspaces = data.get("project_workspaces", {}).get("items", []) if isinstance(data.get("project_workspaces"), dict) else []
        return {
            "id": package.get("id"), "name": package.get("name"), "created_at": package.get("created_at"),
            "scope": package.get("scope", []), "pipeline_count": len(pipelines), "workspace_count": len(workspaces),
        }


_manager: ProjectSnapshotManager | None = None


def get_project_snapshot_manager() -> ProjectSnapshotManager:
    global _manager
    if _manager is None:
        _manager = ProjectSnapshotManager()
    return _manager
