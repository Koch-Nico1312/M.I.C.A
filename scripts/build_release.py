from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
DEFAULT_INCLUDE = (
    "actions",
    "agent",
    "config",
    "core",
    "docs",
    "memory",
    "plugins",
    "startup",
    "tools",
    "UI/dist",
    "main.py",
    "ui.py",
    "ui_bridge.py",
    "config.yaml",
    "requirements.txt",
    "requirements.lock",
    "pyproject.toml",
    "README.md",
    "CHANGELOG.md",
    "LICENSE",
)
EXCLUDE_PARTS = {
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "htmlcov",
    "node_modules",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iter_files(path: Path):
    if path.is_file():
        yield path
        return
    for file_path in path.rglob("*"):
        if file_path.is_file() and not (set(file_path.parts) & EXCLUDE_PARTS):
            yield file_path


def build_release(version: str) -> dict:
    DIST.mkdir(parents=True, exist_ok=True)
    archive = DIST / f"jarvis-{version}.zip"
    if archive.exists():
        archive.unlink()

    included_files = 0
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for item in DEFAULT_INCLUDE:
            source = ROOT / item
            if not source.exists():
                continue
            for file_path in _iter_files(source):
                bundle.write(file_path, file_path.relative_to(ROOT))
                included_files += 1

    manifest = {
        "name": "jarvis",
        "version": version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "archive": archive.name,
        "sha256": _sha256(archive),
        "included_files": included_files,
    }
    manifest_path = DIST / f"jarvis-{version}.manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a local Jarvis release archive.")
    parser.add_argument("--version", required=True, help="Release version, for example 0.4.0")
    parser.add_argument("--clean", action="store_true", help="Remove dist/ before building")
    args = parser.parse_args()

    if args.clean and DIST.exists():
        shutil.rmtree(DIST)

    manifest = build_release(args.version)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
