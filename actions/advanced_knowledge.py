"""Optional advanced document conversion and indexing actions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.advanced_knowledge_integrations import get_llama_index_adapter, get_markitdown_adapter


TOOL_DECLARATION = {
    "name": "advanced_knowledge",
    "description": (
        "Runs optional advanced knowledge tools: MarkItDown document conversion and "
        "LlamaIndex indexing/query. Use when ingesting PDFs/Office/audio as Markdown or "
        "when an advanced RAG index is explicitly useful."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {"type": "STRING", "description": "status | convert | index | query"},
            "path": {"type": "STRING", "description": "File or directory path for convert/index"},
            "query": {"type": "STRING", "description": "Query for LlamaIndex"},
            "persist_dir": {"type": "STRING", "description": "Optional LlamaIndex persistence directory"},
            "max_chars": {"type": "INTEGER", "description": "Maximum Markdown characters for convert"},
        },
        "required": ["action"],
    },
    "category": "knowledge",
    "enabled": True,
}


def advanced_knowledge(parameters: dict, response=None, player=None, session_memory=None, speak=None) -> str:
    params = parameters or {}
    action = str(params.get("action", "status")).lower().strip()

    if action == "status":
        payload = {
            "markitdown": {"available": get_markitdown_adapter().available()},
            "llama_index": {"available": get_llama_index_adapter().available()},
        }
    elif action == "convert":
        payload = get_markitdown_adapter().convert_file(
            Path(str(params.get("path", ""))),
            max_chars=int(params.get("max_chars", 120_000) or 120_000),
        ).to_dict()
    elif action == "index":
        payload = get_llama_index_adapter().index_path(
            Path(str(params.get("path", ""))),
            persist_dir=params.get("persist_dir"),
        ).to_dict()
    elif action == "query":
        payload = get_llama_index_adapter().query(
            str(params.get("query", "")),
            persist_dir=params.get("persist_dir"),
        ).to_dict()
    else:
        payload = {"ok": False, "error": f"Unknown advanced_knowledge action: {action}"}

    if player:
        player.write_log(f"[advanced-knowledge] {action}")
    return json.dumps(payload, indent=2, ensure_ascii=False)

