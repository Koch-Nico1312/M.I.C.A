"""Non-destructive memory curation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from memory.memory_manager import forget, load_memory, remember_structured


@dataclass(frozen=True)
class MemorySuggestion:
    id: str
    kind: str
    title: str
    confidence: float
    entries: list[str]
    recommendation: str


def _entry_id(category: str, key: str) -> str:
    return f"{category}:{key}"


def _flatten(memory: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for category, items in memory.items():
        if not isinstance(items, dict):
            continue
        for key, entry in items.items():
            value = entry.get("value") if isinstance(entry, dict) else entry
            metadata = entry if isinstance(entry, dict) else {}
            rows.append(
                {
                    "id": _entry_id(category, key),
                    "category": category,
                    "key": key,
                    "value": str(value or ""),
                    "confidence": float(metadata.get("confidence", 0.75) or 0.75),
                    "tags": metadata.get("tags", []),
                    "updated": metadata.get("updated"),
                }
            )
    return rows


def build_curation_report(memory: dict[str, Any] | None = None) -> dict[str, Any]:
    memory = memory if memory is not None else load_memory()
    entries = _flatten(memory)
    suggestions: list[MemorySuggestion] = []

    seen_pairs: set[tuple[str, str]] = set()
    for index, left in enumerate(entries):
        for right in entries[index + 1 :]:
            if left["category"] != right["category"]:
                continue
            pair = tuple(sorted((left["id"], right["id"])))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            key_score = SequenceMatcher(None, left["key"].lower(), right["key"].lower()).ratio()
            value_score = SequenceMatcher(None, left["value"].lower(), right["value"].lower()).ratio()
            score = round((key_score * 0.4) + (value_score * 0.6), 3)
            if score >= 0.82:
                suggestions.append(
                    MemorySuggestion(
                        id=f"dup-{len(suggestions) + 1}",
                        kind="duplicate",
                        title=f"Possible duplicate in {left['category']}",
                        confidence=score,
                        entries=[left["id"], right["id"]],
                        recommendation="review_or_merge",
                    )
                )

    for entry in entries:
        if entry["confidence"] < 0.45:
            suggestions.append(
                MemorySuggestion(
                    id=f"low-{len(suggestions) + 1}",
                    kind="low_confidence",
                    title=f"Low confidence: {entry['key']}",
                    confidence=entry["confidence"],
                    entries=[entry["id"]],
                    recommendation="review",
                )
            )

    return {
        "entries": entries,
        "suggestions": [suggestion.__dict__.copy() for suggestion in suggestions],
        "counts": {
            "entries": len(entries),
            "suggestions": len(suggestions),
            "duplicates": sum(1 for item in suggestions if item.kind == "duplicate"),
            "low_confidence": sum(1 for item in suggestions if item.kind == "low_confidence"),
        },
    }


def apply_curation_action(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Apply explicit curation actions. Suggestions alone never mutate memory."""
    action = str(action or "").strip()
    if action == "delete":
        category = str(payload.get("category") or "")
        key = str(payload.get("key") or "")
        if not category or not key:
            raise ValueError("category and key are required")
        return {"status": forget(key, category), "curation": build_curation_report()}

    if action == "merge":
        category = str(payload.get("category") or "")
        target_key = str(payload.get("target_key") or "")
        source_keys = [str(item) for item in payload.get("source_keys", []) if str(item)]
        merged_value = str(payload.get("value") or "").strip()
        if not category or not target_key or not source_keys or not merged_value:
            raise ValueError("category, target_key, source_keys, and value are required")
        remember_structured(category, target_key, merged_value, tags=["curated", "merged"])
        for key in source_keys:
            if key != target_key:
                forget(key, category)
        return {"status": "merged", "curation": build_curation_report()}

    raise ValueError(f"unknown curation action: {action}")
