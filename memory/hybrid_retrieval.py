"""
Hybrid Retrieval System for Mark-XXXIX Memory
============================================
Provides intelligent memory retrieval with semantic similarity, keyword matching,
time weighting, relevance scoring, and conflict detection.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from core.logger import get_logger
from memory.memory_manager import MEMORY_PATH, load_memory

logger = get_logger(__name__)


class MemoryCategory(Enum):
    """Memory categories."""

    IDENTITY = "identity"
    PREFERENCES = "preferences"
    PROJECTS = "projects"
    RELATIONSHIPS = "relationships"
    WISHES = "wishes"
    NOTES = "notes"


class MemoryConfidence(Enum):
    """Confidence levels for memory entries."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCERTAIN = "uncertain"


@dataclass
class MemoryEntry:
    """Represents a single memory entry."""

    category: str
    key: str
    value: str
    created: str
    updated: str
    confidence: MemoryConfidence = MemoryConfidence.MEDIUM
    access_count: int = 0
    last_accessed: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    source: Optional[str] = None  # Where this memory came from

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "category": self.category,
            "key": self.key,
            "value": self.value,
            "created": self.created,
            "updated": self.updated,
            "confidence": self.confidence.value,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed,
            "tags": self.tags,
            "source": self.source,
        }


@dataclass
class RetrievalResult:
    """Result of a memory retrieval operation."""

    entry: MemoryEntry
    relevance_score: float
    match_type: str  # semantic, keyword, exact, hybrid
    confidence: MemoryConfidence
    age_days: float
    source_info: str = ""


@dataclass
class ConflictInfo:
    """Information about conflicting memories."""

    entries: List[MemoryEntry]
    conflict_type: str  # value_conflict, temporal_conflict, category_conflict
    description: str


class HybridRetrieval:
    """
    Provides hybrid retrieval with semantic similarity, keyword matching,
    time weighting, and conflict detection.
    """

    def __init__(self, memory_path: Optional[Path] = None):
        """
        Initialize the hybrid retrieval system.

        Args:
            memory_path: Path to memory file
        """
        self.memory_path = memory_path or MEMORY_PATH
        self.memory_cache: Optional[Dict[str, Any]] = None
        self.memory_entries: List[MemoryEntry] = []
        self._cache_timestamp: Optional[datetime] = None

        # Configuration
        self.semantic_weight = 0.4
        self.keyword_weight = 0.3
        self.time_weight = 0.2
        self.confidence_weight = 0.1
        self.max_results = 10
        self.min_relevance_threshold = 0.3

        logger.info("Hybrid retrieval system initialized")

    def _load_memory(self):
        """Load and parse memory into structured entries."""
        try:
            memory_data = load_memory()

            entries = []
            for category, items in memory_data.items():
                if not isinstance(items, dict):
                    continue

                for key, entry_data in items.items():
                    if not isinstance(entry_data, dict):
                        continue

                    entry = MemoryEntry(
                        category=category,
                        key=key,
                        value=entry_data.get("value", ""),
                        created=entry_data.get("created", datetime.now().isoformat()),
                        updated=entry_data.get("updated", datetime.now().isoformat()),
                        confidence=self._infer_confidence(entry_data),
                        access_count=entry_data.get("access_count", 0),
                        last_accessed=entry_data.get("last_accessed"),
                        tags=entry_data.get("tags", []),
                        source=entry_data.get("source"),
                    )
                    entries.append(entry)

            self.memory_entries = entries
            self._cache_timestamp = datetime.now()
            logger.debug(f"Loaded {len(entries)} memory entries")

        except Exception as e:
            logger.error(f"Failed to load memory: {e}")
            self.memory_entries = []

    def _infer_confidence(self, entry_data: Dict[str, Any]) -> MemoryConfidence:
        """Infer confidence level from entry data."""
        # Check for explicit confidence
        if "confidence" in entry_data:
            try:
                return MemoryConfidence(entry_data["confidence"])
            except ValueError:
                pass

        # Infer from access count
        access_count = entry_data.get("access_count", 0)
        if access_count > 10:
            return MemoryConfidence.HIGH
        elif access_count > 5:
            return MemoryConfidence.MEDIUM
        elif access_count > 0:
            return MemoryConfidence.LOW
        else:
            return MemoryConfidence.UNCERTAIN

    def _calculate_age_days(self, entry: MemoryEntry) -> float:
        """Calculate age of entry in days."""
        try:
            updated = datetime.fromisoformat(entry.updated)
            age = (datetime.now() - updated).total_seconds() / 86400
            return age
        except Exception:
            return 365.0  # Default to 1 year if parsing fails

    def _calculate_keyword_score(self, query: str, entry: MemoryEntry) -> float:
        """Calculate keyword matching score."""
        query_lower = query.lower()
        value_lower = entry.value.lower()
        key_lower = entry.key.lower()

        # Exact match
        if query_lower == key_lower or query_lower == value_lower:
            return 1.0

        # Partial match in key
        if query_lower in key_lower:
            return 0.8

        # Partial match in value
        if query_lower in value_lower:
            return 0.7

        # Word overlap
        query_words = set(query_lower.split())
        value_words = set(value_lower.split())
        key_words = set(key_lower.split())

        all_words = value_words | key_words
        if not all_words:
            return 0.0

        overlap = len(query_words & all_words)
        if overlap > 0:
            return min(0.6, overlap / len(query_words))

        return 0.0

    def _calculate_semantic_score(self, query: str, entry: MemoryEntry) -> float:
        """
        Calculate semantic similarity score.
        This is a simplified version - in production would use embeddings.
        """
        # Simplified semantic matching using word overlap and context
        query_words = set(query.lower().split())
        value_lower = entry.value.lower()

        # Check for related terms
        related_terms = {
            "skin": ["dermatologist", "acne", "blemish", "pimple", "rash"],
            "work": ["job", "project", "task", "deadline"],
            "health": ["doctor", "medical", "wellness", "fitness"],
            "schedule": ["calendar", "appointment", "meeting", "time"],
        }

        score = 0.0
        for word in query_words:
            # Direct match
            if word in value_lower:
                score += 0.5

            # Related terms
            for category, terms in related_terms.items():
                if word in terms:
                    for term in terms:
                        if term in value_lower:
                            score += 0.3

        return min(1.0, score)

    def _calculate_time_score(self, entry: MemoryEntry) -> float:
        """Calculate time-based score (newer = higher)."""
        age_days = self._calculate_age_days(entry)

        # Exponential decay: newer entries get higher scores
        if age_days < 1:
            return 1.0
        elif age_days < 7:
            return 0.8
        elif age_days < 30:
            return 0.6
        elif age_days < 90:
            return 0.4
        else:
            return 0.2

    def _calculate_confidence_score(self, entry: MemoryEntry) -> float:
        """Calculate confidence score."""
        confidence_map = {
            MemoryConfidence.HIGH: 1.0,
            MemoryConfidence.MEDIUM: 0.7,
            MemoryConfidence.LOW: 0.4,
            MemoryConfidence.UNCERTAIN: 0.2,
        }
        return confidence_map.get(entry.confidence, 0.5)

    def retrieve(
        self, query: str, categories: Optional[List[str]] = None, max_results: Optional[int] = None
    ) -> List[RetrievalResult]:
        """
        Retrieve memories using hybrid scoring.

        Args:
            query: Search query
            categories: Optional category filter
            max_results: Maximum number of results

        Returns:
            List of retrieval results sorted by relevance
        """
        # Refresh cache if needed
        if (
            self._cache_timestamp is None
            or (datetime.now() - self._cache_timestamp).total_seconds() > 300
        ):
            self._load_memory()

        # Filter by category if specified
        entries = self.memory_entries
        if categories:
            entries = [e for e in entries if e.category in categories]

        # Calculate scores for each entry
        results = []
        for entry in entries:
            keyword_score = self._calculate_keyword_score(query, entry)
            semantic_score = self._calculate_semantic_score(query, entry)
            time_score = self._calculate_time_score(entry)
            confidence_score = self._calculate_confidence_score(entry)

            # Combined score
            combined_score = (
                self.semantic_weight * semantic_score
                + self.keyword_weight * keyword_score
                + self.time_weight * time_score
                + self.confidence_weight * confidence_score
            )

            # Determine match type
            if keyword_score >= 0.8:
                match_type = "exact"
            elif semantic_score > keyword_score:
                match_type = "semantic"
            elif keyword_score > 0:
                match_type = "keyword"
            else:
                match_type = "hybrid"

            # Only include if above threshold
            if combined_score >= self.min_relevance_threshold:
                result = RetrievalResult(
                    entry=entry,
                    relevance_score=combined_score,
                    match_type=match_type,
                    confidence=entry.confidence,
                    age_days=self._calculate_age_days(entry),
                    source_info=f"Source: {entry.source or 'unknown'}",
                )
                results.append(result)

        # Sort by relevance score
        results.sort(key=lambda r: r.relevance_score, reverse=True)

        # Limit results
        limit = max_results or self.max_results
        return results[:limit]

    def detect_conflicts(self, query: str) -> List[ConflictInfo]:
        """
        Detect conflicting memories for a given query.

        Args:
            query: Search query

        Returns:
            List of conflict information
        """
        results = self.retrieve(query, max_results=20)

        conflicts = []

        # Group by key
        key_groups: Dict[str, List[RetrievalResult]] = {}
        for result in results:
            key = result.entry.key
            if key not in key_groups:
                key_groups[key] = []
            key_groups[key].append(result)

        # Check for value conflicts within same key
        for key, group in key_groups.items():
            if len(group) > 1:
                # Check if values differ significantly
                values = [r.entry.value for r in group]
                unique_values = set(values)

                if len(unique_values) > 1:
                    conflict = ConflictInfo(
                        entries=[r.entry for r in group],
                        conflict_type="value_conflict",
                        description=f"Multiple different values for '{key}': {', '.join(unique_values[:3])}",
                    )
                    conflicts.append(conflict)

        # Check for temporal conflicts (old vs new)
        for key, group in key_groups.items():
            if len(group) > 1:
                # Sort by update time
                sorted_group = sorted(group, key=lambda r: r.entry.updated, reverse=True)

                # If newest and oldest have significantly different values
                newest = sorted_group[0].entry.value
                oldest = sorted_group[-1].entry.value

                if newest != oldest:
                    conflict = ConflictInfo(
                        entries=[r.entry for r in group],
                        conflict_type="temporal_conflict",
                        description=f"Value for '{key}' changed over time: '{oldest}' → '{newest}'",
                    )
                    conflicts.append(conflict)

        return conflicts

    def get_memory_summary(self) -> Dict[str, Any]:
        """
        Get summary of memory contents.

        Returns:
            Dictionary with memory statistics
        """
        if not self.memory_entries:
            self._load_memory()

        # Count by category
        category_counts: Dict[str, int] = {}
        confidence_counts: Dict[str, int] = {}

        for entry in self.memory_entries:
            category_counts[entry.category] = category_counts.get(entry.category, 0) + 1
            confidence_counts[entry.confidence.value] = (
                confidence_counts.get(entry.confidence.value, 0) + 1
            )

        # Calculate average age
        total_age = sum(self._calculate_age_days(e) for e in self.memory_entries)
        avg_age = total_age / len(self.memory_entries) if self.memory_entries else 0

        return {
            "total_entries": len(self.memory_entries),
            "category_counts": category_counts,
            "confidence_counts": confidence_counts,
            "average_age_days": avg_age,
            "last_updated": self._cache_timestamp.isoformat() if self._cache_timestamp else None,
        }

    def update_access_count(self, entry_key: str, category: str):
        """
        Update access count for a memory entry.

        Args:
            entry_key: Key of the entry
            category: Category of the entry
        """
        try:
            memory_data = load_memory()

            if category in memory_data and entry_key in memory_data[category]:
                entry_data = memory_data[category][entry_key]
                entry_data["access_count"] = entry_data.get("access_count", 0) + 1
                entry_data["last_accessed"] = datetime.now().isoformat()

                # Save back
                from memory.memory_manager import save_memory

                save_memory(memory_data)

                # Update cache
                self._load_memory()

        except Exception as e:
            logger.error(f"Failed to update access count: {e}")


# Global instance
_hybrid_retrieval: Optional[HybridRetrieval] = None


def get_hybrid_retrieval() -> HybridRetrieval:
    """Get the global hybrid retrieval instance."""
    global _hybrid_retrieval
    if _hybrid_retrieval is None:
        _hybrid_retrieval = HybridRetrieval()
    return _hybrid_retrieval
