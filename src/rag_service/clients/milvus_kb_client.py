"""
Milvus Internal Knowledge Base Client.

This module provides a client for Milvus-based internal knowledge base,
supporting hybrid search (vector + BM25/keyword).
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

try:
    from pymilvus import MilvusClient
    from pymilvus import utility
    MILVUS_AVAILABLE = True
except ImportError:
    MILVUS_AVAILABLE = False

# Try to import hybrid search components (available in newer pymilvus versions)
try:
    from pymilvus import AnnSearchRequest
    ANN_SEARCH_AVAILABLE = True
except ImportError:
    AnnSearchRequest = None
    ANN_SEARCH_AVAILABLE = False

try:
    from pymilvus import SPARSESearchRequest
    SPARSE_SEARCH_AVAILABLE = True
except ImportError:
    SPARSESearchRequest = None
    SPARSE_SEARCH_AVAILABLE = False

try:
    from pymilvus import RRFRanker
    RRF_RANKER_AVAILABLE = True
except ImportError:
    RRFRanker = None
    RRF_RANKER_AVAILABLE = False

from rag_service.core.exceptions import RetrievalError
from rag_service.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MilvusKBConfig:
    """Configuration for Milvus knowledge base."""

    milvus_uri: str
    collection_name: str = "knowledge_base"
    timeout: int = 30
    embedding_dimension: int = 1024  # bge-m3 dimension


class MilvusKBClient:
    """
    Client for Milvus internal knowledge base.

    Supports hybrid search (vector + BM25/keyword) for document retrieval.
    """

    def __init__(self, config: MilvusKBConfig):
        """Initialize the Milvus KB client.

        Args:
            config: Milvus configuration.
        """
        self._config = config
        self._client: Optional[MilvusClient] = None

        # Check if pymilvus is available
        if not MILVUS_AVAILABLE:
            logger.warning(
                "pymilvus package not available. "
                "Install with: uv add pymilvus"
            )
            self._available = False
        else:
            self._available = True

    async def _get_client(self) -> MilvusClient:
        """Get or create Milvus client.

        Returns:
            MilvusClient instance.
        """
        if self._client is None:
            # Run blocking connect in thread pool
            loop = asyncio.get_event_loop()
            self._client = await loop.run_in_executor(
                None,
                self._connect_milvus
            )
        return self._client

    def _connect_milvus(self) -> MilvusClient:
        """Connect to Milvus (blocking).

        Returns:
            Connected MilvusClient instance.

        Raises:
            ImportError: If pymilvus is not installed.
        """
        if not self._available:
            raise ImportError(
                "pymilvus package is required. Install with: uv add pymilvus"
            )

        client = MilvusClient(uri=self._config.milvus_uri)

        # Test connection
        logger.info(
            "Connecting to Milvus",
            extra={
                "uri": self._config.milvus_uri,
                "collection": self._config.collection_name,
            },
        )

        collections = client.list_collections()
        # collections can be list of strings or list of dicts
        collection_names = []
        if collections:
            for c in collections:
                if isinstance(c, str):
                    collection_names.append(c)
                elif isinstance(c, dict):
                    collection_names.append(c.get("name", ""))
                else:
                    collection_names.append(str(c))

        logger.info(
            "Milvus connected",
            extra={
                "collections_count": len(collections),
                "collections": collection_names,
            },
        )

        return client

    async def close(self) -> None:
        """Close the Milvus client connection."""
        if self._client is not None:
            # pymilvus doesn't have async close, just clear reference
            self._client = None

    async def search(
        self,
        query_vector: List[float],
        query_text: str = "",
        limit: int = 10,
        search_type: str = "hybrid",  # "vector", "keyword", "hybrid"
        filter_expression: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant documents in Milvus.

        Args:
            query_vector: Query embedding vector for semantic search.
            query_text: Query text for keyword/BM25 search.
            limit: Maximum number of results to return.
            search_type: Search type - "vector", "keyword", or "hybrid".
            filter_expression: Optional filter expression.

        Returns:
            List of matching document chunks.

        Raises:
            RetrievalError: If search fails.
        """
        client = await self._get_client()

        try:
            if search_type == "vector":
                # Pure vector search
                results = await self._vector_search(
                    client, query_vector, limit, filter_expression
                )
            elif search_type == "keyword":
                # Keyword/BM25 search
                results = await self._keyword_search(
                    client, query_text, limit, filter_expression
                )
            else:
                # Hybrid search (vector + keyword)
                results = await self._hybrid_search(
                    client, query_vector, query_text, limit, filter_expression
                )

            logger.info(
                "Milvus search completed",
                extra={
                    "search_type": search_type,
                    "result_count": len(results),
                    "limit": limit,
                },
            )

            return results

        except Exception as e:
            logger.error(
                "Milvus search failed",
                extra={"error": str(e)},
            )
            raise RetrievalError(
                message="Milvus knowledge base search failed",
                detail=str(e),
            ) from e

    async def _vector_search(
        self,
        client: MilvusClient,
        query_vector: List[float],
        limit: int,
        filter_expression: str,
    ) -> List[Dict[str, Any]]:
        """Perform vector-only search.

        Args:
            client: Milvus client.
            query_vector: Query embedding.
            limit: Max results.
            filter_expression: Optional filter.

        Returns:
            List of results.
        """
        # Run blocking search in thread pool
        loop = asyncio.get_event_loop()
        # Build search kwargs
        search_kwargs = {
            "collection_name": self._config.collection_name,
            "data": [query_vector],
            "limit": limit,
            "output_fields": ["fileContent", "formTitle", "document_id", "chunk_index"],
        }
        # Only add filter if provided
        if filter_expression:
            search_kwargs["filter"] = filter_expression

        return await loop.run_in_executor(
            None,
            lambda: client.search(**search_kwargs)
        )

    async def _keyword_search(
        self,
        client: MilvusClient,
        query_text: str,
        limit: int,
        filter_expression: str,
    ) -> List[Dict[str, Any]]:
        """Perform keyword/BM25 search.

        Args:
            client: Milvus client.
            query_text: Query keywords.
            limit: Max results.
            filter_expression: Optional filter.

        Returns:
            List of results.
        """
        # Run blocking search in thread pool
        loop = asyncio.get_event_loop()
        # Build search kwargs
        search_kwargs = {
            "collection_name": self._config.collection_name,
            "data": [],  # Empty for keyword search
            "limit": limit,
            "output_fields": ["fileContent", "formTitle", "document_id", "chunk_index"],
        }
        # Add filter for keyword search
        if query_text:
            search_kwargs["filter"] = f"content like '%{query_text}%'"
        elif filter_expression:
            search_kwargs["filter"] = filter_expression

        return await loop.run_in_executor(
            None,
            lambda: client.search(**search_kwargs)
        )

    async def _hybrid_search(
        self,
        client: MilvusClient,
        query_vector: List[float],
        query_text: str,
        limit: int,
        filter_expression: str,
    ) -> List[Dict[str, Any]]:
        """Perform hybrid search (vector + BM25 keyword).

        Uses AnnSearchRequest for dense vector search and SPARSESearchRequest
        for BM25 sparse vector search, combined with RRFRanker.
        Falls back to vector search if hybrid components are not available.

        Args:
            client: Milvus client.
            query_vector: Query embedding.
            query_text: Query keywords.
            limit: Max results.
            filter_expression: Optional filter.

        Returns:
            List of results.
        """
        # Check if hybrid search components are available
        if not ANN_SEARCH_AVAILABLE or not SPARSE_SEARCH_AVAILABLE or not RRF_RANKER_AVAILABLE:
            logger.info(
                "Hybrid search not available (pymilvus version incompatible), "
                "falling back to vector search"
            )
            return await self._vector_search(client, query_vector, limit, filter_expression)

        try:
            # Get RRF k from config if available
            rrf_k = getattr(self._config, "rrf_k", 60)

            # Create dense vector search request (semantic)
            dense_req = AnnSearchRequest(
                data=[query_vector],
                anns_field="vector",
                param={"metric_type": "COSINE", "params": {"nprobe": 10}},
                limit=limit,
            )

            # Create sparse vector search request (BM25 keyword)
            # The sparse vector for the query text will be auto-generated
            # by Milvus using the same BM25 function
            sparse_req = SPARSESearchRequest(
                data=[query_text],  # Milvus will auto-generate sparse vector
                anns_field="sparse_vector",
                param={"metric_type": "BM25"},
                limit=limit,
            )

            # Create RRF ranker for combining results
            ranker = RRFRanker(k=rrf_k)

            # Run hybrid search
            loop = asyncio.get_event_loop()

            # Build search kwargs
            search_kwargs = {
                "collection_name": self._config.collection_name,
                "reqs": [dense_req, sparse_req],  # Both dense and sparse requests
                "ranker": ranker,
                "limit": limit,
                "output_fields": ["fileContent", "formTitle", "document_id", "chunk_index"],
            }

            # Add filter if provided
            if filter_expression:
                search_kwargs["expr"] = filter_expression

            results = await loop.run_in_executor(
                None,
                lambda: client.hybrid_search(**search_kwargs)
            )

            logger.info(
                "Hybrid search completed",
                extra={
                    "dense_vector": True,
                    "sparse_bm25": True,
                    "ranker": "RRF",
                    "rrf_k": rrf_k,
                    "result_count": len(results[0]) if results else 0,
                },
            )

            # Return first batch results (hybrid_search returns list of lists)
            return results[0] if results else []

        except Exception as e:
            logger.warning(
                f"Hybrid search failed, falling back to vector search: {e}"
            )
            return await self._vector_search(client, query_vector, limit, filter_expression)

    async def insert_documents(
        self,
        documents: List[Dict[str, Any]]
    ) -> int:
        """
        Insert documents into Milvus collection.

        Args:
            documents: List of documents with id, content, and optional metadata.

        Returns:
            Number of documents inserted.

        Raises:
            RetrievalError: If insertion fails.
        """
        client = await self._get_client()

        try:
            # Run blocking insert in thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: client.insert(
                    collection_name=self._config.collection_name,
                    data=documents
                )
            )

            logger.info(
                "Milvus insert completed",
                extra={"inserted_count": len(documents)},
            )

            return len(documents)

        except Exception as e:
            logger.error(
                "Milvus insert failed",
                extra={"error": str(e)},
            )
            raise RetrievalError(
                message="Failed to insert documents into Milvus",
                detail=str(e),
            ) from e

    async def health_check(self) -> bool:
        """
        Check if Milvus is accessible.

        Returns:
            True if healthy, False otherwise.
        """
        try:
            client = await self._get_client()
            # Try to list collections
            collections = client.list_collections()
            return True
        except Exception as e:
            logger.warning(
                "Milvus health check failed",
                extra={"error": str(e)},
            )
            return False


# Global Milvus KB client instance
_milvus_kb_client: Optional[MilvusKBClient] = None


async def get_milvus_kb_client() -> MilvusKBClient:
    """Get the global Milvus KB client instance.

    Returns:
        MilvusKBClient instance.

    Raises:
        ImportError: If pymilvus is not installed.
        RuntimeError: If Milvus is not configured.
    """
    global _milvus_kb_client

    if _milvus_kb_client is None:
        from rag_service.config import get_settings

        settings = get_settings()

        # Check if Milvus is configured
        if not hasattr(settings, "milvus_kb") or not settings.milvus_kb.milvus_uri:
            raise RuntimeError(
                "Milvus knowledge base not configured. "
                "Set MILVUS_KB_URI environment variable."
            )

        config = MilvusKBConfig(
            milvus_uri=settings.milvus_kb.milvus_uri,
            collection_name=getattr(settings.milvus_kb, "collection_name", "knowledge_base"),
            timeout=getattr(settings.milvus_kb, "timeout", 30),
            embedding_dimension=getattr(settings.milvus_kb, "embedding_dimension", 1024),
        )

        _milvus_kb_client = MilvusKBClient(config)
        logger.info("Initialized global Milvus KB client")

    return _milvus_kb_client
