"""
Retrieval strategy protocols and implementations.

Defines the RetrievalStrategy Protocol and concrete implementations for
different knowledge base backends. Strategy selection is config-driven
via QueryConfig.retrieval_backend.

Implementations:
- MilvusRetrieval: Vector search via Milvus (local)
- ExternalKBRetrieval: HTTP API to external knowledge base service

API Reference:
- Location: src/rag_service/strategies/retrieval.py
"""

import time
from typing import Any, Optional, Protocol, runtime_checkable

from rag_service.core.exceptions import RetrievalError
from rag_service.core.logger import get_logger

logger = get_logger(__name__)


@runtime_checkable
class RetrievalStrategy(Protocol):
    """Protocol for retrieval backends.

    Implementations must provide an async retrieve method that accepts
    a query string and returns a list of chunk dictionaries.
    """

    async def retrieve(
        self,
        query: str,
        top_k: int,
        context: Optional[dict[str, Any]] = None,
        trace_id: str = "",
    ) -> list[dict[str, Any]]:
        """Retrieve relevant chunks from knowledge base.

        Args:
            query: The search query string.
            top_k: Maximum number of results to return.
            context: Optional retrieval context (company_id, file_type, etc.).
            trace_id: Trace ID for observability.

        Returns:
            List of chunk dictionaries with keys: id, content, score,
            source_doc, metadata.
        """
        ...


class MilvusRetrieval:
    """Retrieval strategy using Milvus vector database.

    Extracts logic from KnowledgeQueryCapability and MilvusKBQueryCapability.
    Uses the existing KnowledgeBase client for vector similarity search.
    """

    def __init__(self) -> None:
        """Initialize MilvusRetrieval."""
        self._knowledge_base = None
        self._milvus_kb_client = None

    async def _get_knowledge_base(self):
        """Get or create the knowledge base client."""
        if self._knowledge_base is None:
            from rag_service.retrieval.knowledge_base import get_knowledge_base
            self._knowledge_base = await get_knowledge_base()
        return self._knowledge_base

    async def _get_milvus_kb_client(self):
        """Get or create the Milvus KB client for hybrid search."""
        if self._milvus_kb_client is None:
            try:
                from rag_service.clients.milvus_kb_client import get_milvus_kb_client
                self._milvus_kb_client = await get_milvus_kb_client()
            except Exception:
                self._milvus_kb_client = None
        return self._milvus_kb_client

    async def retrieve(
        self,
        query: str,
        top_k: int,
        context: Optional[dict[str, Any]] = None,
        trace_id: str = "",
    ) -> list[dict[str, Any]]:
        """Retrieve chunks from Milvus vector database.

        Tries Milvus KB client (hybrid search) first, falls back to
        KnowledgeBase (vector search).

        Args:
            query: The search query string.
            top_k: Maximum number of results to return.
            context: Optional retrieval context (unused for Milvus).
            trace_id: Trace ID for observability.

        Returns:
            List of chunk dictionaries.

        Raises:
            RetrievalError: If retrieval fails.
        """
        start_time = time.time()

        try:
            # Try hybrid search via Milvus KB client
            milvus_client = await self._get_milvus_kb_client()
            if milvus_client is not None:
                results = await milvus_client.search(
                    query=query,
                    limit=top_k,
                )
                elapsed_ms = (time.time() - start_time) * 1000
                logger.info(
                    "Milvus retrieval (hybrid) completed",
                    extra={"trace_id": trace_id, "results": len(results), "ms": elapsed_ms},
                )
                return results

            # Fallback to basic KnowledgeBase vector search
            kb = await self._get_knowledge_base()
            search_results = await kb.asearch(query=query, top_k=top_k)

            chunks = []
            for result in search_results:
                chunks.append({
                    "id": result.get("chunk_id", ""),
                    "content": result.get("content", ""),
                    "score": result.get("score", 0.0),
                    "source_doc": result.get("metadata", {}).get("source_doc", ""),
                    "metadata": result.get("metadata", {}),
                })

            elapsed_ms = (time.time() - start_time) * 1000
            logger.info(
                "Milvus retrieval (vector) completed",
                extra={"trace_id": trace_id, "results": len(chunks), "ms": elapsed_ms},
            )
            return chunks

        except Exception as e:
            raise RetrievalError(
                message=f"Milvus retrieval failed: {query}",
                detail=str(e),
            ) from e


class ExternalKBRetrieval:
    """Retrieval strategy using external HTTP knowledge base.

    Extracts logic from ExternalKBQueryCapability. Uses the existing
    ExternalKBClient for HTTP-based knowledge retrieval.
    """

    def __init__(self) -> None:
        """Initialize ExternalKBRetrieval."""
        self._client = None

    async def _get_client(self):
        """Get or create the external KB client."""
        if self._client is None:
            from rag_service.clients.external_kb_client import get_external_kb_client
            self._client = await get_external_kb_client()
        return self._client

    async def retrieve(
        self,
        query: str,
        top_k: int,
        context: Optional[dict[str, Any]] = None,
        trace_id: str = "",
    ) -> list[dict[str, Any]]:
        """Retrieve chunks from external knowledge base via HTTP.

        Args:
            query: The search query string.
            top_k: Maximum number of results to return.
            context: Must contain 'company_id' for external KB queries.
            trace_id: Trace ID for observability.

        Returns:
            List of chunk dictionaries.

        Raises:
            RetrievalError: If retrieval fails or comp_id is missing.
        """
        start_time = time.time()
        ctx = context or {}

        comp_id = ctx.get("company_id", "")
        if not comp_id:
            raise RetrievalError(
                message="External KB retrieval requires company_id in context",
                detail="Set context.company_id when using external_kb retrieval backend",
            )

        try:
            client = await self._get_client()

            chunks = await client.query(
                query=query,
                comp_id=comp_id,
                file_type=ctx.get("file_type", "PublicDocDispatch"),
                doc_date=ctx.get("doc_date", ""),
                keyword=ctx.get("keyword", ""),
                topk=top_k,
                score_min=ctx.get("score_min", 0.0),
                search_type=ctx.get("search_type", 1),
            )

            elapsed_ms = (time.time() - start_time) * 1000
            logger.info(
                "External KB retrieval completed",
                extra={"trace_id": trace_id, "results": len(chunks), "ms": elapsed_ms},
            )
            return chunks

        except RetrievalError:
            raise
        except Exception as e:
            raise RetrievalError(
                message=f"External KB retrieval failed: {query}",
                detail=str(e),
            ) from e
