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

    def __init__(self, index_path: Optional[Path] = None):
        global _embedding_model_singleton

        self.config = get_config()
        self.enabled = self.config.get("rag.enabled", False)
        self.vector_db = self.config.get("rag.vector_db", "chromadb")
        self._explicit_index_path = index_path is not None
        self.index_path = index_path or resolve_relative_path(
            self.config.get("rag.index_path", str(resolve_relative_path("data/vector_db")))
        )
        self.chunk_size = self.config.get("rag.chunk_size", 500)
        self.chunk_overlap = self.config.get("rag.chunk_overlap", 50)
        self.embedding_model = self.config.get("rag.embedding_model", "all-MiniLM-L6-v2")
        self.indexed = False

        self.index_path.mkdir(parents=True, exist_ok=True)

        self.client = None
        self.collection = None
        self.embedder = None
        self._embedder_loading = False
        self._embedder_ready = threading.Event()
        perf_flags = get_performance_flags()
        metrics = get_metrics_collector()

        if self.enabled and CHROMADB_AVAILABLE:
            try:
                if perf_flags.is_enabled("db_connection_pooling"):
                    # Use connection pooling for ChromaDB
                    # ChromaDB doesn't have built-in pooling, but we can reuse the client
                    metrics.start_operation("chromadb_pool_init")
                    self.client = self._create_chroma_client()
                    metrics.end_operation("chromadb_pool_init", {"pooling": "client_reuse"})
                    print(
                        f"[SemanticSearch] ✅ Initialized ChromaDB with connection pooling at {self.index_path}"
                    )
                else:
                    self.client = self._create_chroma_client()
                    print(f"[SemanticSearch] ✅ Initialized ChromaDB at {self.index_path}")

                self.collection = self.client.get_or_create_collection(
                    name="documents",
                    metadata={"description": "Document embeddings for semantic search"},
                )
            except Exception as e:
                print(f"[SemanticSearch] ❌ ChromaDB error: {e}")
                self.enabled = False

        if self.enabled and SENTENCE_TRANSFORMERS_AVAILABLE:
            if perf_flags.is_enabled("preload_embedding_model"):
                self._start_embedding_warmup()
            else:
                self._ensure_embedder()

        # Precompute common queries if enabled
        if self.enabled and perf_flags.is_enabled("precompute_queries") and self._has_index_content():
            threading.Thread(
                target=self._precompute_common_queries,
                name="mica-semantic-precompute",
                daemon=True,
            ).start()

        if not CHROMADB_AVAILABLE or not SENTENCE_TRANSFORMERS_AVAILABLE:
            print("[SemanticSearch] ⚠️ Required libraries not available")

    def _load_embedding_model(self):
        global _embedding_model_singleton

        metrics = get_metrics_collector()
        with _embedding_model_lock:
            if _embedding_model_singleton is None:
                metrics.start_operation("preload_embedding_model")
                _embedding_model_singleton = SentenceTransformer(self.embedding_model)
                _embedding_model_singleton.encode(["warmup"])
                metrics.end_operation(
                    "preload_embedding_model",
                    {"model": self.embedding_model, "preloaded": True},
                )
                logger.info(f"Embedding model loaded: {self.embedding_model}")
            return _embedding_model_singleton

    def _start_embedding_warmup(self) -> None:
        if self._embedder_loading or self.embedder is not None:
            return
        self._embedder_loading = True

        def warmup() -> None:
            try:
                self.embedder = self._load_embedding_model()
                logger.info(f"Semantic search embedding model warmed: {self.embedding_model}")
            except Exception as e:
                print(f"[SemanticSearch] ❌ Embedding model error: {e}")
                self.enabled = False
            finally:
                self._embedder_loading = False
                self._embedder_ready.set()

        threading.Thread(target=warmup, name="mica-embedding-warmup", daemon=True).start()

    def _ensure_embedder(self):
        if self.embedder is not None:
            return self.embedder
        if not self.enabled or not SENTENCE_TRANSFORMERS_AVAILABLE:
            return None
        if self._embedder_loading:
            self._embedder_ready.wait(timeout=30)
            if self.embedder is not None:
                return self.embedder
        try:
            self.embedder = self._load_embedding_model()
            print(f"[SemanticSearch] ✅ Loaded embedding model: {self.embedding_model}")
        except Exception as e:
            print(f"[SemanticSearch] ❌ Embedding model error: {e}")
            self.enabled = False
        finally:
            self._embedder_ready.set()
        return self.embedder

    def _has_index_content(self) -> bool:
        try:
            return bool(self.collection and self.collection.count() > 0)
        except Exception:
            return False

    def _create_chroma_client(self):
        if self._explicit_index_path and hasattr(chromadb, "EphemeralClient"):
            return chromadb.EphemeralClient()
        return chromadb.PersistentClient(path=str(self.index_path))

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

    def chunk_text(self, text: str, chunk_size: int | None = None, overlap: int | None = None) -> List[str]:
        """Public chunking helper for tests and callers."""
        original_chunk_size = self.chunk_size
        original_overlap = self.chunk_overlap
        try:
            if chunk_size is not None:
                self.chunk_size = max(1, int(chunk_size))
            if overlap is not None:
                self.chunk_overlap = max(0, min(int(overlap), self.chunk_size - 1))
            return self._chunk_text(str(text or ""))
        finally:
            self.chunk_size = original_chunk_size
            self.chunk_overlap = original_overlap

    def get_embedding(self, text: str) -> List[float]:
        """Generate an embedding for a single text string."""
        encoder = self.embedder
        if encoder is None and hasattr(self.embedding_model, "encode"):
            encoder = self.embedding_model
        if encoder is None:
            encoder = self._ensure_embedder()
        if encoder is None:
            raise RuntimeError("Embedding model is not available")
        embedding = encoder.encode([str(text)])
        if hasattr(embedding, "tolist"):
            embedding = embedding.tolist()
        if embedding and isinstance(embedding[0], list):
            return list(embedding[0])
        return list(embedding)

    def _precompute_common_queries(self):
        """Precompute common queries and cache the results."""
        metrics = get_metrics_collector()
        metrics.start_operation("precompute_queries")

        computed_queries: Dict[str, List[Dict[str, Any]]] = {}
        for query in _common_queries:
            try:
                results = self.search(query, n_results=5)
                computed_queries[query] = results
                logger.debug(f"Precomputed query: {query}")
            except Exception as e:
                logger.warning(f"Failed to precompute query '{query}': {e}")

        with _precomputed_queries_lock:
            _precomputed_queries.update(computed_queries)

        metrics.end_operation(
            "precompute_queries", {"queries_precomputed": len(computed_queries)}
        )
        logger.info(f"Precomputed {len(computed_queries)} semantic search queries")

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

    def index_text(
        self,
        document_id: str,
        title: str,
        content: str,
        metadata: Dict[str, Any] = None,
    ):
        """Index arbitrary text for semantic search."""
        if not self.enabled or not self._ensure_embedder():
            return False

        try:
            # Chunk the content
            chunks = self._chunk_text(content)

            # Generate embeddings
            embeddings = self.embedder.encode(chunks).tolist()

            # Create IDs
            ids = [f"{document_id}_{i}" for i in range(len(chunks))]

            # Prepare metadata
            base_metadata = {
                "file_path": document_id,
                "file_name": title,
                "indexed_at": datetime.now().isoformat(),
            }
            if metadata:
                base_metadata.update(metadata)

            metadatas = [base_metadata.copy() for _ in chunks]

            # Add to collection
            self.collection.add(
                ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas
            )

            self.indexed = True
            print(f"[SemanticSearch] 📄 Indexed {title} ({len(chunks)} chunks)")
            return True

        except Exception as e:
            print(f"[SemanticSearch] ❌ Index error for {title}: {e}")
            return False

    def index_file(self, file_path: Path, content: str, metadata: Dict[str, Any] = None):
        """Index a file for semantic search"""
        return self.index_text(str(file_path), file_path.name, content, metadata=metadata)

    def index_directory(self, directory: Path, extensions: List[str] = None):
        """Index all files in a directory"""
        if extensions is None:
            extensions = [".txt", ".md", ".py", ".js", ".html", ".css", ".json", ".xml"]

        if not directory.exists():
            print(f"[SemanticSearch] ⚠️ Directory not found: {directory}")
            raise FileNotFoundError(directory)

        indexed_count = 0
        for file_path in directory.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in extensions:
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    if content.strip() and self.index_file(file_path, content):
                        indexed_count += 1
                except Exception as e:
                    print(f"[SemanticSearch] ⚠️ Could not read {file_path.name}: {e}")

        if indexed_count:
            self.indexed = True
        print(f"[SemanticSearch] ✅ Indexed {indexed_count} files from {directory}")

    def search(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Search for semantically similar documents"""
        if not self.enabled or not self._ensure_embedder():
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
