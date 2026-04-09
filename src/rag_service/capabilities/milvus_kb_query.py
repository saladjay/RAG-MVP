"""
Milvus Internal Knowledge Base Query Capability.

This module provides a capability interface for querying the internal Milvus KB,
supporting hybrid search (vector + BM25/keyword) as an alternative to the external HTTP KB.
"""

import time
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from rag_service.clients.milvus_kb_client import MilvusKBClient, get_milvus_kb_client
from rag_service.retrieval.embeddings import get_http_embedding_service
from rag_service.core.exceptions import RetrievalError
from rag_service.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MilvusKBQueryInput:
    """Input for Milvus KB query capability."""

    query: str
    """The user query to search for."""

    limit: int = 10
    """Maximum number of results to return."""

    search_type: str = "hybrid"
    """Search type: 'vector', 'keyword', or 'hybrid'."""

    filter_expression: str = ""
    """Optional filter expression for Milvus query."""

    trace_id: Optional[str] = None
    """Optional trace ID for logging/tracing."""


@dataclass
class MilvusKBDocChunk:
    """A document chunk from Milvus KB."""

    id: str
    """Document chunk ID."""

    content: str
    """Document chunk content."""

    document_name: Optional[str] = None
    """Source document name."""

    document_id: Optional[str] = None
    """Source document ID."""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """Additional metadata."""

    score: float = 0.0
    """Retrieval relevance score."""


@dataclass
class MilvusKBQueryOutput:
    """Output from Milvus KB query capability."""

    query: str
    """Original query."""

    chunks: List[MilvusKBDocChunk]
    """Retrieved document chunks."""

    search_type: str
    """Search type used."""

    retrieval_count: int
    """Number of chunks retrieved."""

    timing_ms: int = 0
    """Total time in milliseconds."""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """Additional metadata."""


class MilvusKBQuery:
    """
    Capability for querying the internal Milvus knowledge base.

    This capability provides hybrid search (vector + BM25/keyword) for
    document retrieval from Milvus as an alternative to the external HTTP KB.
    """

    def __init__(
        self,
        milvus_client: Optional[MilvusKBClient] = None,
        embedding_service: Optional[Any] = None,
    ):
        """Initialize the Milvus KB query capability.

        Args:
            milvus_client: Milvus KB client (uses global instance if None).
            embedding_service: Embedding service (uses HTTP embedding if None).
        """
        self._milvus_client = milvus_client
        self._embedding_service = embedding_service

    async def _get_milvus_client(self) -> MilvusKBClient:
        """Get or create Milvus KB client."""
        if self._milvus_client is None:
            self._milvus_client = await get_milvus_kb_client()
        return self._milvus_client

    async def _get_embedding_service(self):
        """Get or create embedding service."""
        if self._embedding_service is None:
            self._embedding_service = get_http_embedding_service()
        return self._embedding_service

    async def execute(self, input_data: MilvusKBQueryInput) -> MilvusKBQueryOutput:
        """Execute Milvus KB query.

        Args:
            input_data: Query input with query text and search parameters.

        Returns:
            Query output with retrieved document chunks.

        Raises:
            RetrievalError: If query fails.
        """
        start_time = time.time()
        trace_id = input_data.trace_id or "unknown"

        logger.info(
            "Milvus KB query started",
            extra={
                "trace_id": trace_id,
                "query": input_data.query[:100],
                "search_type": input_data.search_type,
                "limit": input_data.limit,
            },
        )

        try:
            # Get clients
            milvus_client = await self._get_milvus_client()
            embedding_service = await self._get_embedding_service()

            # Get query embedding (needed for vector and hybrid search)
            query_vector = []
            if input_data.search_type in ("vector", "hybrid"):
                query_vector = await embedding_service.embed_text(input_data.query)

            # Perform search
            raw_results = await milvus_client.search(
                query_vector=query_vector,
                query_text=input_data.query,
                limit=input_data.limit,
                search_type=input_data.search_type,
                filter_expression=input_data.filter_expression,
            )

            # Convert results to our format
            chunks = self._parse_results(raw_results)

            elapsed_ms = int((time.time() - start_time) * 1000)

            logger.info(
                "Milvus KB query completed",
                extra={
                    "trace_id": trace_id,
                    "retrieval_count": len(chunks),
                    "timing_ms": elapsed_ms,
                },
            )

            return MilvusKBQueryOutput(
                query=input_data.query,
                chunks=chunks,
                search_type=input_data.search_type,
                retrieval_count=len(chunks),
                timing_ms=elapsed_ms,
                metadata={
                    "trace_id": trace_id,
                    "milvus_collection": milvus_client._config.collection_name,
                },
            )

        except RetrievalError:
            raise
        except Exception as e:
            logger.error(
                "Milvus KB query failed",
                extra={"trace_id": trace_id, "error": str(e)},
            )
            raise RetrievalError(
                message="Milvus KB query failed",
                detail=str(e),
            ) from e

    def _parse_results(self, raw_results: List) -> List[MilvusKBDocChunk]:
        """Parse Milvus search results into doc chunks.

        Args:
            raw_results: Raw results from Milvus search.

        Returns:
            List of parsed document chunks.
        """
        chunks = []

        # Milvus search returns list of lists (one per query vector)
        # We flatten to get all results
        for result_list in raw_results:
            for result in result_list:
                entity = result.get("entity", {})
                distance = result.get("distance", 0.0)

                chunk = MilvusKBDocChunk(
                    id=str(entity.get("id", "")),
                    content=entity.get("content", ""),
                    document_name=entity.get("document_name"),
                    document_id=entity.get("document_id"),
                    metadata=entity.get("metadata", {}),
                    score=float(distance),
                )
                chunks.append(chunk)

        # Sort by score (lower distance = better for vector search)
        chunks.sort(key=lambda x: x.score)

        return chunks


# Global Milvus KB query instance
_milvus_kb_query: Optional[MilvusKBQuery] = None


async def get_milvus_kb_query() -> MilvusKBQuery:
    """Get the global Milvus KB query instance.

    Returns:
        MilvusKBQuery instance.

    Raises:
        ImportError: If pymilvus is not installed.
        RuntimeError: If Milvus KB is not configured.
    """
    global _milvus_kb_query

    if _milvus_kb_query is None:
        # Check if Milvus KB is configured
        from rag_service.config import get_settings

        settings = get_settings()

        if not settings.milvus_kb.enabled:
            raise RuntimeError(
                "Milvus KB not configured. "
                "Set MILVUS_KB_URI environment variable."
            )

        # Initialize clients (will be created on first use)
        milvus_client = await get_milvus_kb_client()
        embedding_service = get_http_embedding_service()

        _milvus_kb_query = MilvusKBQuery(
            milvus_client=milvus_client,
            embedding_service=embedding_service,
        )
        logger.info("Initialized global Milvus KB query capability")

    return _milvus_kb_query
