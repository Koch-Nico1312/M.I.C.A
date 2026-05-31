"""
Semantic File Search with RAG (Retrieval-Augmented Generation)
Uses ChromaDB for vector-based semantic search across documents
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

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


class SemanticSearch:
    """Semantic search using vector embeddings"""
    
    def __init__(self):
        self.config = get_config()
        self.enabled = self.config.get('rag.enabled', False)
        self.vector_db = self.config.get('rag.vector_db', 'chromadb')
        self.index_path = Path(self.config.get('rag.index_path', './data/vector_db'))
        self.chunk_size = self.config.get('rag.chunk_size', 500)
        self.chunk_overlap = self.config.get('rag.chunk_overlap', 50)
        self.embedding_model = self.config.get('rag.embedding_model', 'all-MiniLM-L6-v2')
        
        self.index_path.mkdir(parents=True, exist_ok=True)
        
        self.client = None
        self.collection = None
        self.embedder = None
        
        if self.enabled and CHROMADB_AVAILABLE:
            try:
                self.client = chromadb.PersistentClient(path=str(self.index_path))
                self.collection = self.client.get_or_create_collection(
                    name="documents",
                    metadata={"description": "Document embeddings for semantic search"}
                )
                print(f"[SemanticSearch] ✅ Initialized ChromaDB at {self.index_path}")
            except Exception as e:
                print(f"[SemanticSearch] ❌ ChromaDB error: {e}")
                self.enabled = False
        
        if self.enabled and SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.embedder = SentenceTransformer(self.embedding_model)
                print(f"[SemanticSearch] ✅ Loaded embedding model: {self.embedding_model}")
            except Exception as e:
                print(f"[SemanticSearch] ❌ Embedding model error: {e}")
                self.enabled = False
        
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
                'file_path': str(file_path),
                'file_name': file_path.name,
                'indexed_at': datetime.now().isoformat()
            }
            if metadata:
                base_metadata.update(metadata)
            
            metadatas = [base_metadata.copy() for _ in chunks]
            
            # Add to collection
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=chunks,
                metadatas=metadatas
            )
            
            print(f"[SemanticSearch] 📄 Indexed {file_path.name} ({len(chunks)} chunks)")
            return True
            
        except Exception as e:
            print(f"[SemanticSearch] ❌ Index error for {file_path.name}: {e}")
            return False
    
    def index_directory(self, directory: Path, extensions: List[str] = None):
        """Index all files in a directory"""
        if extensions is None:
            extensions = ['.txt', '.md', '.py', '.js', '.html', '.css', '.json', '.xml']
        
        if not directory.exists():
            print(f"[SemanticSearch] ⚠️ Directory not found: {directory}")
            return
        
        indexed_count = 0
        for file_path in directory.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in extensions:
                try:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
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
        
        try:
            # Generate query embedding
            query_embedding = self.embedder.encode([query]).tolist()
            
            # Search collection
            results = self.collection.query(
                query_embeddings=query_embedding,
                n_results=n_results
            )
            
            # Format results
            formatted_results = []
            for i in range(len(results['ids'][0])):
                formatted_results.append({
                    'id': results['ids'][0][i],
                    'document': results['documents'][0][i],
                    'metadata': results['metadatas'][0][i],
                    'distance': results['distances'][0][i] if 'distances' in results else None
                })
            
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
            context_parts.append(result['document'])
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
            results = self.collection.get(
                where={"file_path": file_id}
            )
            
            if results['ids']:
                self.collection.delete(ids=results['ids'])
                print(f"[SemanticSearch] 🗑️ Deleted {file_path.name} from index")
        except Exception as e:
            print(f"[SemanticSearch] ❌ Delete error: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics"""
        if not self.enabled:
            return {'enabled': False}
        
        try:
            count = self.collection.count()
            return {
                'enabled': True,
                'total_documents': count,
                'index_path': str(self.index_path),
                'embedding_model': self.embedding_model
            }
        except Exception as e:
            return {'enabled': True, 'error': str(e)}
    
    def clear_index(self):
        """Clear all documents from the index"""
        if not self.enabled:
            return
        
        try:
            self.client.delete_collection("documents")
            self.collection = self.client.get_or_create_collection(
                name="documents",
                metadata={"description": "Document embeddings for semantic search"}
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
