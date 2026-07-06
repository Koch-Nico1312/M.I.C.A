"""Crawl4AI-powered web crawling action for M.I.C.A."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from core.document_ingestion import IngestionRecord, chunk_text
from core.paths import resolve_relative_path


TOOL_DECLARATION = {
    "name": "crawl_url",
    "description": (
        "Crawls a URL with Crawl4AI and returns clean LLM-ready Markdown. "
        "Optionally saves the crawl artifact and indexes it into semantic search when RAG is enabled."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "url": {"type": "STRING", "description": "URL to crawl"},
            "query": {
                "type": "STRING",
                "description": "Optional focus query for content filtering.",
            },
            "max_chars": {
                "type": "INTEGER",
                "description": "Maximum Markdown characters to return and persist.",
            },
            "cache_mode": {
                "type": "STRING",
                "description": "enabled | bypass. Defaults to enabled.",
            },
            "headless": {
                "type": "BOOLEAN",
                "description": "Run the browser headlessly. Defaults to true.",
            },
            "save": {
                "type": "BOOLEAN",
                "description": "Save Markdown and chunk metadata under data/web_crawls. Defaults to true.",
            },
            "index": {
                "type": "BOOLEAN",
                "description": "Index the crawled Markdown into semantic search if RAG is enabled.",
            },
        },
        "required": ["url"],
    },
}


def _slugify_url(url: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", url).strip("-").lower()
    return (slug[:72] or "crawl") + "-" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]


def _run(coro):
    """Run an async Crawl4AI call from the sync action surface."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    if loop.is_running():
        new_loop = asyncio.new_event_loop()
        try:
            return new_loop.run_until_complete(coro)
        finally:
            new_loop.close()
    return loop.run_until_complete(coro)


async def _crawl_with_crawl4ai(
    url: str,
    *,
    query: str = "",
    cache_mode: str = "enabled",
    headless: bool = True,
) -> dict[str, Any]:
    try:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig
        from crawl4ai.content_filter_strategy import BM25ContentFilter, PruningContentFilter
        from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
    except ImportError as exc:
        raise RuntimeError(
            "Crawl4AI is not installed. Install it with `pip install crawl4ai` "
            "and run `python -m playwright install` if browser binaries are missing."
        ) from exc

    selected_cache_mode = CacheMode.BYPASS if cache_mode.lower() == "bypass" else CacheMode.ENABLED
    content_filter = (
        BM25ContentFilter(user_query=query, bm25_threshold=1.0)
        if query
        else PruningContentFilter(threshold=0.48, threshold_type="fixed", min_word_threshold=0)
    )
    run_config = CrawlerRunConfig(
        cache_mode=selected_cache_mode,
        markdown_generator=DefaultMarkdownGenerator(content_filter=content_filter),
    )
    browser_config = BrowserConfig(headless=headless, verbose=False)

    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(url=url, config=run_config)

    markdown_obj = getattr(result, "markdown", None)
    fit_markdown = getattr(markdown_obj, "fit_markdown", "") if markdown_obj else ""
    raw_markdown = getattr(markdown_obj, "raw_markdown", "") if markdown_obj else ""
    markdown = fit_markdown or raw_markdown or getattr(result, "markdown", "") or ""
    if not isinstance(markdown, str):
        markdown = str(markdown)

    return {
        "url": url,
        "markdown": markdown.strip(),
        "success": bool(getattr(result, "success", True)),
        "status_code": getattr(result, "status_code", None),
        "error": getattr(result, "error_message", None) or getattr(result, "error", None),
    }


def _save_crawl_artifact(url: str, markdown: str, metadata: dict[str, Any]) -> dict[str, str]:
    out_dir = resolve_relative_path("data/web_crawls")
    out_dir.mkdir(parents=True, exist_ok=True)

    slug = _slugify_url(url)
    markdown_path = out_dir / f"{slug}.md"
    chunks_path = out_dir / f"{slug}.chunks.json"

    markdown_path.write_text(markdown, encoding="utf-8")
    checksum = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
    chunks = chunk_text(markdown)
    now = datetime.now().isoformat()
    record = IngestionRecord(
        id=slug,
        name=f"{slug}.md",
        path=str(markdown_path),
        type="WEB",
        size=len(markdown.encode("utf-8")),
        checksum=checksum,
        status="chunked" if chunks else "uploaded",
        chunks=len(chunks),
        metadata={"url": url, **metadata, "text_preview": markdown[:240]},
        created_at=now,
        updated_at=now,
    )
    chunks_path.write_text(
        json.dumps(
            {"record": asdict(record), "chunks": [asdict(chunk) for chunk in chunks]},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return {"markdown_path": str(markdown_path), "chunks_path": str(chunks_path)}


def _index_crawl(url: str, markdown: str, metadata: dict[str, Any]) -> bool:
    try:
        from core.semantic_search import get_semantic_search

        semantic_search = get_semantic_search()
        return bool(
            semantic_search.index_text(
                document_id=f"web:{url}",
                title=url,
                content=markdown,
                metadata={"source": "crawl4ai", "url": url, **metadata},
            )
        )
    except Exception:
        return False


def crawl_url(parameters: dict, response=None, player=None, session_memory=None) -> str:
    params = parameters or {}
    url = str(params.get("url", "")).strip()
    if not url:
        return "Please provide a URL to crawl."
    if not url.startswith(("http://", "https://")):
        return "Please provide a full URL starting with http:// or https://."

    query = str(params.get("query", "") or "").strip()
    cache_mode = str(params.get("cache_mode", "enabled") or "enabled").lower()
    max_chars = int(params.get("max_chars") or 24000)
    headless = bool(params.get("headless", True))
    default_save = os.getenv("CRAWL4AI_SAVE_ARTIFACTS", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    save = bool(params.get("save", default_save))
    should_index = bool(params.get("index", False))

    if player:
        player.write_log(f"[Crawl4AI] {url}")

    try:
        result = _run(
            _crawl_with_crawl4ai(url, query=query, cache_mode=cache_mode, headless=headless)
        )
    except Exception as exc:
        return f"Crawl failed: {exc}"

    markdown = str(result.get("markdown") or "").strip()
    if max_chars > 0:
        markdown = markdown[:max_chars]

    metadata = {
        "crawler": "crawl4ai",
        "query": query,
        "status_code": result.get("status_code"),
        "success": result.get("success"),
    }
    saved_paths: dict[str, str] = {}
    if save and markdown:
        saved_paths = _save_crawl_artifact(url, markdown, metadata)

    indexed = _index_crawl(url, markdown, metadata) if should_index and markdown else False
    header = [
        f"Crawled: {url}",
        f"Characters: {len(markdown)}",
        f"Saved: {saved_paths.get('markdown_path', 'no')}",
        f"Indexed: {'yes' if indexed else 'no'}",
    ]
    if result.get("error"):
        header.append(f"Warning: {result['error']}")

    return "\n".join(header) + "\n\n" + (markdown or "No Markdown content was extracted.")
