"""
Dream Memory - Background Memory Consolidation
===============================================
Implements Nova's dream memory system that consolidates recent conversations
in the background while Jarvis is in standby mode, linking concepts and
building structured long-term semantic memory.
"""

import json
import re
import sqlite3
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from memory.conversation_compression import get_compressor


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()
DREAM_DB_PATH = BASE_DIR / "data" / "dream_memory.db"
_lock = threading.Lock()


class DreamMemory:
    """
    Dream Memory consolidates conversations in the background to build
    structured long-term semantic memory by linking concepts and extracting
    key information from recent conversations.
    """

    def __init__(self, db_path: Path = DREAM_DB_PATH):
        self.db_path = db_path
        self._init_db()
        self._running = False
        self._dream_thread: Optional[threading.Thread] = None

    def _init_db(self) -> None:
        """Initialize the dream memory database."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with _lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Concepts table - stores extracted concepts/entities
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS concepts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    concept TEXT NOT NULL UNIQUE,
                    category TEXT,
                    first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                    frequency INTEGER DEFAULT 1,
                    context_summary TEXT,
                    related_concepts TEXT
                )
            """)

            # Relationships table - stores relationships between concepts
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS relationships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    concept_a TEXT NOT NULL,
                    concept_b TEXT NOT NULL,
                    relationship_type TEXT,
                    strength REAL DEFAULT 1.0,
                    first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(concept_a, concept_b, relationship_type)
                )
            """)

            # Facts table - stores extracted facts
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fact TEXT NOT NULL,
                    source_conversation_id INTEGER,
                    confidence REAL DEFAULT 1.0,
                    first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                    verified BOOLEAN DEFAULT FALSE
                )
            """)

            # Dream sessions table - tracks consolidation sessions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dream_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    end_time DATETIME,
                    conversations_processed INTEGER,
                    concepts_extracted INTEGER,
                    relationships_found INTEGER,
                    facts_extracted INTEGER
                )
            """)

            # Indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_concept_name ON concepts(concept)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_concept_category ON concepts(category)")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_rel_concept_a ON relationships(concept_a)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_rel_concept_b ON relationships(concept_b)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_fact_source ON facts(source_conversation_id)"
            )

            conn.commit()
            conn.close()

    def start_dreaming(self, interval_minutes: int = 30) -> None:
        """
        Start the background dream memory consolidation process.

        Args:
            interval_minutes: How often to run consolidation (default: 30 minutes)
        """
        if self._running:
            print("[Dream Memory] ⚠️ Already running")
            return

        self._running = True
        self._dream_thread = threading.Thread(
            target=self._dream_loop, args=(interval_minutes,), daemon=True
        )
        self._dream_thread.start()
        print(f"[Dream Memory] 🌙 Started (interval: {interval_minutes} minutes)")

    def stop_dreaming(self) -> None:
        """Stop the background dream memory consolidation."""
        self._running = False
        if self._dream_thread:
            self._dream_thread.join(timeout=10)
        print("[Dream Memory] 🛑 Stopped")

    def _dream_loop(self, interval_minutes: int) -> None:
        """Main dream loop that runs consolidation periodically."""
        while self._running:
            try:
                self.consolidate_recent_conversations()
            except Exception as e:
                print(f"[Dream Memory] ⚠️ Consolidation error: {e}")

            # Wait for next interval
            for _ in range(interval_minutes * 60):
                if not self._running:
                    return
                time.sleep(1)

    def consolidate_recent_conversations(self, hours: int = 24) -> Dict[str, int]:
        """
        Consolidate conversations from the last N hours.

        Returns:
            Statistics about the consolidation session.
        """
        print(f"[Dream Memory] 🌙 Starting consolidation (last {hours} hours)")

        # Get recent conversations
        compressor = get_compressor()
        recent = compressor.get_recent_conversations(limit=100)

        # Filter by time
        cutoff = datetime.now() - timedelta(hours=hours)
        filtered = [
            conv
            for conv in recent
            if datetime.fromisoformat(conv["timestamp"].replace("Z", "+00:00")) > cutoff
        ]

        if not filtered:
            print("[Dream Memory] 😴 No recent conversations to consolidate")
            return {"conversations_processed": 0}

        # Start dream session
        with _lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO dream_sessions (start_time)
                VALUES (?)
            """,
                (datetime.now().isoformat(),),
            )

            session_id = cursor.lastrowid
            conn.commit()

        stats = {
            "conversations_processed": 0,
            "concepts_extracted": 0,
            "relationships_found": 0,
            "facts_extracted": 0,
        }

        # Process each conversation
        for conv in filtered:
            try:
                messages = compressor.retrieve_conversation(conv["id"])
                if messages:
                    self._process_conversation(messages, conv["id"], stats)
                    stats["conversations_processed"] += 1
            except Exception as e:
                print(f"[Dream Memory] ⚠️ Error processing conv {conv['id']}: {e}")

        # Update dream session
        with _lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE dream_sessions
                SET end_time = ?,
                    conversations_processed = ?,
                    concepts_extracted = ?,
                    relationships_found = ?,
                    facts_extracted = ?
                WHERE id = ?
            """,
                (
                    datetime.now().isoformat(),
                    stats["conversations_processed"],
                    stats["concepts_extracted"],
                    stats["relationships_found"],
                    stats["facts_extracted"],
                    session_id,
                ),
            )

            conn.commit()
            conn.close()

        print(f"[Dream Memory] ✅ Consolidation complete: {stats}")
        return stats

    def _process_conversation(self, messages: List[Dict], conv_id: int, stats: Dict) -> None:
        """Process a single conversation to extract concepts, relationships, and facts."""
        # Combine all message content
        full_text = ""
        for msg in messages:
            if isinstance(msg, dict):
                content = msg.get("content", "")
                if content:
                    full_text += content + " "

        # Extract concepts using simple NLP
        concepts = self._extract_concepts(full_text)
        stats["concepts_extracted"] += len(concepts)

        # Store/update concepts
        for concept, category in concepts.items():
            self._update_concept(concept, category, full_text[:500])

        # Extract relationships
        relationships = self._extract_relationships(concepts, full_text)
        stats["relationships_found"] += len(relationships)

        for rel in relationships:
            self._update_relationship(rel)

        # Extract facts
        facts = self._extract_facts(full_text)
        stats["facts_extracted"] += len(facts)

        for fact in facts:
            self._store_fact(fact, conv_id)

    def _extract_concepts(self, text: str) -> Dict[str, str]:
        """
        Extract concepts/entities from text.
        Returns dict of {concept: category}
        """
        concepts = {}

        # Simple extraction patterns (in production, use NER model)
        text_lower = text.lower()

        # People names (capitalized words)
        names = re.findall(r"\b[A-Z][a-z]+\b", text)
        for name in set(names):
            if len(name) > 2:
                concepts[name] = "person"

        # Common categories with keywords
        categories = {
            "technology": ["computer", "software", "app", "program", "code", "ai", "robot"],
            "location": ["city", "country", "street", "building", "home", "office"],
            "time": ["today", "tomorrow", "yesterday", "week", "month", "year"],
            "emotion": ["happy", "sad", "angry", "excited", "worried", "love", "hate"],
            "action": ["do", "make", "create", "delete", "send", "receive", "buy", "sell"],
        }

        for category, keywords in categories.items():
            for keyword in keywords:
                if keyword in text_lower:
                    concepts[keyword] = category

        return concepts

    def _extract_relationships(self, concepts: Dict[str, str], text: str) -> List[Dict]:
        """Extract relationships between concepts."""
        relationships = []
        concept_list = list(concepts.keys())

        # Simple co-occurrence based relationships
        for i, concept_a in enumerate(concept_list):
            for concept_b in concept_list[i + 1 :]:
                if concept_a in text.lower() and concept_b in text.lower():
                    relationships.append(
                        {
                            "concept_a": concept_a,
                            "concept_b": concept_b,
                            "relationship_type": "co_occurs",
                            "strength": 1.0,
                        }
                    )

        return relationships

    def _extract_facts(self, text: str) -> List[str]:
        """Extract factual statements from text."""
        facts = []

        # Simple patterns for facts (in production, use fact extraction model)
        sentences = text.split(".")
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 20 and len(sentence) < 200:
                # Look for statements with is/are/was/were
                if any(word in sentence.lower() for word in [" is ", " are ", " was ", " were "]):
                    facts.append(sentence)

        return facts[:10]  # Limit to top 10 facts

    def _update_concept(self, concept: str, category: str, context: str) -> None:
        """Update or insert a concept in the database."""
        with _lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT OR REPLACE INTO concepts 
                (concept, category, last_seen, frequency, context_summary)
                VALUES (?, ?, ?, 
                    COALESCE((SELECT frequency FROM concepts WHERE concept = ?), 0) + 1,
                    ?)
            """,
                (concept, category, datetime.now().isoformat(), concept, context[:200]),
            )

            conn.commit()
            conn.close()

    def _update_relationship(self, relationship: Dict) -> None:
        """Update or insert a relationship in the database."""
        with _lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT OR REPLACE INTO relationships
                (concept_a, concept_b, relationship_type, strength, last_seen)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    relationship["concept_a"],
                    relationship["concept_b"],
                    relationship["relationship_type"],
                    relationship["strength"],
                    datetime.now().isoformat(),
                ),
            )

            conn.commit()
            conn.close()

    def _store_fact(self, fact: str, conv_id: int) -> None:
        """Store a fact in the database."""
        with _lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT OR IGNORE INTO facts
                (fact, source_conversation_id, confidence)
                VALUES (?, ?, 1.0)
            """,
                (fact, conv_id),
            )

            conn.commit()
            conn.close()

    def get_concept_info(self, concept: str) -> Optional[Dict]:
        """Get information about a specific concept."""
        with _lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT * FROM concepts WHERE concept = ?
            """,
                (concept,),
            )

            result = cursor.fetchone()
            conn.close()

        if result:
            return {
                "id": result[0],
                "concept": result[1],
                "category": result[2],
                "first_seen": result[3],
                "last_seen": result[4],
                "frequency": result[5],
                "context_summary": result[6],
                "related_concepts": json.loads(result[7]) if result[7] else [],
            }
        return None

    def get_related_concepts(self, concept: str, limit: int = 10) -> List[Dict]:
        """Get concepts related to a given concept."""
        with _lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT concept_b, relationship_type, strength
                FROM relationships
                WHERE concept_a = ?
                UNION
                SELECT concept_a, relationship_type, strength
                FROM relationships
                WHERE concept_b = ?
                ORDER BY strength DESC
                LIMIT ?
            """,
                (concept, concept, limit),
            )

            results = cursor.fetchall()
            conn.close()

        return [
            {"concept": row[0], "relationship_type": row[1], "strength": row[2]} for row in results
        ]

    def search_facts(self, query: str, limit: int = 10) -> List[Dict]:
        """Search facts by keyword."""
        with _lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT * FROM facts
                WHERE fact LIKE ?
                ORDER BY last_seen DESC
                LIMIT ?
            """,
                (f"%{query}%", limit),
            )

            results = cursor.fetchall()
            conn.close()

        return [
            {
                "id": row[0],
                "fact": row[1],
                "source_conversation_id": row[2],
                "confidence": row[3],
                "last_seen": row[4],
            }
            for row in results
        ]

    def get_memory_summary(self) -> Dict[str, Any]:
        """Get a summary of the dream memory state."""
        with _lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM concepts")
            total_concepts = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM relationships")
            total_relationships = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM facts")
            total_facts = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM dream_sessions")
            total_sessions = cursor.fetchone()[0]

            cursor.execute("""
                SELECT category, COUNT(*) 
                FROM concepts 
                GROUP BY category
            """)
            categories = dict(cursor.fetchall())

            conn.close()

        return {
            "total_concepts": total_concepts,
            "total_relationships": total_relationships,
            "total_facts": total_facts,
            "total_dream_sessions": total_sessions,
            "concepts_by_category": categories,
        }


# Global instance management
_dream_memory: Optional[DreamMemory] = None
_dream_lock = threading.Lock()


def get_dream_memory() -> DreamMemory:
    """Get the global dream memory instance."""
    global _dream_memory
    if _dream_memory is None:
        with _dream_lock:
            if _dream_memory is None:
                _dream_memory = DreamMemory()
    return _dream_memory


__all__ = ["DreamMemory", "get_dream_memory"]
