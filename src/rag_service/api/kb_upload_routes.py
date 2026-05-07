"""
Knowledge Base Upload API routes for RAG Service.

This module provides HTTP endpoints for document upload, collection management,
and health checks for the Milvus-based knowledge base with hybrid search support.
"""

import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, field_validator

from rag_service.capabilities.milvus_kb_upload import (
    MilvusKBUploadCapability,
    MilvusKBUploadInput,
    MilvusKBUploadOutput,
)
from rag_service.clients.milvus_kb_client import get_milvus_kb_client, MilvusKBClient
from rag_service.config import get_settings
from rag_service.core.exceptions import RetrievalError, EmbeddingError
from rag_service.core.logger import get_logger


logger = get_logger(__name__)

# Deprecation dependency — adds header to all legacy KB route responses
async def _deprecation_header(response: Response):
    response.headers["Deprecation"] = "true; version=0.2.0"


# Create router
router = APIRouter(
    prefix="/kb",
    tags=["Knowledge Base (deprecated)"],
    dependencies=[Depends(_deprecation_header)],
)

# Global capability instance (will be initialized on startup)
_upload_capability: Optional[MilvusKBUploadCapability] = None


def get_upload_capability() -> MilvusKBUploadCapability:
    """Get or initialize the upload capability."""
    global _upload_capability
    if _upload_capability is None:
        settings = get_settings()
        chunk_size = getattr(settings.milvus_kb, "default_chunk_size", 512)
        chunk_overlap = getattr(settings.milvus_kb, "default_chunk_overlap", 50)
        _upload_capability = MilvusKBUploadCapability(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    return _upload_capability


# ============================================================================
# Request/Response Schemas
# ============================================================================


class DocumentUploadRequest(BaseModel):
    """Request for document upload."""

    form_title: str = Field(..., min_length=1, max_length=512, description="Document title")
    file_content: str = Field(..., min_length=1, description="Document content text")
    document_id: Optional[str] = Field(default=None, description="Optional document ID")
    chunk_size: Optional[int] = Field(default=512, ge=100, le=4096, description="Chunk size in characters")
    chunk_overlap: Optional[int] = Field(default=50, ge=0, le=512, description="Chunk overlap in characters")

    @field_validator("form_title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        """Validate title is not just whitespace."""
        if not v or not v.strip():
            raise ValueError("form_title cannot be empty or whitespace only")
        return v.strip()

    @field_validator("file_content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate content is not just whitespace."""
        if not v or not v.strip():
            raise ValueError("file_content cannot be empty or whitespace only")
        return v


class DocumentUploadResponse(BaseModel):
    """Response from document upload."""

    success: bool = Field(..., description="Whether upload succeeded")
    document_id: str = Field(..., description="Unique document identifier")
    chunk_count: int = Field(..., ge=0, description="Number of chunks created")
    inserted_count: int = Field(..., ge=0, description="Number of chunks inserted")
    timing_ms: float = Field(..., ge=0, description="Processing time in milliseconds")
    trace_id: str = Field(..., description="Trace ID for observability")


class CollectionInfo(BaseModel):
    """Collection information."""

    collection_name: str = Field(..., description="Collection name")
    exists: bool = Field(..., description="Whether collection exists")
    document_count: int = Field(..., ge=0, description="Number of documents")
    chunk_count: int = Field(..., ge=0, description="Number of chunks")
    schema_fields: List[str] = Field(default_factory=list, description="Schema field names")
    indexes: List[str] = Field(default_factory=list, description="Index names")


class CollectionCreateRequest(BaseModel):
    """Request for collection creation."""

    collection_name: str = Field(
        default="knowledge_base",
        description="Collection name"
    )
    dimension: int = Field(default=1024, description="Embedding vector dimension")
    drop_existing: bool = Field(default=False, description="Drop existing collection if exists")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Health status: healthy, unhealthy, or degraded")
    milvus_connected: bool = Field(..., description="Whether Milvus is accessible")
    collection_exists: bool = Field(..., description="Whether collection exists")
    embedding_available: bool = Field(..., description="Whether embedding service is available")
    error: Optional[str] = Field(default=None, description="Error message if unhealthy")


# ============================================================================
# API Endpoints
# ============================================================================


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    request: DocumentUploadRequest,
    http_request: Request,
) -> DocumentUploadResponse:
    """
    Upload a document to the Milvus knowledge base.

    This endpoint handles:
    - Text chunking with configurable size and overlap
    - Embedding generation using the cloud embedding service
    - Document insertion into Milvus with hybrid search support
    - Automatic BM25 sparse vector generation

    Args:
        request: Document upload request
        http_request: HTTP request for trace ID extraction

    Returns:
        Upload result with document ID and statistics

    Raises:
        HTTPException: For validation errors or service failures
    """
    trace_id = http_request.headers.get("X-Trace-ID", "")
    if not trace_id:
        trace_id = str(uuid.uuid4())[:8]

    logger.info(
        "Document upload request received",
        extra={
            "trace_id": trace_id,
            "title": request.form_title[:50],
            "content_length": len(request.file_content),
        },
    )

    try:
        # Validate request
        if not request.form_title or not request.form_title.strip():
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_title",
                    "message": "Document title cannot be empty",
                    "trace_id": trace_id,
                },
            )

        if not request.file_content or not request.file_content.strip():
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_content",
                    "message": "Document content cannot be empty",
                    "trace_id": trace_id,
                },
            )

        # Validate overlap < chunk_size
        chunk_size = request.chunk_size or 512
        chunk_overlap = request.chunk_overlap or 50
        if chunk_overlap >= chunk_size:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_chunk_params",
                    "message": "chunk_overlap must be less than chunk_size",
                    "trace_id": trace_id,
                },
            )

        # Get capability and execute
        capability = get_upload_capability()

        upload_input = MilvusKBUploadInput(
            form_title=request.form_title,
            file_content=request.file_content,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            document_id=request.document_id,
            trace_id=trace_id,
        )

        result = await capability.execute(upload_input)

        logger.info(
            "Document upload completed successfully",
            extra={
                "trace_id": trace_id,
                "document_id": result.document_id,
                "chunk_count": result.chunk_count,
                "inserted_count": result.inserted_count,
                "timing_ms": result.timing_ms,
            },
        )

        return DocumentUploadResponse(
            success=result.success,
            document_id=result.document_id,
            chunk_count=result.chunk_count,
            inserted_count=result.inserted_count,
            timing_ms=result.timing_ms,
            trace_id=trace_id,
        )

    except HTTPException:
        raise

    except (RetrievalError, EmbeddingError) as e:
        logger.error(
            "Document upload failed",
            extra={"trace_id": trace_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "upload_failed",
                "message": "Failed to upload document to knowledge base",
                "detail": str(e) if get_settings().server.log_level == "DEBUG" else None,
                "trace_id": trace_id,
            },
        )

    except Exception as e:
        logger.error(
            "Document upload unexpected error",
            extra={"trace_id": trace_id, "error": str(e)},
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": "Internal server error",
                "trace_id": trace_id,
            },
        )


@router.post("/collection/create", response_model=Dict[str, Any])
async def create_collection(
    request: CollectionCreateRequest,
    http_request: Request,
) -> Dict[str, Any]:
    """
    Create a BM25-enabled hybrid collection in Milvus.

    This creates a collection with:
    - Dense vector field for semantic search
    - Sparse vector field (auto-generated) for BM25 keyword search
    - Proper indexes for hybrid search
    - BM25 function for sparse vector generation

    Args:
        request: Collection creation parameters
        http_request: HTTP request for trace ID extraction

    Returns:
        Collection creation result

    Raises:
        HTTPException: For validation errors or creation failures
    """
    trace_id = http_request.headers.get("X-Trace-ID", "")
    if not trace_id:
        trace_id = str(uuid.uuid4())[:8]

    logger.info(
        "Collection creation request received",
        extra={
            "trace_id": trace_id,
            "collection_name": request.collection_name,
            "dimension": request.dimension,
            "drop_existing": request.drop_existing,
        },
    )

    try:
        from rag_service.utils.milvus_collection import create_hybrid_collection

        result = await create_hybrid_collection(
            collection_name=request.collection_name,
            dimension=request.dimension,
            drop_existing=request.drop_existing,
        )

        logger.info(
            "Collection creation completed",
            extra={
                "trace_id": trace_id,
                "collection_name": request.collection_name,
                "created": result.get("created", False),
            },
        )

        return {
            "success": True,
            "collection_name": request.collection_name,
            "created": result.get("created", False),
            "existed": result.get("existed", False),
            "trace_id": trace_id,
        }

    except Exception as e:
        logger.error(
            "Collection creation failed",
            extra={"trace_id": trace_id, "error": str(e)},
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "collection_creation_failed",
                "message": "Failed to create collection",
                "detail": str(e) if get_settings().server.log_level == "DEBUG" else None,
                "trace_id": trace_id,
            },
        )


@router.get("/collection/info", response_model=CollectionInfo)
async def get_collection_info(
    collection_name: str = Query(default="knowledge_base", description="Collection name"),
    http_request: Request = None,
) -> CollectionInfo:
    """
    Get information about a Milvus collection.

    Args:
        collection_name: Name of the collection
        http_request: HTTP request for trace ID extraction

    Returns:
        Collection information

    Raises:
        HTTPException: For retrieval failures
    """
    trace_id = http_request.headers.get("X-Trace-ID", "") if http_request else ""
    if not trace_id:
        trace_id = str(uuid.uuid4())[:8]

    try:
        from rag_service.utils.milvus_collection import get_collection_stats

        stats = await get_collection_stats(collection_name)

        return CollectionInfo(
            collection_name=collection_name,
            exists=stats.get("exists", False),
            document_count=stats.get("document_count", 0),
            chunk_count=stats.get("chunk_count", 0),
            schema_fields=stats.get("schema_fields", []),
            indexes=stats.get("indexes", []),
        )

    except Exception as e:
        logger.error(
            "Collection info retrieval failed",
            extra={"trace_id": trace_id, "collection_name": collection_name, "error": str(e)},
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "collection_info_failed",
                "message": "Failed to retrieve collection information",
                "detail": str(e) if get_settings().server.log_level == "DEBUG" else None,
                "trace_id": trace_id,
            },
        )


@router.get("/health", response_model=HealthResponse)
async def health_check(
    http_request: Request,
) -> HealthResponse:
    """
    Health check for Milvus knowledge base components.

    Checks:
    - Milvus connectivity
    - Collection existence
    - Embedding service availability

    Args:
        http_request: HTTP request for trace ID extraction

    Returns:
        Health status information
    """
    trace_id = http_request.headers.get("X-Trace-ID", "")
    if not trace_id:
        trace_id = str(uuid.uuid4())[:8]

    # Default values
    milvus_connected = False
    collection_exists = False
    embedding_available = False
    error_message = None

    try:
        settings = get_settings()
        collection_name = settings.milvus_kb.collection_name

        # Check Milvus connection
        try:
            milvus_client = await get_milvus_kb_client()
            milvus_connected = await milvus_client.health_check()
        except Exception as e:
            error_message = str(e)
            logger.warning(f"Milvus connection check failed: {e}")

        # Check collection existence
        if milvus_connected:
            try:
                from pymilvus import utility

                client = await milvus_client._get_client()
                collections = client.list_collections()
                collection_names = []

                for c in collections:
                    if isinstance(c, str):
                        collection_names.append(c)
                    elif isinstance(c, dict):
                        collection_names.append(c.get("name", ""))

                collection_exists = collection_name in collection_names
            except Exception as e:
                logger.warning(f"Failed to check collection existence: {e}")

        # Check embedding service
        try:
            from rag_service.retrieval.embeddings import get_http_embedding_service

            embedding_service = await get_http_embedding_service()
            # Simple check - if we can get the service, it's available
            embedding_available = embedding_service is not None
        except Exception:
            embedding_available = False

        # Determine overall status
        if milvus_connected and collection_exists and embedding_available:
            status = "healthy"
        elif milvus_connected:
            status = "degraded"
        else:
            status = "unhealthy"

        return HealthResponse(
            status=status,
            milvus_connected=milvus_connected,
            collection_exists=collection_exists,
            embedding_available=embedding_available,
            error=error_message,
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            milvus_connected=False,
            collection_exists=False,
            embedding_available=False,
            error=str(e),
        )
