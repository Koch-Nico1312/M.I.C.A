"""Privacy modes for model and tool routing."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from core.paths import project_path


PRIVACY_PATH = project_path("data", "privacy_mode.json")
MODES = {
    "local_only": {"external_models": False, "external_tools": False, "approval_required": True},
    "private_with_approval": {"external_models": False, "external_tools": True, "approval_required": True},
    "balanced": {"external_models": True, "external_tools": True, "approval_required": True},
    "cloud_allowed": {"external_models": True, "external_tools": True, "approval_required": False},
    "debug": {"external_models": True, "external_tools": True, "approval_required": False},
}


@dataclass
class PrivacyState:
    mode: str = "balanced"
    temporary_until: str | None = None
    updated_at: str = datetime.now().isoformat()


class PrivacyModeManager:
    def __init__(self, path: Path = PRIVACY_PATH):
        self.path = path
        self.state = PrivacyState()
        self._load()

    def set_mode(self, mode: str, *, minutes: int | None = None) -> dict[str, Any]:
        if mode not in MODES:
            raise ValueError("unknown privacy mode")
        self.state.mode = mode
        self.state.temporary_until = (
            (datetime.now() + timedelta(minutes=minutes)).isoformat() if minutes else None
        )
        self.state.updated_at = datetime.now().isoformat()
        self._save()
        return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        return {**asdict(self.state), "rules": MODES[self.effective_mode()], "modes": MODES}

    def effective_mode(self) -> str:
        if self.state.temporary_until:
            try:
                if datetime.fromisoformat(self.state.temporary_until) < datetime.now():
                    self.state.temporary_until = None
                    self.state.mode = "balanced"
                    self._save()
            except Exception:
                self.state.temporary_until = None
        return self.state.mode

    def allows_external_model(self, sensitivity: str = "") -> bool:
        mode = self.effective_mode()
        if sensitivity in {"secret"}:
            return False
        if sensitivity == "private" and mode in {"local_only", "private_with_approval"}:
            return False
        return bool(MODES[mode]["external_models"])

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.state = PrivacyState(**raw.get("state", raw))
        except Exception:
            self.state = PrivacyState()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"state": asdict(self.state)}, indent=2), encoding="utf-8")


_manager: PrivacyModeManager | None = None


def get_privacy_mode_manager() -> PrivacyModeManager:
    global _manager
    if _manager is None:
        _manager = PrivacyModeManager()
    return _manager
