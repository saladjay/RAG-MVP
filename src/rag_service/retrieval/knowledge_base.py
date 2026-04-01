"""
Knowledge Base Client for RAG Service.

This module provides Milvus integration for vector similarity search.
It handles:
- Connection management to Milvus vector database
- Vector search for relevant document chunks
- Result formatting with scores and metadata
- Connection pooling for performance

API Reference:
- Location: src/rag_service/retrieval/knowledge_base.py
- Class: KnowledgeBase
- Method: search() -> Vector similarity search
- Method: add_document() -> Add document to knowledge base
- Method: delete_document() -> Remove document from knowledge base
"""

import asyncio
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import threading

from rag_service.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SearchResult:
    """Result from knowledge base search.

    Attributes:
        chunk_id: Unique chunk identifier
        content: Chunk text content
        score: Similarity score (0-1, higher is better)
        source_doc: Source document identifier
        metadata: Additional chunk metadata
    """
    chunk_id: str
    content: str
    score: float
    source_doc: str
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "chunk_id": self.chunk_id,
            "content": self.content,
            "score": self.score,
            "source_doc": self.source_doc,
            "metadata": self.metadata,
        }


@dataclass
class DocumentChunk:
    """A chunk of a document to be stored in the knowledge base.

    Attributes:
        chunk_id: Unique chunk identifier
        doc_id: Source document identifier
        text: Chunk text content
        embedding: Vector embedding of the text
        metadata: Additional chunk metadata
        chunk_index: Position of chunk in document
    """
    chunk_id: str
    doc_id: str
    text: str
    embedding: List[float]
    metadata: Dict[str, Any]
    chunk_index: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "text": self.text,
            "embedding": self.embedding,
            "metadata": self.metadata,
            "chunk_index": self.chunk_index,
        }


class KnowledgeBase:
    """
    Client for Milvus vector database knowledge base.

    This client handles vector similarity search for retrieving relevant
    document chunks based on semantic similarity to a query.

    Attributes:
        host: Milvus server host
        port: Milvus server port
        collection_name: Name of the Milvus collection
        embedding_dim: Dimension of embedding vectors
        connection_pool: Thread-local connection storage
    """

    # Default collection schema
    DEFAULT_COLLECTION = "documents"
    EMBEDDING_DIM = 1536  # text-embedding-3-small dimension

    # Connection pool (thread-local)
    _connections = threading.local()

    def __init__(
        self,
        host: str = "localhost",
        port: int = 19530,
        collection_name: str = DEFAULT_COLLECTION,
        embedding_dim: int = EMBEDDING_DIM,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ):
        """Initialize the knowledge base client.

        Args:
            host: Milvus server host
            port: Milvus server port
            collection_name: Name of the Milvus collection
            embedding_dim: Dimension of embedding vectors
            user: Optional Milvus user
            password: Optional Milvus password
        """
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.embedding_dim = embedding_dim
        self.user = user
        self.password = password

        # Lazy initialization - connect on first use
        self._collection = None
        self._connected = False

        logger.info(
            "Initialized knowledge base client",
            extra={
                "host": host,
                "port": port,
                "collection": collection_name,
                "embedding_dim": embedding_dim,
            },
        )

    def _get_connection(self):
        """Get or create Milvus connection for current thread.

        Returns:
            Milvus connection object
        """
        if not hasattr(self._connections, "conn"):
            self._connect()
        return self._connections.conn

    def _connect(self) -> None:
        """Establish connection to Milvus server."""
        try:
            from pymilvus import connections

            connect_kwargs = {
                "alias": "default",
                "host": self.host,
                "port": self.port,
            }

            if self.user and self.password:
                connect_kwargs["user"] = self.user
                connect_kwargs["password"] = self.password

            connections.connect(**connect_kwargs)
            self._connections.conn = connections

            logger.info(
                "Connected to Milvus",
                extra={"host": self.host, "port": self.port},
            )

        except ImportError:
            logger.error("pymilvus package not installed")
            raise RuntimeError(
                "pymilvus is required. Install with: uv add pymilvus"
            )
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}")
            raise

    def _get_collection(self):
        """Get or create Milvus collection.

        Returns:
            Milvus Collection object
        """
        if self._collection is None:
            try:
                from pymilvus import Collection

                # Try to load existing collection
                if Collection.has_collection(self.collection_name):
                    self._collection = Collection(self.collection_name)
                    self._collection.load()
                    logger.debug(
                        "Loaded existing collection",
                        extra={"collection": self.collection_name},
                    )
                else:
                    # Collection doesn't exist - would need to be created
                    logger.warning(
                        "Collection does not exist",
                        extra={"collection": self.collection_name},
                    )
                    self._collection = None

            except Exception as e:
                logger.error(f"Failed to get collection: {e}")
                self._collection = None

        return self._collection

    def _embed_query(self, query: str) -> List[float]:
        """Generate embedding for query text.

        Args:
            query: Query text to embed

        Returns:
            Embedding vector
        """
        # Use embedding service
        try:
            # Import here to avoid circular dependency
            from rag_service.retrieval.embeddings import get_embedding_service

            # For sync code, we need to run async in new event loop or thread
            # For simplicity, create service instance directly
            from rag_service.retrieval.embeddings import EmbeddingService

            service = EmbeddingService()
            return service.embed_text(query)

        except Exception as e:
            logger.error(f"Failed to embed query: {e}")
            raise

    def search(
        self,
        query: str,
        top_k: int = 5,
        score_threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search knowledge base for relevant chunks.

        Performs vector similarity search to find chunks semantically
        similar to the query.

        Args:
            query: Query text
            top_k: Maximum number of results to return
            score_threshold: Optional minimum similarity score (0-1)

        Returns:
            List of search results with chunk_id, content, score, source_doc

        Raises:
            RuntimeError: If search fails
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        if top_k <= 0:
            raise ValueError("top_k must be positive")

        start_time = asyncio.get_event_loop().time()

        try:
            # Generate query embedding
            query_vector = self._embed_query(query)

            # Get collection
            collection = self._get_collection()
            if collection is None:
                logger.warning("No collection available, returning empty results")
                return []

            # Perform vector search
            search_params = {
                "metric_type": "COSINE",
                "params": {"nprobe": 10},
            }

            results = collection.search(
                data=[query_vector],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                output_fields=["text", "doc_id", "chunk_id", "metadata"],
            )

            # Format results
            formatted_results = []
            for hit in results[0]:
                # Convert distance to similarity score (COSINE distance → similarity)
                distance = hit.distance
                similarity = 1 - distance

                # Apply score threshold if provided
                if score_threshold is not None and similarity < score_threshold:
                    continue

                result = {
                    "chunk_id": hit.entity.get("chunk_id", hit.id),
                    "content": hit.entity.get("text", ""),
                    "score": similarity,
                    "source_doc": hit.entity.get("doc_id", ""),
                }

                # Add metadata if present
                if "metadata" in hit.entity:
                    result["metadata"] = hit.entity.get("metadata", {})

                formatted_results.append(result)

            latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000

            logger.info(
                "Knowledge base search completed",
                extra={
                    "query_length": len(query),
                    "results_count": len(formatted_results),
                    "latency_ms": latency_ms,
                },
            )

            return formatted_results

        except Exception as e:
            logger.error(
                "Knowledge base search failed",
                extra={"error": str(e), "query_length": len(query)},
            )
            raise RuntimeError(f"Search failed: {e}")

    async def asearch(
        self,
        query: str,
        top_k: int = 5,
        score_threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Async version of search.

        Args:
            query: Query text
            top_k: Maximum number of results
            score_threshold: Optional minimum similarity score

        Returns:
            List of search results
        """
        # Run blocking search in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.search,
            query,
            top_k,
            score_threshold,
        )

    def add_document(
        self,
        doc_id: str,
        chunks: List[DocumentChunk],
    ) -> None:
        """
        Add document chunks to knowledge base.

        Args:
            doc_id: Document identifier
            chunks: List of document chunks with embeddings

        Raises:
            RuntimeError: If insertion fails
        """
        if not chunks:
            raise ValueError("Cannot add empty chunk list")

        try:
            collection = self._get_collection()
            if collection is None:
                logger.error("No collection available for insertion")
                raise RuntimeError("Collection not available")

            # Prepare data for insertion
            data = [{
                "chunk_id": chunk.chunk_id,
                "doc_id": doc_id,
                "text": chunk.text,
                "embedding": chunk.embedding,
                "metadata": chunk.metadata,
                "chunk_index": chunk.chunk_index,
            } for chunk in chunks]

            # Insert into collection
            insert_result = collection.insert(data)

            logger.info(
                "Added document to knowledge base",
                extra={
                    "doc_id": doc_id,
                    "chunks_count": len(chunks),
                    "insert_count": insert_result.insert_count,
                },
            )

        except Exception as e:
            logger.error(
                "Failed to add document",
                extra={"error": str(e), "doc_id": doc_id},
            )
            raise RuntimeError(f"Failed to add document: {e}")

    def delete_document(self, doc_id: str) -> None:
        """
        Delete all chunks for a document from knowledge base.

        Args:
            doc_id: Document identifier

        Raises:
            RuntimeError: If deletion fails
        """
        try:
            collection = self._get_collection()
            if collection is None:
                logger.warning("No collection available for deletion")
                return

            # Delete by doc_id
            expr = f"doc_id == '{doc_id}'"
            result = collection.delete(expr)

            logger.info(
                "Deleted document from knowledge base",
                extra={"doc_id": doc_id, "delete_count": result.delete_count},
            )

        except Exception as e:
            logger.error(
                "Failed to delete document",
                extra={"error": str(e), "doc_id": doc_id},
            )
            raise RuntimeError(f"Failed to delete document: {e}")

    async def add_document_async(
        self,
        doc_id: str,
        content: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Add document to knowledge base with automatic chunking and embedding.

        This is a convenience method that handles chunking, embedding generation,
        and insertion. It wraps the lower-level add_document that takes pre-chunked data.

        Args:
            doc_id: Document identifier
            content: Document text content
            metadata: Document metadata

        Returns:
            Dictionary with operation results

        Raises:
            ValueError: If content is empty
            RuntimeError: If insertion fails
        """
        if not content or not content.strip():
            raise ValueError("Document content cannot be empty")

        try:
            # Import embedding service
            from rag_service.retrieval.embeddings import EmbeddingService

            # Chunk size and overlap
            chunk_size = 500  # characters
            chunk_overlap = 50  # characters

            # Split content into chunks
            chunks = self._chunk_text(content, chunk_size, chunk_overlap)

            # Generate embeddings for all chunks
            embedding_service = EmbeddingService()
            embeddings = embedding_service.embed_batch([c["text"] for c in chunks])

            # Create DocumentChunk objects
            from rag_service.retrieval.knowledge_base import DocumentChunk

            document_chunks = [
                DocumentChunk(
                    chunk_id=f"{doc_id}_chunk_{i}",
                    text=chunk["text"],
                    embedding=embeddings[i],
                    doc_id=doc_id,
                    metadata=metadata,
                    chunk_index=i,
                )
                for i, chunk in enumerate(chunks)
            ]

            # Use existing add_document method
            self.add_document(doc_id, document_chunks)

            logger.info(
                "Document indexed successfully",
                extra={
                    "doc_id": doc_id,
                    "chunk_count": len(chunks),
                },
            )

            return {
                "doc_id": doc_id,
                "chunk_count": len(chunks),
                "indexed": True,
                "embedding_model": "text-embedding-3-small",
                "embedding_dimension": len(embeddings[0]) if embeddings else 0,
                "metadata": metadata,
            }

        except Exception as e:
            logger.error(
                "Failed to add document",
                extra={"error": str(e), "doc_id": doc_id},
            )
            raise RuntimeError(f"Failed to add document: {e}")

    async def update_document(
        self,
        doc_id: str,
        content: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Update document in knowledge base with re-indexing.

        Deletes old chunks and re-indexes with new content and metadata.

        Args:
            doc_id: Document identifier
            content: New document content
            metadata: New document metadata

        Returns:
            Dictionary with operation results
        """
        try:
            # Check if document exists
            existing = await self.get_document(doc_id)
            created = existing is None

            # Delete existing chunks (if any)
            old_chunks_removed = 0
            if existing:
                try:
                    KnowledgeBase.delete_document(self, doc_id)
                    old_chunks_removed = existing.get("chunk_count", 1)
                except Exception:
                    pass  # Document might not exist

            # Add new content
            result = await self.add_document_async(doc_id, content, metadata)

            logger.info(
                "Document updated successfully",
                extra={
                    "doc_id": doc_id,
                    "created": created,
                    "new_chunks_added": result["chunk_count"],
                },
            )

            return {
                "doc_id": doc_id,
                "updated": True,
                "re_indexed": True,
                "created": created,
                "old_chunks_removed": old_chunks_removed,
                "new_chunks_added": result["chunk_count"],
                "metadata": metadata,
            }

        except Exception as e:
            logger.error(
                "Failed to update document",
                extra={"error": str(e), "doc_id": doc_id},
            )
            raise RuntimeError(f"Failed to update document: {e}")

    async def delete_document_async(
        self,
        doc_id: str,
    ) -> Dict[str, Any]:
        """
        Delete document from knowledge base and return result.

        Args:
            doc_id: Document identifier

        Returns:
            Dictionary with operation results
        """
        try:
            # Get existing document to count chunks
            existing = await self.get_document(doc_id)
            chunk_count = existing.get("chunk_count", 0) if existing else 0

            # Delete using sync method
            KnowledgeBase.delete_document(self, doc_id)

            return {
                "doc_id": doc_id,
                "deleted": True,
                "chunks_removed": chunk_count,
            }

        except Exception as e:
            logger.error(
                "Failed to delete document",
                extra={"error": str(e), "doc_id": doc_id},
            )
            raise RuntimeError(f"Failed to delete document: {e}")

    async def get_document(
        self,
        doc_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get document by ID.

        Args:
            doc_id: Document identifier

        Returns:
            Document data or None if not found
        """
        try:
            collection = self._get_collection()
            if collection is None:
                return None

            # Query for document chunks
            expr = f"doc_id == '{doc_id}'"
            results = collection.query(expr=expr, output_fields=["text", "metadata", "doc_id", "chunk_index"])

            if not results or not results[0]:
                return None

            chunks = results[0]
            if not chunks:
                return None

            # Aggregate content from chunks
            content_parts = [chunk.get("text", "") for chunk in chunks]
            content_parts.sort(key=lambda x: chunks[0].get("chunk_index", 0))

            # Get metadata from first chunk
            metadata = chunks[0].get("metadata", {}) if chunks else {}

            return {
                "doc_id": doc_id,
                "content": " ".join(content_parts),
                "metadata": metadata,
                "chunk_count": len(chunks),
            }

        except Exception as e:
            logger.warning(
                "Failed to get document",
                extra={"error": str(e), "doc_id": doc_id},
            )
            return None

    def _chunk_text(
        self,
        text: str,
        chunk_size: int,
        overlap: int,
    ) -> List[Dict[str, Any]]:
        """
        Split text into overlapping chunks.

        Args:
            text: Input text
            chunk_size: Maximum chunk size in characters
            overlap: Overlap between chunks in characters

        Returns:
            List of chunks with text and metadata
        """
        chunks = []
        start = 0
        chunk_index = 0

        while start < len(text):
            end = start + chunk_size
            chunk_text = text[start:end]

            if chunk_text:
                chunks.append({
                    "text": chunk_text,
                    "start": start,
                    "end": end,
                    "chunk_index": chunk_index,
                })
                chunk_index += 1

            start = end - overlap if end < len(text) else end

        return chunks

    def close(self) -> None:
        """Close connection to Milvus."""
        try:
            from pymilvus import connections

            if connections.has_connection("default"):
                connections.disconnect("default")
                logger.info("Disconnected from Milvus")

        except Exception as e:
            logger.warning(f"Error disconnecting from Milvus: {e}")


# Global singleton instance
_knowledge_base: Optional[KnowledgeBase] = None
_kb_lock = asyncio.Lock()


async def get_knowledge_base() -> KnowledgeBase:
    """Get or create the global knowledge base singleton.

    Returns:
        The global KnowledgeBase instance
    """
    global _knowledge_base

    async with _kb_lock:
        if _knowledge_base is None:
            # Read configuration from environment
            import os

            host = os.getenv("MILVUS_HOST", "localhost")
            port = int(os.getenv("MILVUS_PORT", "19530"))
            collection = os.getenv("MILVUS_COLLECTION", "documents")

            _knowledge_base = KnowledgeBase(
                host=host,
                port=port,
                collection_name=collection,
            )
            logger.info("Initialized global knowledge base")

    return _knowledge_base


def reset_knowledge_base() -> None:
    """Reset the global knowledge base instance.

    This is primarily used for testing to ensure clean state between tests.
    """
    global _knowledge_base
    if _knowledge_base:
        _knowledge_base.close()
    _knowledge_base = None
    logger.debug("Reset global knowledge base")
