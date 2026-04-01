"""
External HTTP Knowledge Base Client.

This module provides an HTTP client for querying the external knowledge base service.
It handles request/response transformation and error handling.
"""

import asyncio
import json
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel, Field

from rag_service.core.exceptions import RetrievalError
from rag_service.core.logger import get_logger


# Module logger
logger = get_logger(__name__)


class ExternalKBRequest(BaseModel):
    """Request model for external knowledge base API."""

    query: str = Field(..., description="Keyword 1 - primary search query")
    comp_id: str = Field(..., alias="compId", description="Company unique code, e.g., N000131")
    file_type: str = Field(..., alias="fileType", description="File type: PublicDocReceive or PublicDocDispatch")
    doc_date: str = Field("", alias="docDate", description="Document date (optional)")
    keyword: str = Field("", description="Keyword 2 (optional)")
    topk: int = Field(10, description="Top K results, default 10")
    score_min: float = Field(0.0, alias="scoreMin", description="Score threshold (optional)")
    search_type: int = Field(..., alias="searchType", description="Search type: 0=vector, 1=fulltext, 2=hybrid")

    class Config:
        """Pydantic config."""
        populate_by_name = True


class ExternalKBMetadata(BaseModel):
    """Metadata from external knowledge base response."""

    score: float = Field(..., description="Match score")
    position: int = Field(..., description="Position in results")
    source: str = Field(..., alias="_source", description="Data source")
    dataset_id: str = Field(..., alias="dataset_id", description="Dataset ID")
    dataset_name: str = Field(..., alias="dataset_name", description="Dataset name")
    document_id: str = Field(..., alias="document_id", description="Document ID")
    document_name: str = Field(..., alias="document_name", description="Document name")
    data_source_type: str = Field(..., alias="data_source_type", description="Data source type")
    segment_id: str = Field(..., alias="segment_id", description="Segment ID")
    retriever_from: str = Field(..., alias="retriever_from", description="Retriever source")
    doc_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="doc_metadata", description="Document metadata")

    model_config = {"populate_by_name": True}


class ExternalKBChunk(BaseModel):
    """Single chunk from external knowledge base response."""

    metadata: ExternalKBMetadata = Field(..., description="Chunk metadata")
    title: str = Field(..., description="Document title")
    content: str = Field(..., description="Chunk content")


class ExternalKBResponse(BaseModel):
    """Response model for external knowledge base API."""

    result: List[ExternalKBChunk] = Field(default_factory=list, description="Query results")


class ExternalKBClientConfig(BaseModel):
    """Configuration for external knowledge base client."""

    base_url: str = Field(..., description="Base URL of the external KB service")
    endpoint: str = Field("/cloudoa-ai/ai/file-knowledge/queryKnowledge", description="API endpoint")
    timeout: int = Field(30, description="Request timeout in seconds")
    max_retries: int = Field(3, description="Maximum retry attempts")
    xtoken: str = Field("", description="X-Token header for authentication")


class ExternalKBClient:
    """
    HTTP client for external knowledge base service.

    This client provides async methods to query the external HTTP knowledge base
    and transform responses to the internal format used by the RAG service.
    """

    def __init__(self, config: ExternalKBClientConfig) -> None:
        """
        Initialize the external KB client.

        Args:
            config: Client configuration.
        """
        self._config = config
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """
        Get or create HTTP client.

        Returns:
            Async HTTP client instance.
        """
        if self._client is None or self._client.is_closed:
            # Don't use base_url to avoid path resolution issues
            self._client = httpx.AsyncClient(
                timeout=self._config.timeout,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def query(
        self,
        query: str,
        comp_id: str,
        file_type: str = "PublicDocDispatch",
        doc_date: str = "",
        keyword: str = "",
        topk: int = 10,
        score_min: float = 0.0,
        search_type: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Query the external knowledge base.

        Args:
            query: Primary search query.
            comp_id: Company unique code (e.g., N000131).
            file_type: File type (PublicDocReceive or PublicDocDispatch).
            doc_date: Optional document date filter.
            keyword: Optional secondary keyword.
            topk: Number of results to return.
            score_min: Minimum score threshold.
            search_type: Search type (0=vector, 1=fulltext, 2=hybrid).

        Returns:
            List of transformed chunks compatible with internal format.

        Raises:
            RetrievalError: If the query fails.
        """
        client = await self._get_client()

        # Build request
        request = ExternalKBRequest(
            query=query,
            compId=comp_id,
            fileType=file_type,
            docDate=doc_date,
            keyword=keyword,
            topk=topk,
            scoreMin=score_min,
            searchType=search_type,
        )

        logger.info(
            "Querying external KB",
            extra={
                "query": query,
                "comp_id": comp_id,
                "file_type": file_type,
                "topk": topk,
                "search_type": search_type,
            },
        )

        # Retry logic
        last_error = None
        for attempt in range(self._config.max_retries):
            try:
                # Build full URL to avoid path issues
                # Ensure endpoint starts with / and base_url doesn't end with /
                base = self._config.base_url.rstrip('/')
                path = self._config.endpoint if self._config.endpoint.startswith('/') else '/' + self._config.endpoint
                url = f"{base}{path}"

                # Debug logging
                logger.info(f"Making request to full URL: {url}")

                # Build headers
                headers = {"Content-Type": "application/json"}
                if self._config.xtoken:
                    headers["xtoken"] = self._config.xtoken

                # Serialize JSON with ensure_ascii=True to match requests library behavior
                # This is required because the external KB API expects Unicode escapes for Chinese characters
                body = json.dumps(request.model_dump(by_alias=True, exclude_none=True), ensure_ascii=True)

                response = await client.post(
                    url,
                    content=body.encode("utf-8"),
                    headers=headers,
                )

                response.raise_for_status()

                # Parse response
                data = response.json()
                logger.info(f"Raw response: code={data.get('code')}, msg={data.get('msg')}, result_count={len(data.get('result', []))}")

                # Check for error codes
                if data.get('code') != 200:
                    logger.warning(f"External KB returned error code {data.get('code')}: {data.get('msg')}")
                    # Return empty results instead of raising error
                    return []

                external_response = ExternalKBResponse(**data)

                # Transform to internal format
                chunks = self._transform_chunks(external_response.result)

                logger.info(
                    "External KB query successful",
                    extra={
                        "result_count": len(chunks),
                        "attempt": attempt + 1,
                    },
                )

                return chunks

            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning(
                    "External KB query failed",
                    extra={
                        "status_code": e.response.status_code,
                        "attempt": attempt + 1,
                        "error": str(e),
                    },
                )
                if e.response.status_code < 500 or attempt == self._config.max_retries - 1:
                    break

                # Retry for server errors
                await asyncio.sleep(1 * (attempt + 1))

            except httpx.RequestError as e:
                last_error = e
                logger.warning(
                    "External KB request failed",
                    extra={
                        "attempt": attempt + 1,
                        "error": str(e),
                    },
                )
                if attempt == self._config.max_retries - 1:
                    break

                await asyncio.sleep(1 * (attempt + 1))

            except Exception as e:
                last_error = e
                logger.error(
                    "External KB query unexpected error",
                    extra={"error": str(e)},
                    exc_info=True,
                )
                break

        raise RetrievalError(
            message="Failed to query external knowledge base",
            detail=str(last_error) if last_error else "Unknown error",
        )

    def _transform_chunks(self, external_chunks: List[ExternalKBChunk]) -> List[Dict[str, Any]]:
        """
        Transform external chunks to internal format.

        Args:
            external_chunks: List of chunks from external API.

        Returns:
            Transformed chunks in internal format.
        """
        chunks = []
        for ext_chunk in external_chunks:
            chunks.append({
                "id": ext_chunk.metadata.segment_id,
                "chunk_id": ext_chunk.metadata.segment_id,
                "content": ext_chunk.content,
                "metadata": {
                    "title": ext_chunk.title,
                    "document_name": ext_chunk.metadata.document_name,
                    "document_id": ext_chunk.metadata.document_id,
                    "dataset_id": ext_chunk.metadata.dataset_id,
                    "dataset_name": ext_chunk.metadata.dataset_name,
                    "score": ext_chunk.metadata.score,
                    "position": ext_chunk.metadata.position,
                    "doc_metadata": ext_chunk.metadata.doc_metadata or {},
                },
                "score": ext_chunk.metadata.score,
                "source_doc": ext_chunk.metadata.document_name,
            })
        return chunks

    async def health_check(self) -> bool:
        """
        Check if the external KB service is healthy.

        Returns:
            True if service is healthy, False otherwise.
        """
        try:
            client = await self._get_client()
            # Use a simple query to check connectivity
            response = await client.post(
                self._config.endpoint,
                json={
                    "query": "health_check",
                    "compId": "N000131",
                    "fileType": "PublicDocDispatch",
                    "searchType": 1,
                    "topk": 1,
                },
                headers={"Content-Type": "application/json"},
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning("External KB health check failed", extra={"error": str(e)})
            return False


# Global client instance
_external_kb_client: Optional[ExternalKBClient] = None


async def get_external_kb_client() -> ExternalKBClient:
    """
    Get the global external KB client instance.

    Returns:
        External KB client instance.
    """
    global _external_kb_client

    if _external_kb_client is None:
        from rag_service.config import get_settings

        settings = get_settings()

        # Check if external KB is configured
        if not hasattr(settings, "external_kb") or not settings.external_kb.base_url:
            raise RetrievalError(
                message="External knowledge base not configured",
                detail="Set EXTERNAL_KB_BASE_URL environment variable",
            )

        config = ExternalKBClientConfig(
            base_url=settings.external_kb.base_url,
            endpoint=getattr(settings.external_kb, "endpoint", "/cloudoa-ai/ai/file-knowledge/queryKnowledge"),
            xtoken=getattr(settings.external_kb, "token", ""),
            timeout=getattr(settings.external_kb, "timeout", 30),
            max_retries=getattr(settings.external_kb, "max_retries", 3),
        )
        _external_kb_client = ExternalKBClient(config)

    return _external_kb_client


async def close_external_kb_client() -> None:
    """Close the global external KB client."""
    global _external_kb_client

    if _external_kb_client is not None:
        await _external_kb_client.close()
        _external_kb_client = None
