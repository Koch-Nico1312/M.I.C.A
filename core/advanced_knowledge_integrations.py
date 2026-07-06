"""Optional knowledge and orchestration integrations for M.I.C.A.

These adapters keep heavyweight third-party SDKs behind lazy imports so the
default local-first M.I.C.A runtime remains usable without extra packages.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paths import project_path, resolve_relative_path


class OptionalKnowledgeIntegrationError(RuntimeError):
    """Raised when an optional knowledge integration is unavailable."""


@dataclass
class OptionalIntegrationResult:
    ok: bool
    provider: str
    action: str
    result: Any = None
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "provider": self.provider,
            "action": self.action,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata,
        }


def _artifact_dir(name: str) -> Path:
    path = project_path("data", name)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


class MarkItDownAdapter:
    """Adapter for microsoft/markitdown document-to-Markdown conversion."""

    provider = "markitdown"

    def available(self) -> bool:
        try:
            __import__("markitdown")
            return True
        except Exception:
            return False

    def convert_file(self, path: str | Path, *, max_chars: int = 120_000) -> OptionalIntegrationResult:
        file_path = Path(path).expanduser()
        if not file_path.is_absolute():
            file_path = resolve_relative_path(file_path)
        if not file_path.exists():
            return OptionalIntegrationResult(False, self.provider, "convert_file", error=f"Missing file: {file_path}")

        try:
            from markitdown import MarkItDown
        except Exception as exc:
            return OptionalIntegrationResult(
                False,
                self.provider,
                "convert_file",
                error=f"MarkItDown is not installed/configured: {exc}",
            )

        try:
            converted = MarkItDown().convert(str(file_path))
            text = str(getattr(converted, "text_content", "") or getattr(converted, "markdown", "") or converted)
            text = text[:max_chars]
            artifact = _artifact_dir("markitdown") / f"{file_path.stem}_{_stamp()}.md"
            artifact.write_text(text, encoding="utf-8")
            return OptionalIntegrationResult(
                True,
                self.provider,
                "convert_file",
                result=text,
                metadata={"artifact": str(artifact), "source_path": str(file_path)},
            )
        except Exception as exc:
            return OptionalIntegrationResult(False, self.provider, "convert_file", error=str(exc))


class LlamaIndexAdapter:
    """Optional advanced indexing and query path backed by LlamaIndex."""

    provider = "llama_index"

    def available(self) -> bool:
        try:
            __import__("llama_index.core")
            return True
        except Exception:
            return False

    def index_path(self, path: str | Path, *, persist_dir: str | Path | None = None) -> OptionalIntegrationResult:
        source_path = Path(path).expanduser()
        if not source_path.is_absolute():
            source_path = resolve_relative_path(source_path)
        persist_path = Path(persist_dir or project_path("data", "llama_index"))
        if not persist_path.is_absolute():
            persist_path = resolve_relative_path(persist_path)

        try:
            from llama_index.core import SimpleDirectoryReader, VectorStoreIndex
        except Exception as exc:
            return OptionalIntegrationResult(
                False,
                self.provider,
                "index_path",
                error=f"LlamaIndex is not installed/configured: {exc}",
            )

        if not source_path.exists():
            return OptionalIntegrationResult(False, self.provider, "index_path", error=f"Missing path: {source_path}")

        try:
            input_dir = source_path if source_path.is_dir() else source_path.parent
            input_files = None if source_path.is_dir() else [str(source_path)]
            documents = SimpleDirectoryReader(
                input_dir=str(input_dir),
                input_files=input_files,
                recursive=source_path.is_dir(),
            ).load_data()
            index = VectorStoreIndex.from_documents(documents)
            persist_path.mkdir(parents=True, exist_ok=True)
            index.storage_context.persist(persist_dir=str(persist_path))
            manifest = {
                "source_path": str(source_path),
                "persist_dir": str(persist_path),
                "documents": len(documents),
                "indexed_at": datetime.now().isoformat(),
            }
            (_artifact_dir("llama_index") / "latest_manifest.json").write_text(
                json.dumps(manifest, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            return OptionalIntegrationResult(True, self.provider, "index_path", result=manifest)
        except Exception as exc:
            return OptionalIntegrationResult(False, self.provider, "index_path", error=str(exc))

    def query(self, query: str, *, persist_dir: str | Path | None = None) -> OptionalIntegrationResult:
        persist_path = Path(persist_dir or project_path("data", "llama_index"))
        if not persist_path.is_absolute():
            persist_path = resolve_relative_path(persist_path)
        try:
            from llama_index.core import StorageContext, load_index_from_storage
        except Exception as exc:
            return OptionalIntegrationResult(
                False,
                self.provider,
                "query",
                error=f"LlamaIndex is not installed/configured: {exc}",
            )
        if not persist_path.exists():
            return OptionalIntegrationResult(False, self.provider, "query", error=f"Missing index: {persist_path}")
        try:
            storage_context = StorageContext.from_defaults(persist_dir=str(persist_path))
            index = load_index_from_storage(storage_context)
            response = index.as_query_engine().query(query)
            return OptionalIntegrationResult(
                True,
                self.provider,
                "query",
                result=str(response),
                metadata={"persist_dir": str(persist_path)},
            )
        except Exception as exc:
            return OptionalIntegrationResult(False, self.provider, "query", error=str(exc))


def get_markitdown_adapter() -> MarkItDownAdapter:
    return MarkItDownAdapter()


def get_llama_index_adapter() -> LlamaIndexAdapter:
    return LlamaIndexAdapter()

