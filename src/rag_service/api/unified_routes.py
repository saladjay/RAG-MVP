"""
Unified API routes for RAG Service.

Provides 5 endpoints with clear, non-overlapping responsibilities:
- POST /query          — Unified query (all retrieval/quality modes)
- POST /query/stream   — Streaming query variant
- POST /documents      — Document management (upload/update/delete)
- GET  /traces/{id}    — Trace inspection
- GET  /health         — Health check
- GET  /models         — List available models

API Reference:
- Location: src/rag_service/api/unified_routes.py
"""

import uuid
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from rag_service.api.unified_schemas import (
    UnifiedQueryRequest,
    QueryResponse,
    DocumentRequest,
    DocumentResponse,
    HealthResponse,
)
from rag_service.capabilities.base import get_capability_registry
from rag_service.capabilities.query_capability import QueryCapability
from rag_service.capabilities.management_capability import ManagementCapability
from rag_service.capabilities.trace_capability import TraceCapability
from rag_service.config import get_settings
from rag_service.core.exceptions import (
    GenerationError,
    RetrievalError,
)
from rag_service.core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Unified API"])

DEPRECATION_HEADER = "true; version=0.2.0"


def _get_trace_id(request: Request) -> str:
    """Extract or generate trace ID from request."""
    trace_id = request.headers.get("X-Trace-ID", "")
    if not trace_id:
        trace_id = str(uuid.uuid4())[:8]
    return trace_id


# ============================================================================
# Query Endpoints
# ============================================================================


@router.post("/query", response_model=QueryResponse)
async def unified_query(
    request: UnifiedQueryRequest,
    http_request: Request,
) -> QueryResponse:
    """Unified query endpoint for all retrieval and quality modes.

    Handles queries regardless of retrieval backend (Milvus, External KB),
    quality mode (basic, dimension_gather, conversational), or LLM provider.
    All strategy selection is config-driven — callers never specify backends.

    Minimum viable request: {"query": "What is RAG?"}
    """
    trace_id = _get_trace_id(http_request)

    logger.info(
        "Unified query received",
        extra={"trace_id": trace_id, "query": request.query[:100]},
    )

    try:
        registry = get_capability_registry()
        capability: QueryCapability = registry.get("QueryCapability")

        result = await capability.execute(request)

        logger.info(
            "Unified query completed",
            extra={
                "trace_id": trace_id,
                "retrieval_count": result.metadata.retrieval_count,
            },
        )

        return result

    except RetrievalError as e:
        logger.error(
            "Query retrieval failed",
            extra={"trace_id": trace_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=503,
            detail={
                "error": "kb_unavailable",
                "message": "Knowledge base temporarily unavailable",
                "trace_id": trace_id,
                "is_fallback": True,
            },
        )

    except GenerationError as e:
        logger.error(
            "Query generation failed",
            extra={"trace_id": trace_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "generation_failed",
                "message": "Answer generation failed",
                "trace_id": trace_id,
            },
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            "Query unexpected error",
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


@router.post("/query/stream")
async def unified_query_stream(
    request: UnifiedQueryRequest,
    http_request: Request,
) -> StreamingResponse:
    """Streaming query endpoint.

    Same as POST /query but streams response tokens as Server-Sent Events.
    """
    trace_id = _get_trace_id(http_request)

    async def generate():
        try:
            registry = get_capability_registry()
            capability: QueryCapability = registry.get("QueryCapability")

            async for token in capability.stream_execute(request):
                yield f"data: {token}\n\n"

            yield "data: [DONE]\n\n"

        except RetrievalError:
            error_msg = "Knowledge base temporarily unavailable."
            for char in error_msg:
                yield f"data: {char}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"data: [ERROR] {str(e)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "X-Trace-ID": trace_id,
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


# ============================================================================
# Document Endpoint
# ============================================================================


@router.post("/documents", response_model=DocumentResponse)
async def manage_documents(
    request: DocumentRequest,
    http_request: Request,
) -> DocumentResponse:
    """Unified document management endpoint.

    Handles upload, update, and delete via the 'operation' field.
    """
    trace_id = _get_trace_id(http_request)

    try:
        registry = get_capability_registry()
        capability: ManagementCapability = registry.get("ManagementCapability")

        result = await capability.execute(request)
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": str(e), "trace_id": trace_id})
    except Exception as e:
        logger.error(f"Document operation failed: {e}", extra={"trace_id": trace_id})
        raise HTTPException(
            status_code=500,
            detail={"error": "operation_failed", "message": str(e), "trace_id": trace_id},
        )


# ============================================================================
# Health Endpoint
# ============================================================================


@router.get("/health")
async def health_check(http_request: Request) -> Dict[str, Any]:
    """System health check.

    Returns health status of all components: Milvus, LiteLLM, External KB.
    """
    try:
        registry = get_capability_registry()
        capability: TraceCapability = registry.get("TraceCapability")
        return await capability.health_check()
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}


# ============================================================================
# Traces Endpoint
# ============================================================================


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str, http_request: Request) -> Dict[str, Any]:
    """Get trace details by ID.

    Returns trace data from the three-layer observability stack.
    """
    try:
        registry = get_capability_registry()
        capability: TraceCapability = registry.get("TraceCapability")
        return await capability.get_trace(trace_id)
    except Exception as e:
        logger.error(f"Trace retrieval failed: {e}")
        return {"trace_id": trace_id, "error": str(e)}


# ============================================================================
# Models Endpoint
# ============================================================================


@router.get("/models")
async def list_models(http_request: Request) -> Dict[str, Any]:
    """List available models via LiteLLM gateway."""
    try:
        registry = get_capability_registry()
        capability: ManagementCapability = registry.get("ManagementCapability")
        models = await capability.list_models()
        return {"models": models}
    except Exception as e:
        logger.error(f"Model listing failed: {e}")
        return {"models": [], "error": str(e)}
