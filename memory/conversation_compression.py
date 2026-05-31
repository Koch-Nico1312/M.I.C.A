"""
Conversation Compression with SQLite + Gzip
=============================================
Implements Nova's storage pipeline for compressing conversations using Gzip
and storing them in SQLite database for 90%+ storage savings.
"""

import gzip
import json
import sqlite3
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()
DB_PATH = BASE_DIR / "data" / "conversations.db"
_lock = threading.Lock()


class ConversationCompression:
    """
    Handles compression and storage of conversations using SQLite + Gzip.
    Achieves 90%+ storage savings compared to plain text storage.
    """
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize the SQLite database with required tables."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with _lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Main conversations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    compressed_data BLOB NOT NULL,
                    original_size INTEGER,
                    compressed_size INTEGER,
                    message_count INTEGER,
                    user_profile TEXT,
                    tags TEXT
                )
            """)
            
            # Index for faster queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_id 
                ON conversations(session_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON conversations(timestamp DESC)
            """)
            
            # Dictionary for common word compression
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS compression_dict (
                    word TEXT PRIMARY KEY,
                    code TEXT NOT NULL,
                    frequency INTEGER DEFAULT 1
                )
            """)
            
            conn.commit()
            conn.close()
    
    def _compress_text(self, text: str) -> Tuple[bytes, int, int]:
        """
        Compress text using Gzip.
        
        Returns:
            (compressed_bytes, original_size, compressed_size)
        """
        original_size = len(text.encode('utf-8'))
        compressed_bytes = gzip.compress(text.encode('utf-8'))
        compressed_size = len(compressed_bytes)
        
        compression_ratio = (1 - compressed_size / original_size) * 100
        print(f"[Compression] 📦 {original_size} -> {compressed_size} bytes ({compression_ratio:.1f}% reduction)")
        
        return compressed_bytes, original_size, compressed_size
    
    def _decompress_text(self, compressed_bytes: bytes) -> str:
        """Decompress Gzip-compressed text."""
        return gzip.decompress(compressed_bytes).decode('utf-8')
    
    def _apply_dictionary_compression(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Apply dictionary-based compression for common words/phrases.
        Reduces repetitive text in conversations.
        """
        # Common words and their short codes
        compression_dict = {
            "assistant": "asst",
            "user": "usr",
            "message": "msg",
            "content": "cnt",
            "timestamp": "ts",
            "tool": "tl",
            "function": "fn",
            "parameters": "prm",
            "result": "res",
            "error": "err",
            "please": "pls",
            "thank you": "thx",
            "hello": "hi",
            "goodbye": "bye",
            "assistant:": "asst:",
            "user:": "usr:",
        }
        
        compressed_messages = []
        for msg in messages:
            compressed_msg = json.loads(json.dumps(msg))
            
            # Recursively apply compression
            def compress_dict(obj):
                if isinstance(obj, dict):
                    return {k: compress_dict(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [compress_dict(item) for item in obj]
                elif isinstance(obj, str):
                    text = obj
                    for word, code in compression_dict.items():
                        text = text.replace(word, code)
                    return text
                else:
                    return obj
            
            compressed_msg = compress_dict(compressed_msg)
            compressed_messages.append(compressed_msg)
        
        return compressed_messages
    
    def store_conversation(
        self,
        session_id: str,
        messages: List[Dict[str, Any]],
        user_profile: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> int:
        """
        Store a compressed conversation in the database.
        
        Returns:
            The ID of the stored conversation.
        """
        # Apply dictionary compression first
        compressed_messages = self._apply_dictionary_compression(messages)
        
        # Convert to JSON
        json_text = json.dumps(compressed_messages, ensure_ascii=False)
        
        # Apply Gzip compression
        compressed_data, original_size, compressed_size = self._compress_text(json_text)
        
        # Store in database
        with _lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO conversations 
                (session_id, compressed_data, original_size, compressed_size, 
                 message_count, user_profile, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                compressed_data,
                original_size,
                compressed_size,
                len(messages),
                user_profile,
                json.dumps(tags) if tags else None
            ))
            
            conversation_id = cursor.lastrowid
            conn.commit()
            conn.close()
        
        print(f"[Compression] 💾 Stored conversation {conversation_id} (session: {session_id})")
        return conversation_id
    
    def retrieve_conversation(self, conversation_id: int) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieve and decompress a conversation by ID.
        
        Returns:
            The list of messages, or None if not found.
        """
        with _lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT compressed_data FROM conversations 
                WHERE id = ?
            """, (conversation_id,))
            
            result = cursor.fetchone()
            conn.close()
        
        if not result:
            return None
        
        compressed_data = result[0]
        json_text = self._decompress_text(compressed_data)
        messages = json.loads(json_text)
        
        print(f"[Compression] 📂 Retrieved conversation {conversation_id}")
        return messages
    
    def retrieve_by_session(self, session_id: str, limit: int = 10) -> List[List[Dict[str, Any]]]:
        """
        Retrieve all conversations for a specific session.
        
        Returns:
            List of conversation message lists.
        """
        with _lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, compressed_data FROM conversations 
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (session_id, limit))
            
            results = cursor.fetchall()
            conn.close()
        
        conversations = []
        for conv_id, compressed_data in results:
            json_text = self._decompress_text(compressed_data)
            messages = json.loads(json_text)
            conversations.append(messages)
        
        print(f"[Compression] 📂 Retrieved {len(conversations)} conversations for session {session_id}")
        return conversations
    
    def get_recent_conversations(
        self,
        limit: int = 20,
        user_profile: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get recent conversations with metadata.
        
        Returns:
            List of conversation metadata (not full content).
        """
        with _lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if user_profile:
                cursor.execute("""
                    SELECT id, session_id, timestamp, message_count, 
                           original_size, compressed_size, tags
                    FROM conversations 
                    WHERE user_profile = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (user_profile, limit))
            else:
                cursor.execute("""
                    SELECT id, session_id, timestamp, message_count, 
                           original_size, compressed_size, tags
                    FROM conversations 
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,))
            
            results = cursor.fetchall()
            conn.close()
        
        conversations = []
        for row in results:
            conversations.append({
                "id": row[0],
                "session_id": row[1],
                "timestamp": row[2],
                "message_count": row[3],
                "original_size": row[4],
                "compressed_size": row[5],
                "compression_ratio": (1 - row[5] / row[4]) * 100 if row[4] > 0 else 0,
                "tags": json.loads(row[6]) if row[6] else []
            })
        
        return conversations
    
    def search_conversations(
        self,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search conversations by decompressing and matching text.
        Note: This is slower than semantic search but provides exact matches.
        
        Returns:
            List of matching conversations with snippets.
        """
        with _lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, session_id, timestamp, compressed_data
                FROM conversations
                ORDER BY timestamp DESC
                LIMIT 100
            """)
            
            results = cursor.fetchall()
            conn.close()
        
        matches = []
        query_lower = query.lower()
        
        for conv_id, session_id, timestamp, compressed_data in results:
            try:
                json_text = self._decompress_text(compressed_data)
                if query_lower in json_text.lower():
                    matches.append({
                        "id": conv_id,
                        "session_id": session_id,
                        "timestamp": timestamp,
                        "snippet": json_text[:500] + "..." if len(json_text) > 500 else json_text
                    })
                    
                    if len(matches) >= limit:
                        break
            except Exception as e:
                print(f"[Compression] ⚠️ Search error on conv {conv_id}: {e}")
                continue
        
        print(f"[Compression] 🔍 Found {len(matches)} matches for '{query}'")
        return matches
    
    def delete_conversation(self, conversation_id: int) -> bool:
        """Delete a conversation by ID."""
        with _lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                DELETE FROM conversations WHERE id = ?
            """, (conversation_id,))
            
            affected = cursor.rowcount
            conn.commit()
            conn.close()
        
        if affected > 0:
            print(f"[Compression] 🗑️ Deleted conversation {conversation_id}")
            return True
        return False
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        with _lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM conversations")
            total_conversations = cursor.fetchone()[0]
            
            cursor.execute("SELECT SUM(original_size), SUM(compressed_size) FROM conversations")
            sizes = cursor.fetchone()
            
            cursor.execute("SELECT AVG(message_count) FROM conversations")
            avg_messages = cursor.fetchone()[0] or 0
            
            conn.close()
        
        total_original = sizes[0] or 0
        total_compressed = sizes[1] or 0
        compression_ratio = (1 - total_compressed / total_original) * 100 if total_original > 0 else 0
        
        return {
            "total_conversations": total_conversations,
            "total_original_size": total_original,
            "total_compressed_size": total_compressed,
            "space_saved": total_original - total_compressed,
            "compression_ratio": compression_ratio,
            "avg_messages_per_conversation": round(avg_messages, 1)
        }
    
    def cleanup_old_conversations(self, days: int = 30) -> int:
        """
        Delete conversations older than specified days.
        
        Returns:
            Number of conversations deleted.
        """
        with _lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                DELETE FROM conversations 
                WHERE timestamp < datetime('now', '-' || ? || ' days')
            """, (days,))
            
            deleted = cursor.rowcount
            conn.commit()
            conn.close()
        
        print(f"[Compression] 🧹 Cleaned up {deleted} conversations older than {days} days")
        return deleted


# Global instance management
_compressor: Optional[ConversationCompression] = None
_compressor_lock = threading.Lock()


def get_compressor() -> ConversationCompression:
    """Get the global conversation compressor instance."""
    global _compressor
    if _compressor is None:
        with _compressor_lock:
            if _compressor is None:
                _compressor = ConversationCompression()
    return _compressor


__all__ = [
    "ConversationCompression",
    "get_compressor"
]
