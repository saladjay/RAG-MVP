"""
External HTTP Knowledge Base Client.

This module provides an HTTP client for querying the external knowledge base service.
It handles request/response transformation and error handling.
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel, Field

from rag_service.core.exceptions import RetrievalError
from rag_service.core.logger import get_logger


# Module logger
logger = get_logger(__name__)


# ============================================================================
# HTTP Request/Response Logger
# ============================================================================

class KBHttpLogger:
    """
    Logger for external KB HTTP requests and responses.

    Logs are saved to logs/external_kb_http.jsonl with full request/response details.
    """

    def __init__(self, log_dir: str = "logs"):
        """Initialize the HTTP logger.

        Args:
            log_dir: Directory to store log files.
        """
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = self._log_dir / "external_kb_http.jsonl"
        self._enabled = os.getenv("EXTERNAL_KB_HTTP_LOG", "true").lower() == "true"

    def log_request_response(
        self,
        request_url: str,
        request_headers: Dict[str, str],
        request_body: Dict[str, Any],
        response_status: int,
        response_headers: Dict[str, str],
        response_body: Dict[str, Any],
        latency_ms: float,
        error: Optional[str] = None,
    ) -> None:
        """Log a complete HTTP request/response pair.

        Args:
            request_url: The request URL.
            request_headers: Request headers (sensitive values masked).
            request_body: Request payload.
            response_status: HTTP status code.
            response_headers: Response headers.
            response_body: Response payload.
            latency_ms: Request latency in milliseconds.
            error: Error message if request failed.
        """
        if not self._enabled:
            return

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "request": {
                "url": request_url,
                "headers": self._mask_sensitive_headers(request_headers),
                "body": request_body,
            },
            "response": {
                "status": response_status,
                "headers": dict(response_headers) if response_headers else {},
                "body": response_body if not error else None,
            },
            "latency_ms": round(latency_ms, 2),
            "error": error,
        }

        try:
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning(f"Failed to write HTTP log: {e}")

    def _mask_sensitive_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Mask sensitive header values.

        Args:
            headers: Original headers.

        Returns:
            Headers with sensitive values masked.
        """
        masked = {}
        sensitive_keys = {"authorization", "xtoken", "x-api-key", "token"}

        for key, value in headers.items():
            if key.lower() in sensitive_keys:
                # Show first 8 and last 4 characters
                if len(value) > 12:
                    masked[key] = f"{value[:8]}...{value[-4:]}"
                else:
                    masked[key] = "***"
            else:
                masked[key] = value

        return masked


# Global HTTP logger instance
_kb_http_logger: Optional[KBHttpLogger] = None


def get_kb_http_logger() -> KBHttpLogger:
    """Get the global KB HTTP logger instance.

    Returns:
        KBHttpLogger instance.
    """
    global _kb_http_logger
    if _kb_http_logger is None:
        _kb_http_logger = KBHttpLogger()
    return _kb_http_logger


# ============================================================================
# External KB Models
# ============================================================================

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
    """Configuration for external knowledge base client.

    Supports flexible authentication through custom HTTP headers or simple auth token.
    """

    base_url: str = Field(..., description="Base URL of the external KB service")
    endpoint: str = Field("/cloudoa-ai/ai/file-knowledge/queryKnowledge", description="API endpoint")
    timeout: int = Field(30, description="Request timeout in seconds")
    max_retries: int = Field(3, description="Maximum retry attempts")

    # Flexible authentication options
    headers: Dict[str, str] = Field(
        default_factory=dict,
        description="Custom HTTP headers (e.g., {'Authorization': 'Bearer token', 'x-api-key': 'key'})"
    )
    auth_token: str = Field(
        "",
        description="Auth token for 'Authorization: Bearer <token>' header (shortcut for common pattern)"
    )

    # Deprecated: use 'headers' or 'auth_token' instead
    xtoken: str = Field(
        "",
        deprecated="Use 'headers'={'xtoken': 'xxx'} or 'auth_token' instead",
        description="X-Token header (deprecated, use 'headers' dict for flexibility)"
    )


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
        file_type: str = None,
        doc_date: str = "",
        keyword: str = "",
        topk: int = 10,
        score_min: float = 0.0,
        search_type: int = 2,
    ) -> List[Dict[str, Any]]:
        """
        Query the external knowledge base.

        Args:
            query: Primary search query.
            comp_id: Company unique code (e.g., N000131).
            file_type: File type (PublicDocReceive or PublicDocDispatch or None).
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
            start_time = asyncio.get_event_loop().time()
            request_body_dict = None
            response_body_dict = None

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

                # Add authentication headers
                # Priority: headers dict > auth_token > xtoken (deprecated)
                if self._config.headers:
                    headers.update(self._config.headers)
                elif self._config.auth_token:
                    headers["Authorization"] = f"Bearer {self._config.auth_token}"
                elif self._config.xtoken:
                    # Deprecated: xtoken for backward compatibility
                    headers["xtoken"] = self._config.xtoken

                # Log authentication (without exposing sensitive values)
                auth_keys = [k for k in headers.keys() if k.lower() in ("authorization", "xtoken", "x-api-key")]
                if auth_keys:
                    logger.debug(f"Using auth headers: {auth_keys}")
                else:
                    logger.debug("No authentication headers configured")

                # Serialize JSON with ensure_ascii=True to match requests library behavior
                # This is required because the external KB API expects Unicode escapes for Chinese characters
                body_str = json.dumps(request.model_dump(by_alias=True, exclude_none=True), ensure_ascii=True)
                request_body_dict = request.model_dump(by_alias=True, exclude_none=True)

                response = await client.post(
                    url,
                    content=body_str.encode("utf-8"),
                    headers=headers,
                )

                response.raise_for_status()

                # Parse response
                data = response.json()
                response_body_dict = data
                logger.info(f"Raw response: code={data.get('code')}, msg={data.get('msg')}, result_count={len(data.get('result', []))}")

                # Calculate latency
                latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000

                # Log HTTP request/response
                get_kb_http_logger().log_request_response(
                    request_url=url,
                    request_headers=headers,
                    request_body=request_body_dict,
                    response_status=response.status_code,
                    response_headers=dict(response.headers),
                    response_body=response_body_dict,
                    latency_ms=latency_ms,
                )

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
                latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000

                # Log failed request
                get_kb_http_logger().log_request_response(
                    request_url=url if 'url' in locals() else "unknown",
                    request_headers=headers if 'headers' in locals() else {},
                    request_body=request_body_dict if request_body_dict else {},
                    response_status=e.response.status_code,
                    response_headers=dict(e.response.headers),
                    response_body={},
                    latency_ms=latency_ms,
                    error=str(e),
                )

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
                latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000

                # Log failed request
                get_kb_http_logger().log_request_response(
                    request_url=url if 'url' in locals() else "unknown",
                    request_headers=headers if 'headers' in locals() else {},
                    request_body=request_body_dict if request_body_dict else {},
                    response_status=0,
                    response_headers={},
                    response_body={},
                    latency_ms=latency_ms,
                    error=str(e),
                )

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
                latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000

                # Log failed request
                get_kb_http_logger().log_request_response(
                    request_url=url if 'url' in locals() else "unknown",
                    request_headers=headers if 'headers' in locals() else {},
                    request_body=request_body_dict if request_body_dict else {},
                    response_status=0,
                    response_headers={},
                    response_body={},
                    latency_ms=latency_ms,
                    error=str(e),
                )

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

        # Build config with new authentication pattern
        config_kwargs = {
            "base_url": settings.external_kb.base_url,
            "endpoint": getattr(settings.external_kb, "endpoint", "/cloudoa-ai/ai/file-knowledge/queryKnowledge"),
            "timeout": getattr(settings.external_kb, "timeout", 30),
            "max_retries": getattr(settings.external_kb, "max_retries", 3),
        }

        # Use new authentication pattern with priority
        # Priority: headers dict > auth_token > token (deprecated)
        if hasattr(settings.external_kb, "headers") and settings.external_kb.headers:
            config_kwargs["headers"] = settings.external_kb.headers
        elif hasattr(settings.external_kb, "auth_token") and settings.external_kb.auth_token:
            config_kwargs["auth_token"] = settings.external_kb.auth_token
        elif hasattr(settings.external_kb, "token") and settings.external_kb.token:
            # Deprecated: use headers or auth_token instead
            config_kwargs["xtoken"] = settings.external_kb.token

        config = ExternalKBClientConfig(**config_kwargs)
        _external_kb_client = ExternalKBClient(config)

    return _external_kb_client


async def close_external_kb_client() -> None:
    """Close the global external KB client."""
    global _external_kb_client

    if _external_kb_client is not None:
        await _external_kb_client.close()
        _external_kb_client = None
