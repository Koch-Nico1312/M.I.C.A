"""Small filesystem snapshot helpers for reversible local file operations."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paths import project_path


SNAPSHOT_DIR = project_path("data", "snapshots")


def snapshot_path(target: Path, *, reason: str) -> dict[str, Any] | None:
    """Copy an existing file/folder into data/snapshots and return undo data."""
    try:
        target = Path(target).expanduser()
        if not target.exists():
            return None
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        safe_name = "".join(ch if ch.isalnum() or ch in ".-_" else "_" for ch in target.name)
        dest = SNAPSHOT_DIR / stamp / safe_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if target.is_dir():
            shutil.copytree(str(target), str(dest))
            kind = "directory"
        else:
            shutil.copy2(str(target), str(dest))
            kind = "file"
        return {
            "strategy": "restore_snapshot",
            "original_path": str(target),
            "snapshot_path": str(dest),
            "kind": kind,
            "reason": reason,
            "steps": [{"action": "restore", "snapshot": str(dest), "target": str(target)}],
            "automatic": False,
            "notes": "Restore the saved snapshot after confirmation.",
        }
    except Exception as exc:
        return {
            "strategy": "snapshot_failed",
            "original_path": str(target),
            "reason": reason,
            "error": str(exc),
            "automatic": False,
        }
