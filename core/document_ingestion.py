"""Controlled document ingestion records for uploads and local imports."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".py", ".ts", ".tsx", ".html", ".css"}
MARKITDOWN_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    ".wav",
    ".mp3",
    ".m4a",
    ".html",
    ".htm",
}


@dataclass
class IngestionChunk:
    id: str
    index: int
    text: str
    start: int
    end: int


@dataclass
class IngestionRecord:
    id: str
    name: str
    path: str
    type: str
    size: int
    checksum: str
    status: str
    chunks: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


def file_checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def detect_type(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    return suffix.upper() if suffix else "FILE"


def extract_text(path: Path, max_chars: int = 120_000) -> tuple[str, list[str]]:
    errors: list[str] = []
    if path.suffix.lower() in MARKITDOWN_EXTENSIONS:
        try:
            from core.advanced_knowledge_integrations import get_markitdown_adapter

            result = get_markitdown_adapter().convert_file(path, max_chars=max_chars)
            if result.ok:
                return str(result.result or "")[:max_chars], errors
            errors.append(result.error)
        except Exception as exc:
            errors.append(f"MarkItDown conversion failed: {exc}")

    if path.suffix.lower() in SUPPORTED_TEXT_EXTENSIONS:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")[:max_chars], errors
        except Exception as exc:
            errors.append(str(exc))
            return "", errors
    errors.append(f"No parser configured for {path.suffix or 'unknown'} files yet.")
    return "", errors


def chunk_text(text: str, *, chunk_size: int = 1200, overlap: int = 120) -> list[IngestionChunk]:
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []
    chunks: list[IngestionChunk] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunks.append(
            IngestionChunk(
                id=f"chunk-{uuid.uuid4().hex[:8]}",
                index=len(chunks),
                text=text[start:end],
                start=start,
                end=end,
            )
        )
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def build_ingestion_record(
    path: Path,
    *,
    existing_checksums: set[str] | None = None,
    chunk_size: int = 1200,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    checksum = file_checksum(path)
    text, errors = extract_text(path)
    chunks = chunk_text(text, chunk_size=chunk_size)
    duplicate = checksum in (existing_checksums or set())
    status = "duplicate" if duplicate else ("chunked" if chunks else "uploaded")
    record = IngestionRecord(
        id=uuid.uuid4().hex,
        name=path.name,
        path=str(path),
        type=detect_type(path),
        size=path.stat().st_size,
        checksum=checksum,
        status=status,
        chunks=len(chunks),
        metadata={
            "text_preview": text[:240],
            "duplicate": duplicate,
            "advanced_converter": "markitdown" if path.suffix.lower() in MARKITDOWN_EXTENSIONS else "",
        },
        errors=errors,
    )
    return asdict(record), [asdict(chunk) for chunk in chunks]


def write_chunk_artifact(base_dir: Path, record: dict[str, Any], chunks: list[dict[str, Any]]) -> str:
    base_dir.mkdir(parents=True, exist_ok=True)
    path = base_dir / f"{record['id']}.chunks.json"
    path.write_text(
        json.dumps({"record_id": record["id"], "chunks": chunks}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(path)
