"""Per-user application autostart with explicit enable and disable operations."""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path
from typing import Any

from core.paths import project_path


class AppAutostartManager:
    def __init__(
        self,
        *,
        platform_name: str | None = None,
        target_path: Path | None = None,
        python_executable: str | None = None,
        entrypoint: Path | None = None,
    ):
        self.platform_name = platform_name or platform.system()
        self.python_executable = python_executable or sys.executable
        self.entrypoint = entrypoint or project_path("main.py")
        self.target_path = target_path or self._default_target()

    def status(self) -> dict[str, Any]:
        return {
            "supported": self.platform_name in {"Windows", "Linux"},
            "enabled": self.target_path.is_file(),
            "platform": self.platform_name,
            "target": str(self.target_path),
            "entrypoint": str(self.entrypoint),
            "scope": "current user only",
        }

    def preview(self) -> dict[str, Any]:
        return {**self.status(), "content": self._content(), "automatic_changes": False}

    def enable(self) -> dict[str, Any]:
        if self.platform_name not in {"Windows", "Linux"}:
            raise ValueError("app autostart is not supported on this platform")
        if not self.entrypoint.is_file():
            raise ValueError(f"M.I.C.A entrypoint is missing: {self.entrypoint}")
        self.target_path.parent.mkdir(parents=True, exist_ok=True)
        self.target_path.write_text(self._content(), encoding="utf-8")
        return self.status()

    def disable(self) -> dict[str, Any]:
        if self.target_path.is_file():
            self.target_path.unlink()
        return self.status()

    def _default_target(self) -> Path:
        if self.platform_name == "Windows":
            appdata = Path(os.getenv("APPDATA") or Path.home() / "AppData" / "Roaming")
            return appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "M.I.C.A.cmd"
        return Path.home() / ".config" / "autostart" / "mica.desktop"

    def _content(self) -> str:
        if self.platform_name == "Windows":
            executable = Path(self.python_executable)
            pythonw = executable.with_name("pythonw.exe")
            runtime = pythonw if pythonw.is_file() else executable
            return f'@echo off\nstart "" "{runtime}" "{self.entrypoint}"\n'
        return (
            "[Desktop Entry]\nType=Application\nName=M.I.C.A\n"
            f'Exec="{self.python_executable}" "{self.entrypoint}"\n'
            "Terminal=false\nX-GNOME-Autostart-enabled=true\n"
        )
