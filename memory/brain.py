"""
Memory Brain for JARVIS.

This module turns explicit memory requests and stable conversational facts into
structured long-term memory entries.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Iterable, Optional

from .memory_manager import DEFAULT_MEMORY_CATEGORIES, save_memory, update_memory

try:
    from core.logger import get_logger

    logger = get_logger(__name__)
except Exception:  # pragma: no cover - fallback for slim test environments
    import logging

    logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MemoryCandidate:
    category: str
    key: str
    value: str
    confidence: str = "medium"
    source: str = "conversation"
    reason: str = ""


def _normalize_text(text: str) -> str:
    text = str(text or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _normalize_key(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value or "memory_note"


def _strip_directive_prefix(text: str) -> str:
    text = _normalize_text(text)
    patterns = [
        r"^(?:bitte\s+)?(?:fuege|füge)\s+hinzu[,:\s]*",
        r"^(?:bitte\s+)?(?:merk|merke)\s+dir[,:\s]*",
        r"^(?:bitte\s+)?(?:speichere|speicher|notiere|schreibe|schreib)\s*(?:das|dir|mir)?[,:\s]*",
        r"^(?:please\s+)?(?:add|remember|save|note)\s*(?:this|that|it)?[,:\s]*",
    ]
    for pattern in patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    text = re.sub(r"^(?:dass|that)\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^bitte[:, ]*", "", text, flags=re.IGNORECASE)
    return text.strip(" .,:;")


class MemoryBrain:
    """
    Extracts stable facts from user messages and stores them in long-term memory.
    """

    _lock = Lock()

    def __init__(self, memory_path: Optional[Path] = None):
        self.memory_path = memory_path

    def handle_direct_request(self, text: str, source: str = "ui") -> tuple[bool, list[MemoryCandidate]]:
        """
        Handle a direct memory request such as "fuege ... hinzu" or "merke dir ...".

        Returns a tuple of (handled, saved_candidates).
        """
        normalized = _normalize_text(text)
        if not self._looks_like_direct_request(normalized):
            return False, []

        candidates = self.extract_candidates(normalized, explicit=True, source=source)
        if not candidates:
            fallback = MemoryCandidate(
                category="notes",
                key=f"memory_{datetime.now():%Y%m%d_%H%M%S}",
                value=_strip_directive_prefix(normalized),
                confidence="high",
                source=source,
                reason="direct_request_fallback",
            )
            candidates = [fallback]

        self.store_candidates(candidates)
        return True, candidates

    def observe(self, text: str, source: str = "conversation") -> list[MemoryCandidate]:
        """
        Observe a conversation turn and store stable facts when we can infer them safely.
        """
        normalized = _normalize_text(text)
        if not normalized:
            return []

        candidates = self.extract_candidates(normalized, explicit=False, source=source)
        if candidates:
            self.store_candidates(candidates)
        return candidates

    def handle_memory_query(self, text: str) -> str | None:
        """
        Handle questions like "was weißt du über mich?" or "was weißt du über Japan?".
        Returns a human-readable response or None if the text is not a memory query.
        """
        normalized = _normalize_text(text)
        if not self._looks_like_query(normalized):
            return None

        query = self._extract_query_term(normalized)
        if not query:
            return self.describe_memory()
        return self.describe_memory(query=query)

    def handle_forget_request(self, text: str) -> tuple[bool, str]:
        """
        Handle explicit forget/delete requests.
        Returns (handled, response).
        """
        normalized = _normalize_text(text)
        query = self._extract_forget_term(normalized)
        if not query:
            return False, ""

        memory = self._load_memory_snapshot()
        removed = self._remove_matching_entries(memory, query)
        if not removed:
            return True, f"Ich habe nichts gefunden, das zu '{query}' passt."

        save_memory(memory, memory_path=self.memory_path)
        if removed == 1:
            return True, f"Ich habe {removed} Erinnerung zu '{query}' gelöscht."
        return True, f"Ich habe {removed} Erinnerungen zu '{query}' gelöscht."

    def extract_candidates(
        self,
        text: str,
        explicit: bool = False,
        source: str = "conversation",
    ) -> list[MemoryCandidate]:
        text = _normalize_text(text)
        if not text:
            return []

        working_text = _strip_directive_prefix(text) if explicit else text
        candidates: list[MemoryCandidate] = []

        for clause in self._split_clauses(working_text):
            candidates.extend(self._extract_identity(clause, source=source))
            candidates.extend(self._extract_preferences(clause, source=source))
            candidates.extend(self._extract_projects(clause, source=source))
            candidates.extend(self._extract_wishes(clause, source=source))
            candidates.extend(self._extract_relationships(clause, source=source))

        if explicit and not candidates:
            candidates.append(
                MemoryCandidate(
                    category="notes",
                    key=f"memory_{datetime.now():%Y%m%d_%H%M%S}",
                    value=working_text,
                    confidence="high",
                    source=source,
                    reason="explicit_note",
                )
            )

        return self._dedupe(candidates)

    @staticmethod
    def _split_clauses(text: str) -> list[str]:
        parts = re.split(r"\s+(?:und|aber|sowie)\s+|(?<=[.!?])\s+", text)
        return [part.strip(" ,;:.") for part in parts if part.strip(" ,;:.")]

    def store_candidates(self, candidates: Iterable[MemoryCandidate]) -> list[MemoryCandidate]:
        saved: list[MemoryCandidate] = []
        for candidate in self._dedupe(candidates):
            payload = {
                candidate.category: {
                    candidate.key: {
                        "value": candidate.value,
                        "confidence": candidate.confidence,
                        "source": candidate.source,
                        "tags": self._candidate_tags(candidate),
                    }
                }
            }
            update_memory(payload, memory_path=self.memory_path)
            saved.append(candidate)
            logger.info(
                "[MemoryBrain] Stored %s/%s from %s",
                candidate.category,
                candidate.key,
                candidate.source,
            )
        return saved

    def describe_memory(self, query: str | None = None, limit: int = 6) -> str:
        """
        Return a concise human-readable memory summary.
        """
        memory = self._load_memory_snapshot()
        entries = self._collect_entries(memory)
        if query:
            entries = [entry for entry in entries if self._entry_matches_query(entry, query)]

        if not entries:
            if query:
                return f"Ich habe dazu noch nichts gespeichert: {query}."
            return "Ich habe noch nichts im Langzeitgedächtnis gespeichert."

        lines = []
        header = "Das weiß ich über dich:" if not query else f"Das weiß ich zu '{query}':"
        lines.append(header)
        for entry in entries[:limit]:
            lines.append(f"- {entry['category']}/{entry['key']}: {entry['value']}")
        if len(entries) > limit:
            lines.append(f"- ... und {len(entries) - limit} weitere Einträge")
        return "\n".join(lines)

    def _candidate_tags(self, candidate: MemoryCandidate) -> list[str]:
        tags = ["memory_brain"]
        if candidate.confidence:
            tags.append(f"confidence/{candidate.confidence}")
        if candidate.source:
            tags.append(f"source/{candidate.source}")
        if candidate.reason:
            tags.append(candidate.reason)
        return tags

    def _load_memory_snapshot(self) -> dict:
        from .memory_manager import load_memory

        return load_memory(memory_path=self.memory_path)

    def _collect_entries(self, memory: dict) -> list[dict]:
        entries: list[dict] = []
        for category, items in memory.items():
            entries.extend(self._collect_entry_values(category, "", items))
        return entries

    def _collect_entry_values(self, category: str, key_prefix: str, value: object) -> list[dict]:
        if isinstance(value, dict):
            if "value" in value:
                raw_value = value.get("value", "")
                return [
                    {
                        "category": category,
                        "key": key_prefix,
                        "value": str(raw_value),
                        "entry": value,
                    }
                ] if str(raw_value).strip() else []

            entries: list[dict] = []
            for key, child in value.items():
                child_key = f"{key_prefix}.{key}" if key_prefix else str(key)
                entries.extend(self._collect_entry_values(category, child_key, child))
            return entries

        if isinstance(value, list):
            raw_value = ", ".join(str(item) for item in value if str(item).strip())
        else:
            raw_value = str(value) if value is not None else ""

        return [
            {
                "category": category,
                "key": key_prefix,
                "value": raw_value,
                "entry": {"value": raw_value},
            }
        ] if key_prefix and raw_value.strip() else []

    def _entry_matches_query(self, entry: dict, query: str) -> bool:
        haystack = " ".join(
            [
                str(entry.get("category", "")),
                str(entry.get("key", "")),
                str(entry.get("value", "")),
            ]
        ).lower()
        tokens = [token for token in re.findall(r"[\w#äöüß]+", query.lower()) if token]
        if not tokens:
            return query.lower() in haystack
        return any(token in haystack for token in tokens)

    def _remove_matching_entries(self, memory: dict, query: str) -> int:
        removed = 0
        for category, items in list(memory.items()):
            if not isinstance(items, dict):
                continue
            for key in list(items.keys()):
                entry = items.get(key)
                if not isinstance(entry, dict):
                    continue
                if self._entry_matches_query(
                    {"category": category, "key": key, "value": entry.get("value", "")},
                    query,
                ):
                    del items[key]
                    removed += 1
        return removed

    @staticmethod
    def _looks_like_query(text: str) -> bool:
        patterns = [
            r"\bwas\s+wei(?:s|ss|ß)t\s+du\b",
            r"\bwas\s+hast\s+du\s+dir\s+gemerkt\b",
            r"\bwhat\s+do\s+you\s+know\b",
            r"\bshow\s+memory\b",
            r"\berinnerst\s+du\s+dich\s+an\b",
            r"\bwas\s+ist\s+in\s+deinem\s+gedaechtnis\b",
        ]
        return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)

    @staticmethod
    def _extract_query_term(text: str) -> str:
        patterns = [
            r"\b(?:was\s+wei(?:s|ss|ß)t\s+du\s+über|was\s+wei(?:s|ss|ß)t\s+du\s+ueber|what\s+do\s+you\s+know\s+about|erinnerst\s+du\s+dich\s+an)\s+(?P<value>.+)$",
            r"\b(?:was\s+wei[sz]t\s+du|was\s+hast\s+du\s+dir\s+gemerkt|show\s+memory)\s*$",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match and "value" in match.groupdict():
                value = match.group("value").strip(" ?!.,:")
                if value.lower() in {"mich", "mir", "me", "about me", "über mich", "ueber mich"}:
                    return ""
                return value
        return ""

    @staticmethod
    def _extract_forget_term(text: str) -> str:
        patterns = [
            r"\b(?:vergiss|lösche|loesche|forget|delete)\s+(?P<value>.+)$",
            r"\b(?:entferne)\s+(?P<value>.+?)\s+aus\s+(?:deinem\s+)?gedaechtnis$",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                value = match.group("value").strip(" ?!.,:")
                value = re.sub(r"\bbitte\b$", "", value, flags=re.IGNORECASE).strip(" ?!.,:")
                return value
        return ""

    @staticmethod
    def _dedupe(candidates: Iterable[MemoryCandidate]) -> list[MemoryCandidate]:
        seen: set[tuple[str, str, str]] = set()
        unique: list[MemoryCandidate] = []
        for candidate in candidates:
            key = (candidate.category, candidate.key, candidate.value)
            if key in seen:
                continue
            seen.add(key)
            unique.append(candidate)
        return unique

    @staticmethod
    def _looks_like_direct_request(text: str) -> bool:
        patterns = [
            r"\b(fuege|füge)\s+hinzu\b",
            r"\b(merk|merke)\s+dir\b",
            r"\b(speichere|speicher|notiere|schreibe|schreib)\b",
            r"\b(add|remember|save|note)\b",
        ]
        return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)

    @staticmethod
    def _clean_value(value: str) -> str:
        value = value.strip(" .,:;")
        value = re.sub(
            r"^(?:einem|einer|einen|eine|ein|der|die|das|dem|den)\s+",
            "",
            value,
            flags=re.IGNORECASE,
        )
        return value.strip(" .,:;")

    def _extract_identity(self, text: str, source: str) -> list[MemoryCandidate]:
        results: list[MemoryCandidate] = []
        patterns = [
            (r"\b(?:ich hei(?:s|ss|ß)e|mein name ist|call me)\s+(?P<value>.+)$", "name", "high"),
            (r"\b(?:ich bin|i am)\s+(?P<value>\d{1,3})\s*(?:jahre alt|years old)?$", "age", "high"),
            (r"\b(?:ich wohne in|ich lebe in|my city is)\s+(?P<value>.+)$", "city", "high"),
            (r"\b(?:ich arbeite als|mein job ist|i work as)\s+(?P<value>.+)$", "job", "high"),
            (r"\b(?:ich spreche|my language is)\s+(?P<value>.+)$", "language", "medium"),
            (r"\b(?:ich komme aus|i am from)\s+(?P<value>.+)$", "origin", "medium"),
        ]
        for pattern, key, confidence in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            value = self._clean_value(match.group("value"))
            if not value:
                continue
            results.append(
                MemoryCandidate(
                    category="identity",
                    key=key,
                    value=value,
                    confidence=confidence,
                    source=source,
                    reason=f"identity:{key}",
                )
            )
        return results

    def _extract_preferences(self, text: str, source: str) -> list[MemoryCandidate]:
        results: list[MemoryCandidate] = []
        patterns = [
            (
                r"\b(?:ich mag|ich liebe|i like|i love)\s+(?P<value>.+)$",
                "likes",
                "high",
                "positive",
            ),
            (
                r"\b(?:ich\s+)?(?P<value>.+?)\s+(?:mag|liebe|love)\b$",
                "likes",
                "medium",
                "positive_inverse",
            ),
            (
                r"\b(?:ich hasse|ich mag nicht|i dislike|i hate)\s+(?P<value>.+)$",
                "dislikes",
                "high",
                "negative",
            ),
            (
                r"\b(?:ich\s+)?(?P<value>.+?)\s+(?:hasse|mag nicht|dislike|hate)\b$",
                "dislikes",
                "medium",
                "negative_inverse",
            ),
            (
                r"\b(?:mein lieblings(?:essen|getrank|getränk|farbe|spiel|film|song|musik|sport) ist|my favorite (?P<kind>[a-z ]+) is)\s+(?P<value>.+)$",
                "favorite",
                "high",
                "favorite",
            ),
        ]

        for pattern, key_prefix, confidence, reason in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue

            value = self._clean_value(match.group("value"))
            if not value:
                continue

            if key_prefix == "favorite":
                kind = match.groupdict().get("kind") or "item"
                key = f"favorite_{_normalize_key(kind)}"
                category = "preferences"
            elif reason == "negative":
                key = f"dislikes_{_normalize_key(value)}"
                category = "preferences"
            elif reason == "negative_inverse":
                key = f"dislikes_{_normalize_key(value)}"
                category = "preferences"
            else:
                key = f"likes_{_normalize_key(value)}"
                category = "preferences"

            results.append(
                MemoryCandidate(
                    category=category,
                    key=key,
                    value=value,
                    confidence=confidence,
                    source=source,
                    reason=f"preferences:{reason}",
                )
            )

        return results

    def _extract_projects(self, text: str, source: str) -> list[MemoryCandidate]:
        results: list[MemoryCandidate] = []
        patterns = [
            (r"\b(?:ich arbeite an|i'?m working on|im working on|ich baue|ich entwickle)\s+(?P<value>.+)$", "current_project", "high"),
            (r"\b(?:mein projekt ist|my project is)\s+(?P<value>.+)$", "project", "medium"),
            (r"\b(?:ich plane|i plan to|ich will bauen|i want to build)\s+(?P<value>.+)$", "goal", "medium"),
        ]
        for pattern, key, confidence in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            value = self._clean_value(match.group("value"))
            if not value:
                continue
            results.append(
                MemoryCandidate(
                    category="projects",
                    key=key if key != "project" else f"project_{_normalize_key(value)[:24]}",
                    value=value,
                    confidence=confidence,
                    source=source,
                    reason=f"projects:{key}",
                )
            )
        return results

    def _extract_wishes(self, text: str, source: str) -> list[MemoryCandidate]:
        results: list[MemoryCandidate] = []
        patterns = [
            (r"\b(?:ich will|ich möchte|ich moechte|i want to|i want)\s+(?P<value>.+)$", "wish", "high"),
            (r"\b(?:mein ziel ist|my goal is)\s+(?P<value>.+)$", "goal", "high"),
            (r"\b(?:ich plane|i plan to)\s+(?P<value>.+)$", "plan", "medium"),
        ]
        for pattern, key, confidence in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            value = self._clean_value(match.group("value"))
            if not value:
                continue
            results.append(
                MemoryCandidate(
                    category="wishes",
                    key=f"{key}_{_normalize_key(value)[:32]}",
                    value=value,
                    confidence=confidence,
                    source=source,
                    reason=f"wishes:{key}",
                )
            )
        return results

    def _extract_relationships(self, text: str, source: str) -> list[MemoryCandidate]:
        results: list[MemoryCandidate] = []
        patterns = [
            (r"\b(?:meine mutter heisst|my mother is|my mom is)\s+(?P<value>.+)$", "mother", "medium"),
            (r"\b(?:mein vater heisst|my father is|my dad is)\s+(?P<value>.+)$", "father", "medium"),
            (r"\b(?:meine schwester heisst|my sister is)\s+(?P<value>.+)$", "sister", "medium"),
            (r"\b(?:mein bruder heisst|my brother is)\s+(?P<value>.+)$", "brother", "medium"),
            (r"\b(?:mein freund heisst|my friend is|my partner is)\s+(?P<value>.+)$", "close_person", "medium"),
        ]
        for pattern, key, confidence in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            value = self._clean_value(match.group("value"))
            if not value:
                continue
            results.append(
                MemoryCandidate(
                    category="relationships",
                    key=f"{key}_{_normalize_key(value)[:32]}",
                    value=value,
                    confidence=confidence,
                    source=source,
                    reason=f"relationships:{key}",
                )
            )
        return results


_memory_brain: Optional[MemoryBrain] = None
_memory_brain_lock = Lock()


def get_memory_brain(memory_path: Optional[Path] = None) -> MemoryBrain:
    global _memory_brain
    if _memory_brain is None:
        with _memory_brain_lock:
            if _memory_brain is None:
                _memory_brain = MemoryBrain(memory_path=memory_path)
    return _memory_brain
