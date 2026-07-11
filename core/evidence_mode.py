"""Evidence bundles with stable citation identifiers for knowledge answers."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

from core.knowledge_manager import get_knowledge_manager


class EvidenceMode:
    def build(self, query: str, *, limit: int = 5, sources: list[str] | None = None) -> dict[str, Any]:
        query = str(query or "").strip()
        if not query:
            raise ValueError("query is required")
        results = get_knowledge_manager().search(query, limit=max(1, min(int(limit), 12)), sources=sources)
        citations = []
        context_parts = []
        for index, result in enumerate(results, start=1):
            citation_id = f"E{index}"
            item = asdict(result)
            item["id"] = citation_id
            item["excerpt"] = str(result.content).strip()[:500]
            citations.append(item)
            context_parts.append(f"[{citation_id}] {result.title}: {item['excerpt']}")
        return {
            "query": query,
            "generated_at": datetime.now().isoformat(),
            "citation_count": len(citations),
            "citations": citations,
            "context": "\n\n".join(context_parts),
        }


_evidence_mode: EvidenceMode | None = None


def get_evidence_mode() -> EvidenceMode:
    global _evidence_mode
    if _evidence_mode is None:
        _evidence_mode = EvidenceMode()
    return _evidence_mode
