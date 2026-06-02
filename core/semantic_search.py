"""
Semantic File Search with RAG (Retrieval-Augmented Generation)
Uses ChromaDB for vector-based semantic search across documents
"""

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import chromadb
    from chromadb.config import Settings

    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

try:
    from sentence_transformers import SentenceTransformer

    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False

from config.config_loader import get_config
from core.logger import get_logger
from core.metrics_collector import get_metrics_collector
from core.paths import resolve_relative_path
from core.performance_flags import get_performance_flags
from core.vector_cache import get_vector_cache

logger = get_logger(__name__)

# Singleton instance for embedding model
_embedding_model_singleton = None
_embedding_model_lock = threading.Lock()

# Precomputed query cache
_precomputed_queries: Dict[str, List[Dict[str, Any]]] = {}
_precomputed_queries_lock = threading.Lock()
_common_queries = [
    "what files are in the project",
    "how do I configure",
    "what are the main features",
    "show me the documentation",
    "help with setup",
]


class SemanticSearch:
    """Semantic search using vector embeddings"""

    def __init__(self):
        self.config = get_config()
        self.enabled = self.config.get("rag.enabled", False)
        self.vector_db = self.config.get("rag.vector_db", "chromadb")
        self.index_path = resolve_relative_path(
            self.config.get("rag.index_path", str(resolve_relative_path("data/vector_db")))
        )
        self.chunk_size = self.config.get("rag.chunk_size", 500)
        self.chunk_overlap = self.config.get("rag.chunk_overlap", 50)
        self.embedding_model = self.config.get("rag.embedding_model", "all-MiniLM-L6-v2")

        self.index_path.mkdir(parents=True, exist_ok=True)

        self.client = None
        self.collection = None
        self.embedder = None

        if self.enabled and CHROMADB_AVAILABLE:
            try:
                perf_flags = get_performance_flags()
                metrics = get_metrics_collector()

                if perf_flags.is_enabled("db_connection_pooling"):
                    # Use connection pooling for ChromaDB
                    # ChromaDB doesn't have built-in pooling, but we can reuse the client
                    metrics.start_operation("chromadb_pool_init")
                    self.client = chromadb.PersistentClient(path=str(self.index_path))
                    metrics.end_operation("chromadb_pool_init", {"pooling": "client_reuse"})
                    print(
                        f"[SemanticSearch] ✅ Initialized ChromaDB with connection pooling at {self.index_path}"
                    )
                else:
                    self.client = chromadb.PersistentClient(path=str(self.index_path))
                    print(f"[SemanticSearch] ✅ Initialized ChromaDB at {self.index_path}")

                self.collection = self.client.get_or_create_collection(
                    name="documents",
                    metadata={"description": "Document embeddings for semantic search"},
                )
            except Exception as e:
                print(f"[SemanticSearch] ❌ ChromaDB error: {e}")
                self.enabled = False

        if self.enabled and SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                # Check if preloading is enabled
                perf_flags = get_performance_flags()
                metrics = get_metrics_collector()

                if perf_flags.is_enabled("preload_embedding_model"):
                    # Use singleton pattern
                    with _embedding_model_lock:
                        if _embedding_model_singleton is None:
                            metrics.start_operation("preload_embedding_model")
                            _embedding_model_singleton = SentenceTransformer(self.embedding_model)
                            # Warmup call to initialize model
                            _embedding_model_singleton.encode(["warmup"])
                            metrics.end_operation(
                                "preload_embedding_model",
                                {"model": self.embedding_model, "preloaded": True},
                            )
                            logger.info(f"Embedding model preloaded: {self.embedding_model}")
                        self.embedder = _embedding_model_singleton
                        print(
                            f"[SemanticSearch] ✅ Using preloaded embedding model: {self.embedding_model}"
                        )
                else:
                    # Original lazy loading
                    self.embedder = SentenceTransformer(self.embedding_model)
                    print(f"[SemanticSearch] ✅ Loaded embedding model: {self.embedding_model}")
            except Exception as e:
                print(f"[SemanticSearch] ❌ Embedding model error: {e}")
                self.enabled = False

        # Precompute common queries if enabled
        if self.enabled and perf_flags.is_enabled("precompute_queries"):
            self._precompute_common_queries()

        if not CHROMADB_AVAILABLE or not SENTENCE_TRANSFORMERS_AVAILABLE:
            print("[SemanticSearch] ⚠️ Required libraries not available")

    def _chunk_text(self, text: str) -> List[str]:
        """Split text into chunks for embedding"""
        chunks = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - self.chunk_overlap

        return chunks

    def _precompute_common_queries(self):
        """Precompute common queries and cache the results."""
        metrics = get_metrics_collector()
        metrics.start_operation("precompute_queries")

        with _precomputed_queries_lock:
            for query in _common_queries:
                try:
                    results = self.search(query, n_results=5)
                    _precomputed_queries[query] = results
                    logger.debug(f"Precomputed query: {query}")
                except Exception as e:
                    logger.warning(f"Failed to precompute query '{query}': {e}")

        metrics.end_operation("precompute_queries", {"queries_precomputed": len(_common_queries)})
        print(f"[SemanticSearch] ✅ Precomputed {len(_common_queries)} common queries")

    def get_precomputed_query(self, query: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get precomputed query result if available.

        Args:
            query: Query string

        Returns:
            Cached results or None if not found
        """
        perf_flags = get_performance_flags()
        if not perf_flags.is_enabled("precompute_queries"):
            return None

        with _precomputed_queries_lock:
            # Check for exact match
            if query in _precomputed_queries:
                return _precomputed_queries[query]

            # Check for partial match (fuzzy matching)
            for cached_query, results in _precomputed_queries.items():
                if cached_query.lower() in query.lower() or query.lower() in cached_query.lower():
                    return results

        return None

    def index_file(self, file_path: Path, content: str, metadata: Dict[str, Any] = None):
        """Index a file for semantic search"""
        if not self.enabled or not self.embedder:
            return False

        try:
            # Chunk the content
            chunks = self._chunk_text(content)

            # Generate embeddings
            embeddings = self.embedder.encode(chunks).tolist()

            # Create IDs
            file_id = str(file_path)
            ids = [f"{file_id}_{i}" for i in range(len(chunks))]

            # Prepare metadata
            base_metadata = {
                "file_path": str(file_path),
                "file_name": file_path.name,
                "indexed_at": datetime.now().isoformat(),
            }
            if metadata:
                base_metadata.update(metadata)

            metadatas = [base_metadata.copy() for _ in chunks]

            # Add to collection
            self.collection.add(
                ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas
            )

            print(f"[SemanticSearch] 📄 Indexed {file_path.name} ({len(chunks)} chunks)")
            return True

        except Exception as e:
            print(f"[SemanticSearch] ❌ Index error for {file_path.name}: {e}")
            return False

    def index_directory(self, directory: Path, extensions: List[str] = None):
        """Index all files in a directory"""
        if extensions is None:
            extensions = [".txt", ".md", ".py", ".js", ".html", ".css", ".json", ".xml"]

        if not directory.exists():
            print(f"[SemanticSearch] ⚠️ Directory not found: {directory}")
            return

        indexed_count = 0
        for file_path in directory.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in extensions:
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    if len(content) > 100:  # Only index files with meaningful content
                        if self.index_file(file_path, content):
                            indexed_count += 1
                except Exception as e:
                    print(f"[SemanticSearch] ⚠️ Could not read {file_path.name}: {e}")

        print(f"[SemanticSearch] ✅ Indexed {indexed_count} files from {directory}")

    def search(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Search for semantically similar documents"""
        if not self.enabled or not self.embedder:
            return []

        perf_flags = get_performance_flags()
        metrics = get_metrics_collector()

        # Check precomputed cache first
        if perf_flags.is_enabled("precompute_queries"):
            cached_results = self.get_precomputed_query(query)
            if cached_results:
                metrics.start_operation("precomputed_query_hit")
                metrics.end_operation(
                    "precomputed_query_hit",
                    {"query_length": len(query), "results_count": len(cached_results)},
                )
                return cached_results[:n_results]

        # Check vector cache
        if perf_flags.is_enabled("vector_db_cache"):
            vector_cache = get_vector_cache()
            cached_results = vector_cache.get(query, top_k=n_results)
            if cached_results is not None:
                metrics.start_operation("vector_search_cached")
                metrics.end_operation(
                    "vector_search_cached",
                    {"query_length": len(query), "results_count": len(cached_results)},
                )
                return cached_results

        try:
            metrics.start_operation("vector_search")

            # Generate query embedding
            query_embedding = self.embedder.encode([query]).tolist()

            # Search collection
            results = self.collection.query(query_embeddings=query_embedding, n_results=n_results)

            # Format results
            formatted_results = []
            for i in range(len(results["ids"][0])):
                formatted_results.append(
                    {
                        "id": results["ids"][0][i],
                        "document": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "distance": results["distances"][0][i] if "distances" in results else None,
                    }
                )

            metrics.end_operation(
                "vector_search",
                {"query_length": len(query), "results_count": len(formatted_results)},
            )

            # Cache the results
            if perf_flags.is_enabled("vector_db_cache"):
                vector_cache = get_vector_cache()
                vector_cache.set(query, formatted_results, top_k=n_results)

            return formatted_results

        except Exception as e:
            print(f"[SemanticSearch] ❌ Search error: {e}")
            return []

    def ask(self, question: str, context_files: List[Path] = None, n_results: int = 3) -> str:
        """Ask a question with RAG - retrieve relevant context and answer"""
        # Search for relevant documents
        results = self.search(question, n_results=n_results)

        if not results:
            return "I couldn't find any relevant information in the indexed documents, sir."

        # Build context from results
        context_parts = []
        for result in results:
            context_parts.append(f"From {result['metadata'].get('file_name', 'unknown')}:")
            context_parts.append(result["document"])
            context_parts.append("---")

        context = "\n".join(context_parts)

        # Return context (the actual answering would be done by the LLM)
        return f"Found {len(results)} relevant documents:\n\n{context}"

    def delete_file(self, file_path: Path):
        """Remove a file from the index"""
        if not self.enabled:
            return

        try:
            file_id = str(file_path)
            # Get all IDs for this file
            results = self.collection.get(where={"file_path": file_id})

            if results["ids"]:
                self.collection.delete(ids=results["ids"])
                print(f"[SemanticSearch] 🗑️ Deleted {file_path.name} from index")
        except Exception as e:
            print(f"[SemanticSearch] ❌ Delete error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics"""
        if not self.enabled:
            return {"enabled": False}

        try:
            count = self.collection.count()
            return {
                "enabled": True,
                "total_documents": count,
                "index_path": str(self.index_path),
                "embedding_model": self.embedding_model,
            }
        except Exception as e:
            return {"enabled": True, "error": str(e)}

    def clear_index(self):
        """Clear all documents from the index"""
        if not self.enabled:
            return

        try:
            self.client.delete_collection("documents")
            self.collection = self.client.get_or_create_collection(
                name="documents",
                metadata={"description": "Document embeddings for semantic search"},
            )
            print("[SemanticSearch] 🗑️ Cleared index")
        except Exception as e:
            print(f"[SemanticSearch] ❌ Clear error: {e}")


# Global instance
_semantic_search: Optional[SemanticSearch] = None


def get_semantic_search() -> SemanticSearch:
    """Get the global semantic search instance"""
    global _semantic_search
    if _semantic_search is None:
        _semantic_search = SemanticSearch()
    return _semantic_search
