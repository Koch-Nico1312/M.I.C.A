"""
Unified local knowledge access for M.I.C.A.

The KnowledgeManager is the single entry point for retrieval across personal
notes, indexed documents, and long-term memory. Source-specific integrations
stay behind small adapters so Wikipedia/Kiwix, GitHub, PDFs, or other sources
can be added without changing callers.
"""

from __future__ import annotations

import html
import json
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol

from core.logger import get_logger
from core.paths import resolve_relative_path

logger = get_logger(__name__)


@dataclass
class KnowledgeSource:
    """A source that can be indexed by the knowledge system."""

    kind: str
    uri: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class KnowledgeResult:
    """One normalized search result from any knowledge source."""

    title: str
    content: str
    source: str
    uri: str = ""
    score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class KnowledgeContext:
    """Context bundle ready to pass to an LLM prompt."""

    query: str
    results: list[KnowledgeResult]
    text: str


@dataclass
class KnowledgeGraphEdge:
    """A relationship inferred between two knowledge topics."""

    source: str
    target: str
    relation: str = "related"
    evidence: str = ""


@dataclass
class KnowledgeNoteSuggestion:
    """A proposed Obsidian note derived from retrieved knowledge."""

    title: str
    summary: str
    sources: list[str]
    links: list[str]
    tags: list[str]
    confidence: float
    reason: str
    content: str


@dataclass
class KnowledgeNotePlan:
    """Suggested notes plus graph edges derived from a query."""

    query: str
    suggestions: list[KnowledgeNoteSuggestion]
    graph_edges: list[KnowledgeGraphEdge]


class KnowledgeAdapter(Protocol):
    """Adapter contract for one retrievable knowledge source."""

    name: str

    def search(self, query: str, limit: int) -> list[KnowledgeResult]:
        """Return normalized results for a query."""

    def index(self, source: KnowledgeSource) -> dict[str, Any]:
        """Index a source when supported."""


class SemanticSearchAdapter:
    """Adapter for core.semantic_search.SemanticSearch."""

    name = "documents"

    def __init__(self, semantic_search_factory: Callable[[], Any] | None = None):
        self._semantic_search_factory = semantic_search_factory
        self._semantic_search: Any | None = None

    @property
    def semantic_search(self) -> Any:
        if self._semantic_search is None:
            if self._semantic_search_factory is not None:
                self._semantic_search = self._semantic_search_factory()
            else:
                from core.semantic_search import get_semantic_search

                self._semantic_search = get_semantic_search()
        return self._semantic_search

    def search(self, query: str, limit: int) -> list[KnowledgeResult]:
        if not query:
            return []
        results = self.semantic_search.search(query, n_results=limit)
        normalized = []
        for item in results or []:
            metadata = dict(item.get("metadata") or {})
            title = str(metadata.get("file_name") or metadata.get("source") or "Indexed document")
            uri = str(metadata.get("file_path") or item.get("id") or "")
            normalized.append(
                KnowledgeResult(
                    title=title,
                    content=str(item.get("document") or ""),
                    source=self.name,
                    uri=uri,
                    score=item.get("distance"),
                    metadata=metadata,
                )
            )
        return normalized

    def index(self, source: KnowledgeSource) -> dict[str, Any]:
        if source.kind not in {"directory", "documents", "file"}:
            return {"indexed": False, "source": self.name, "reason": "unsupported_source_kind"}

        path = Path(source.uri).expanduser()
        if not path.is_absolute():
            path = resolve_relative_path(path)

        if source.kind == "file" or path.is_file():
            content = path.read_text(encoding="utf-8", errors="ignore")
            indexed = bool(
                self.semantic_search.index_file(path, content, metadata=source.metadata)
            )
            return {"indexed": indexed, "source": self.name, "path": str(path)}

        self.semantic_search.index_directory(path)
        return {"indexed": True, "source": self.name, "path": str(path)}


class ObsidianKnowledgeAdapter:
    """Adapter for personal Obsidian notes."""

    name = "obsidian"

    def __init__(self, obsidian_bridge_factory: Callable[[], Any] | None = None):
        self._obsidian_bridge_factory = obsidian_bridge_factory
        self._obsidian_bridge: Any | None = None

    @property
    def obsidian_bridge(self) -> Any:
        if self._obsidian_bridge is None:
            if self._obsidian_bridge_factory is not None:
                self._obsidian_bridge = self._obsidian_bridge_factory()
            else:
                from memory.obsidian_vault import get_obsidian_bridge

                self._obsidian_bridge = get_obsidian_bridge()
        return self._obsidian_bridge

    def search(self, query: str, limit: int) -> list[KnowledgeResult]:
        if not query:
            return []
        notes = self.obsidian_bridge.search_notes(query) or []
        results = []
        for note in notes[:limit]:
            results.append(
                KnowledgeResult(
                    title=str(note.get("title") or "Obsidian note"),
                    content=str(note.get("snippet") or ""),
                    source=self.name,
                    uri=str(note.get("path") or ""),
                    metadata=dict(note),
                )
            )
        return results

    def index(self, source: KnowledgeSource) -> dict[str, Any]:
        if source.kind not in {"obsidian", "vault"}:
            return {"indexed": False, "source": self.name, "reason": "unsupported_source_kind"}
        summary = self.obsidian_bridge.sync_vault()
        return {"indexed": True, "source": self.name, **summary}


class KiwixWikipediaAdapter:
    """Adapter for offline Wikipedia archives stored as Kiwix .zim files."""

    name = "wikipedia"

    def __init__(
        self,
        semantic_search_factory: Callable[[], Any] | None = None,
        article_reader_factory: Callable[[Path], Iterable[dict[str, Any]]] | None = None,
        metadata_db_path: Path | None = None,
    ):
        self._semantic_search_factory = semantic_search_factory
        self._semantic_search: Any | None = None
        self._article_reader_factory = article_reader_factory
        self.metadata_db_path = metadata_db_path or resolve_relative_path(
            "data/knowledge/wikipedia_metadata.sqlite"
        )

    @property
    def semantic_search(self) -> Any:
        if self._semantic_search is None:
            if self._semantic_search_factory is not None:
                self._semantic_search = self._semantic_search_factory()
            else:
                from core.semantic_search import get_semantic_search

                self._semantic_search = get_semantic_search()
        return self._semantic_search

    def search(self, query: str, limit: int) -> list[KnowledgeResult]:
        if not query:
            return []

        results = self._search_semantic_index(query, limit)
        seen = {result.uri for result in results}
        for result in self._search_metadata(query, limit):
            if result.uri not in seen:
                results.append(result)
                seen.add(result.uri)
            if len(results) >= limit:
                break
        return results[:limit]

    def index(self, source: KnowledgeSource) -> dict[str, Any]:
        if source.kind not in {"zim", "kiwix", "wikipedia"}:
            return {"indexed": False, "source": self.name, "reason": "unsupported_source_kind"}

        zim_path = Path(source.uri).expanduser()
        if not zim_path.is_absolute():
            zim_path = resolve_relative_path(zim_path)
        if not zim_path.exists():
            return {
                "indexed": False,
                "source": self.name,
                "reason": "missing_zim_file",
                "path": str(zim_path),
            }

        max_articles = source.metadata.get("max_articles")
        if max_articles is not None:
            max_articles = int(max_articles)

        self._ensure_schema()
        indexed_articles = 0
        metadata_rows = 0

        try:
            articles = self._read_articles(zim_path)
        except RuntimeError as exc:
            return {
                "indexed": False,
                "source": self.name,
                "reason": "missing_dependency",
                "detail": str(exc),
                "path": str(zim_path),
            }

        for article in articles:
            if max_articles is not None and indexed_articles >= max_articles:
                break

            normalized = self._normalize_article(article, zim_path)
            if not normalized["title"] or not normalized["content"]:
                continue

            self._store_article_metadata(normalized)
            metadata_rows += 1

            document_id = f"wikipedia:{normalized['zim_path']}:{normalized['path']}"
            indexed = self.semantic_search.index_text(
                document_id=document_id,
                title=normalized["title"],
                content=normalized["content"],
                metadata={
                    "source": self.name,
                    "zim_path": normalized["zim_path"],
                    "zim_entry_path": normalized["path"],
                    "title": normalized["title"],
                    "categories": ", ".join(normalized["categories"]),
                },
            )
            if indexed:
                indexed_articles += 1

        return {
            "indexed": indexed_articles > 0 or metadata_rows > 0,
            "source": self.name,
            "path": str(zim_path),
            "articles_indexed": indexed_articles,
            "metadata_rows": metadata_rows,
            "metadata_db_path": str(self.metadata_db_path),
        }

    def _read_articles(self, zim_path: Path) -> Iterable[dict[str, Any]]:
        if self._article_reader_factory is not None:
            return self._article_reader_factory(zim_path)
        return self._read_articles_with_pyzim(zim_path)

    def _read_articles_with_pyzim(self, zim_path: Path) -> Iterable[dict[str, Any]]:
        try:
            from pyzim.archive import Archive
        except Exception as exc:
            raise RuntimeError("pyzim is required to index .zim files") from exc

        archive = Archive(str(zim_path))
        try:
            entries = archive.iter_entries()
            for entry in entries:
                if getattr(entry, "is_redirect", False):
                    continue
                namespace = str(getattr(entry, "namespace", "A"))
                if namespace not in {"A", "C", ""}:
                    continue

                title = str(getattr(entry, "title", "") or getattr(entry, "path", ""))
                entry_path = str(getattr(entry, "path", title))
                content = self._extract_entry_content(entry)
                if content:
                    yield {"title": title, "path": entry_path, "content": content}
        finally:
            close = getattr(archive, "close", None)
            if callable(close):
                close()

    def _extract_entry_content(self, entry: Any) -> str:
        item = entry
        get_item = getattr(entry, "get_item", None)
        if callable(get_item):
            item = get_item()

        content = getattr(item, "content", None)
        if callable(content):
            content = content()
        if isinstance(content, bytes):
            return content.decode("utf-8", errors="ignore")
        if content is not None:
            return str(content)

        read = getattr(item, "read", None)
        if callable(read):
            raw = read()
            if isinstance(raw, bytes):
                return raw.decode("utf-8", errors="ignore")
            return str(raw)
        return ""

    def _normalize_article(self, article: dict[str, Any], zim_path: Path) -> dict[str, Any]:
        raw_content = str(article.get("content") or article.get("text") or "")
        content = self._clean_article_text(raw_content)
        title = str(article.get("title") or article.get("path") or "").strip()
        entry_path = str(article.get("path") or title).strip()
        categories = article.get("categories") if isinstance(article.get("categories"), list) else []
        links = article.get("links") if isinstance(article.get("links"), list) else []
        description = str(article.get("description") or self._summarize(content))
        return {
            "zim_path": str(zim_path),
            "path": entry_path,
            "title": title,
            "description": description,
            "categories": [str(category) for category in categories],
            "links": [str(link) for link in links],
            "content": content,
        }

    def _clean_article_text(self, text: str) -> str:
        text = re.sub(r"<script\b.*?</script>", " ", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<style\b.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = html.unescape(text)
        return re.sub(r"\s+", " ", text).strip()

    def _summarize(self, text: str) -> str:
        return text[:280].strip()

    def _ensure_schema(self) -> None:
        self.metadata_db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.metadata_db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS wikipedia_articles (
                    zim_path TEXT NOT NULL,
                    entry_path TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    categories_json TEXT NOT NULL DEFAULT '[]',
                    links_json TEXT NOT NULL DEFAULT '[]',
                    indexed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (zim_path, entry_path)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_wikipedia_articles_title "
                "ON wikipedia_articles(title)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_wikipedia_articles_description "
                "ON wikipedia_articles(description)"
            )

    def _store_article_metadata(self, article: dict[str, Any]) -> None:
        with sqlite3.connect(self.metadata_db_path) as conn:
            conn.execute(
                """
                INSERT INTO wikipedia_articles (
                    zim_path, entry_path, title, description, categories_json, links_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(zim_path, entry_path) DO UPDATE SET
                    title = excluded.title,
                    description = excluded.description,
                    categories_json = excluded.categories_json,
                    links_json = excluded.links_json,
                    indexed_at = CURRENT_TIMESTAMP
                """,
                (
                    article["zim_path"],
                    article["path"],
                    article["title"],
                    article["description"],
                    json.dumps(article["categories"]),
                    json.dumps(article["links"]),
                ),
            )

    def _search_metadata(self, query: str, limit: int) -> list[KnowledgeResult]:
        if not self.metadata_db_path.exists():
            return []

        like_query = f"%{query}%"
        with sqlite3.connect(self.metadata_db_path) as conn:
            rows = conn.execute(
                """
                SELECT zim_path, entry_path, title, description, categories_json, links_json
                FROM wikipedia_articles
                WHERE title LIKE ? OR description LIKE ? OR categories_json LIKE ?
                ORDER BY
                    CASE WHEN title LIKE ? THEN 0 ELSE 1 END,
                    title
                LIMIT ?
                """,
                (like_query, like_query, like_query, like_query, limit),
            ).fetchall()

        results = []
        for zim_path, entry_path, title, description, categories_json, links_json in rows:
            results.append(
                KnowledgeResult(
                    title=title,
                    content=description or "",
                    source=self.name,
                    uri=f"{zim_path}#{entry_path}",
                    metadata={
                        "zim_path": zim_path,
                        "entry_path": entry_path,
                        "categories": json.loads(categories_json or "[]"),
                        "links": json.loads(links_json or "[]"),
                        "match_type": "metadata",
                    },
                )
            )
        return results

    def _search_semantic_index(self, query: str, limit: int) -> list[KnowledgeResult]:
        results = []
        for item in self.semantic_search.search(query, n_results=limit * 2) or []:
            metadata = dict(item.get("metadata") or {})
            if metadata.get("source") != self.name:
                continue
            zim_path = str(metadata.get("zim_path") or "")
            entry_path = str(metadata.get("zim_entry_path") or "")
            results.append(
                KnowledgeResult(
                    title=str(metadata.get("title") or metadata.get("file_name") or "Wikipedia article"),
                    content=str(item.get("document") or ""),
                    source=self.name,
                    uri=f"{zim_path}#{entry_path}" if zim_path or entry_path else str(item.get("id") or ""),
                    score=item.get("distance"),
                    metadata={**metadata, "match_type": "semantic"},
                )
            )
            if len(results) >= limit:
                break
        return results


class MemoryKnowledgeAdapter:
    """Adapter for M.I.C.A long-term structured memory."""

    name = "memory"

    def __init__(self, retrieval_factory: Callable[[], Any] | None = None):
        self._retrieval_factory = retrieval_factory
        self._retrieval: Any | None = None

    @property
    def retrieval(self) -> Any:
        if self._retrieval is None:
            if self._retrieval_factory is not None:
                self._retrieval = self._retrieval_factory()
            else:
                from memory.hybrid_retrieval import get_hybrid_retrieval

                self._retrieval = get_hybrid_retrieval()
        return self._retrieval

    def search(self, query: str, limit: int) -> list[KnowledgeResult]:
        if not query:
            return []
        results = []
        for item in self.retrieval.retrieve(query, max_results=limit) or []:
            entry = item.entry
            results.append(
                KnowledgeResult(
                    title=f"{entry.category}/{entry.key}",
                    content=entry.value,
                    source=self.name,
                    uri=entry.source or "",
                    score=item.relevance_score,
                    metadata={
                        "category": entry.category,
                        "key": entry.key,
                        "match_type": item.match_type,
                        "confidence": item.confidence.value,
                        "age_days": item.age_days,
                    },
                )
            )
        return results

    def index(self, source: KnowledgeSource) -> dict[str, Any]:
        return {"indexed": False, "source": self.name, "reason": "read_only_source"}


class LlamaIndexKnowledgeAdapter:
    """Optional advanced RAG adapter backed by LlamaIndex."""

    name = "advanced_index"

    def search(self, query: str, limit: int) -> list[KnowledgeResult]:
        if not query:
            return []
        from core.advanced_knowledge_integrations import get_llama_index_adapter

        result = get_llama_index_adapter().query(query)
        if not result.ok:
            logger.debug("LlamaIndex query unavailable: %s", result.error)
            return []
        return [
            KnowledgeResult(
                title="LlamaIndex response",
                content=str(result.result or ""),
                source=self.name,
                uri=str(result.metadata.get("persist_dir", "")),
                score=1.0,
                metadata=result.to_dict(),
            )
        ][:limit]

    def index(self, source: KnowledgeSource) -> dict[str, Any]:
        if source.kind not in {"advanced_index", "llama_index", "directory", "file"}:
            return {"indexed": False, "source": self.name, "reason": "unsupported_source_kind"}
        from core.advanced_knowledge_integrations import get_llama_index_adapter

        persist_dir = source.metadata.get("persist_dir")
        result = get_llama_index_adapter().index_path(source.uri, persist_dir=persist_dir)
        payload = result.to_dict()
        return {"indexed": result.ok, "source": self.name, **payload}


class KnowledgeManager:
    """Unified API for indexing and retrieving local knowledge."""

    def __init__(
        self,
        adapters: Iterable[KnowledgeAdapter] | None = None,
        obsidian_bridge_factory: Callable[[], Any] | None = None,
    ):
        self.adapters: list[KnowledgeAdapter] = list(adapters or self._default_adapters())
        self._obsidian_bridge_factory = obsidian_bridge_factory
        self._obsidian_bridge: Any | None = None

    def _default_adapters(self) -> list[KnowledgeAdapter]:
        return [
            ObsidianKnowledgeAdapter(),
            SemanticSearchAdapter(),
            LlamaIndexKnowledgeAdapter(),
            KiwixWikipediaAdapter(),
            MemoryKnowledgeAdapter(),
        ]

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        sources: list[str] | None = None,
    ) -> list[KnowledgeResult]:
        """Search all enabled knowledge sources through one API."""
        query = str(query or "").strip()
        if not query:
            return []

        wanted_sources = {source.lower() for source in sources or []}
        results: list[KnowledgeResult] = []
        for adapter in self.adapters:
            if wanted_sources and adapter.name.lower() not in wanted_sources:
                continue
            try:
                results.extend(adapter.search(query, limit))
            except Exception as exc:
                logger.warning("Knowledge adapter search failed: %s: %s", adapter.name, exc)

        return self._rank_results(results)[:limit]

    def index(self, source: KnowledgeSource | str | Path | dict[str, Any]) -> dict[str, Any]:
        """Index a source through the adapter that supports it."""
        normalized = self._normalize_source(source)
        outcomes = []
        for adapter in self.adapters:
            try:
                outcome = adapter.index(normalized)
            except Exception as exc:
                logger.warning("Knowledge adapter index failed: %s: %s", adapter.name, exc)
                outcome = {"indexed": False, "source": adapter.name, "error": str(exc)}
            outcomes.append(outcome)

        return {
            "source": normalized.__dict__,
            "indexed": any(bool(item.get("indexed")) for item in outcomes),
            "outcomes": outcomes,
        }

    def get_context(
        self,
        query: str,
        *,
        limit: int = 5,
        sources: list[str] | None = None,
        max_chars: int = 4000,
    ) -> KnowledgeContext:
        """Return search results formatted as compact LLM context."""
        results = self.search(query, limit=limit, sources=sources)
        text = self._format_context(results, max_chars=max_chars)
        return KnowledgeContext(query=query, results=results, text=text)

    def suggest_notes(
        self,
        query: str,
        *,
        limit: int = 5,
        sources: list[str] | None = None,
    ) -> KnowledgeNotePlan:
        """Suggest Obsidian notes and graph links from retrieved knowledge."""
        results = self.search(query, limit=limit, sources=sources)
        suggestions: list[KnowledgeNoteSuggestion] = []
        titles = [self._topic_title(result.title) for result in results]

        for result in results:
            title = self._topic_title(result.title)
            related_titles = [
                candidate for candidate in titles if candidate and candidate.lower() != title.lower()
            ][:5]
            source_uri = result.uri or result.title
            summary = self._summarize_for_note(result.content)
            tags = self._tags_for_result(result)
            content = self._build_note_content(
                title=title,
                summary=summary,
                sources=[source_uri],
                links=related_titles,
                tags=tags,
                query=query,
            )
            suggestions.append(
                KnowledgeNoteSuggestion(
                    title=title,
                    summary=summary,
                    sources=[source_uri],
                    links=related_titles,
                    tags=tags,
                    confidence=self._suggestion_confidence(result),
                    reason=f"Matched '{query}' in {result.source}.",
                    content=content,
                )
            )

        return KnowledgeNotePlan(
            query=query,
            suggestions=suggestions,
            graph_edges=self._build_graph_edges(suggestions),
        )

    def write_suggested_notes(
        self,
        query: str,
        *,
        limit: int = 5,
        sources: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create suggested Obsidian notes and a graph index note."""
        plan = self.suggest_notes(query, limit=limit, sources=sources)
        bridge = self._get_obsidian_bridge()
        written_notes = []

        for suggestion in plan.suggestions:
            relative_path = f"Knowledge/Auto/{self._safe_filename(suggestion.title)}.md"
            bridge.create_note(relative_path, suggestion.content)
            written_notes.append(relative_path)

        graph_path = ""
        if plan.graph_edges:
            graph_path = "Knowledge/Graph.md"
            bridge.create_note(graph_path, self._build_graph_note(plan.graph_edges))

        return {
            "query": query,
            "suggested": len(plan.suggestions),
            "written": written_notes,
            "graph_edges": [edge.__dict__ for edge in plan.graph_edges],
            "graph_path": graph_path,
        }

    def _normalize_source(self, source: KnowledgeSource | str | Path | dict[str, Any]) -> KnowledgeSource:
        if isinstance(source, KnowledgeSource):
            return source
        if isinstance(source, Path):
            return KnowledgeSource(kind="file" if source.is_file() else "directory", uri=str(source))
        if isinstance(source, str):
            path = Path(source).expanduser()
            kind = "file" if path.is_file() else "directory"
            return KnowledgeSource(kind=kind, uri=source)
        if isinstance(source, dict):
            return KnowledgeSource(
                kind=str(source.get("kind") or source.get("type") or "directory"),
                uri=str(source.get("uri") or source.get("path") or ""),
                metadata=dict(source.get("metadata") or {}),
            )
        raise TypeError(f"Unsupported knowledge source: {type(source)!r}")

    def _get_obsidian_bridge(self) -> Any:
        if self._obsidian_bridge is None:
            if self._obsidian_bridge_factory is not None:
                self._obsidian_bridge = self._obsidian_bridge_factory()
            else:
                from memory.obsidian_vault import get_obsidian_bridge

                self._obsidian_bridge = get_obsidian_bridge()
        return self._obsidian_bridge

    def _topic_title(self, title: str) -> str:
        clean_title = Path(str(title or "Knowledge Note")).stem
        clean_title = re.sub(r"[_\-]+", " ", clean_title).strip()
        return clean_title[:80] or "Knowledge Note"

    def _safe_filename(self, title: str) -> str:
        safe = re.sub(r"[^\w\s-]", "", title).strip()
        safe = re.sub(r"\s+", " ", safe)
        return safe or "Knowledge Note"

    def _summarize_for_note(self, content: str) -> str:
        text = " ".join(str(content or "").split())
        if len(text) <= 480:
            return text
        return text[:477].rstrip() + "..."

    def _tags_for_result(self, result: KnowledgeResult) -> list[str]:
        tags = ["mica-knowledge", str(result.source).replace(" ", "-")]
        categories = result.metadata.get("categories")
        if isinstance(categories, list):
            tags.extend(str(category).replace(" ", "-") for category in categories[:5])
        elif isinstance(categories, str):
            tags.extend(part.strip().replace(" ", "-") for part in categories.split(",")[:5])
        return [tag for tag in tags if tag]

    def _suggestion_confidence(self, result: KnowledgeResult) -> float:
        if result.score is None:
            return 0.55
        if result.source in {"documents", "wikipedia"}:
            return max(0.1, min(0.95, 1.0 - float(result.score)))
        return max(0.1, min(0.95, float(result.score)))

    def _build_note_content(
        self,
        *,
        title: str,
        summary: str,
        sources: list[str],
        links: list[str],
        tags: list[str],
        query: str,
    ) -> str:
        lines = [
            f"# {title}",
            "",
            "---",
            "type: knowledge-note",
            f"query: {query}",
            "tags:",
        ]
        lines.extend(f"  - {tag}" for tag in tags)
        lines.extend(["---", "", "## Summary", "", summary or "No summary available.", ""])
        lines.extend(["## Sources", ""])
        lines.extend(f"- {source}" for source in sources)
        lines.extend(["", "## Links", ""])
        if links:
            lines.extend(f"- [[{link}]]" for link in links)
        else:
            lines.append("- ")
        return "\n".join(lines).rstrip() + "\n"

    def _build_graph_edges(
        self, suggestions: list[KnowledgeNoteSuggestion]
    ) -> list[KnowledgeGraphEdge]:
        edges: list[KnowledgeGraphEdge] = []
        seen = set()
        for suggestion in suggestions:
            for link in suggestion.links:
                key = (suggestion.title.lower(), link.lower())
                if key in seen:
                    continue
                seen.add(key)
                edges.append(
                    KnowledgeGraphEdge(
                        source=suggestion.title,
                        target=link,
                        evidence=suggestion.sources[0] if suggestion.sources else "",
                    )
                )
        return edges

    def _build_graph_note(self, edges: list[KnowledgeGraphEdge]) -> str:
        lines = ["# Knowledge Graph", "", "## Edges", ""]
        for edge in edges:
            evidence = f" ({edge.evidence})" if edge.evidence else ""
            lines.append(f"- [[{edge.source}]] -> [[{edge.target}]]: {edge.relation}{evidence}")
        return "\n".join(lines).rstrip() + "\n"

    def _rank_results(self, results: list[KnowledgeResult]) -> list[KnowledgeResult]:
        def key(result: KnowledgeResult) -> tuple[int, float]:
            score = result.score
            if score is None:
                return (0, 0.0)
            # Chroma distances are lower-is-better; memory relevance is higher-is-better.
            if result.source in {"documents", "wikipedia"}:
                return (1, -float(score))
            return (1, float(score))

        return sorted(results, key=key, reverse=True)

    def _format_context(self, results: list[KnowledgeResult], *, max_chars: int) -> str:
        if not results:
            return ""

        parts = []
        for index, result in enumerate(results, start=1):
            location = f" ({result.uri})" if result.uri else ""
            content = " ".join(result.content.split())
            parts.append(f"[{index}] {result.source}: {result.title}{location}\n{content}")

        text = "\n\n".join(parts)
        if len(text) > max_chars:
            text = text[: max_chars - 3].rstrip() + "..."
        return text


_knowledge_manager: KnowledgeManager | None = None


def get_knowledge_manager() -> KnowledgeManager:
    """Return the process-wide KnowledgeManager instance."""
    global _knowledge_manager
    if _knowledge_manager is None:
        _knowledge_manager = KnowledgeManager()
    return _knowledge_manager
