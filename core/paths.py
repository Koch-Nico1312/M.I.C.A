from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT_ENV_VARS = ("MARK_XXXIX_ROOT", "MARK_XXXIX_BASE_DIR")


def _looks_like_project_root(candidate: Path) -> bool:
    return (candidate / "config.yaml").exists() and (
        (candidate / "main.py").exists()
        or (candidate / "UI" / "package.json").exists()
        or ((candidate / "config").exists() and (candidate / "core").exists())
    )


def resolve_project_root(start: Path | None = None) -> Path:
    """
    Resolve the repository root or packaged runtime root.

    The resolver prefers an explicit environment override, then walks upward
    from the supplied start path, the current module location, or the frozen
    executable directory.
    """
    for env_var in _ROOT_ENV_VARS:
        raw = os.getenv(env_var, "").strip()
        if raw:
            candidate = Path(raw).expanduser()
            if candidate.exists():
                return candidate.resolve()

    if start is None:
        if getattr(sys, "frozen", False):
            start = Path(sys.executable).resolve().parent
        else:
            start = Path(__file__).resolve()

    candidate = Path(start).expanduser().resolve()
    if candidate.is_file():
        candidate = candidate.parent

    for parent in (candidate, *candidate.parents):
        if _looks_like_project_root(parent):
            return parent

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent.parent


def project_path(*parts: str) -> Path:
    """Return an absolute path inside the project root."""
    return resolve_project_root().joinpath(*parts)


def resolve_relative_path(value: str | Path, *, base: Path | None = None) -> Path:
    """
    Resolve a configuration path against the project root when it is relative.
    """
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return (base or resolve_project_root()) / path
