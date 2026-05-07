"""
API route definitions for RAG Service.

This module defines all HTTP endpoints using FastAPI. All routes
use Capability interfaces ONLY - they NEVER access components directly.

CORE ARCHITECTURE: HTTP Routes → Capabilities → Components
"""

import asyncio
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse

from rag_service.api.schemas import (
    DocumentDeleteResponse,
    DocumentUploadRequest,
    DocumentUploadResponse,
    ExternalKBChunkInfo,
    ExternalKBQueryRequest,
    ExternalKBQueryResponse,
    HealthResponse,
    ModelInfo,
    ModelsResponse,
    ObservabilityMetricsResponse,
    QueryRequest,
    QueryResponse,
    TraceResponse,
)
from rag_service.capabilities.base import get_capability_registry
from rag_service.capabilities.document_management import (
    DocumentManagementCapability,
    DocumentManagementInput,
)
from rag_service.capabilities.health_check import (
    HealthCheckCapability,
    HealthCheckInput,
)
from rag_service.capabilities.knowledge_query import (
    KnowledgeQueryCapability,
    KnowledgeQueryInput,
)
from rag_service.capabilities.model_discovery import (
    ModelDiscoveryCapability,
    ModelDiscoveryInput,
)
from rag_service.core.logger import get_logger


# Module logger
logger = get_logger(__name__)

# Deprecation dependency — adds header to all legacy route responses
async def _deprecation_header(response: Response):
    response.headers["Deprecation"] = "true; version=0.2.0"


# Create API router
router = APIRouter(
    prefix="/api/v1",
    tags=["v1 (deprecated)"],
    dependencies=[Depends(_deprecation_header)],
)


# ============================================================================
# Health Endpoints
# ============================================================================

@router.get("/health", response_model=HealthResponse)
async def health_check(
    detailed: bool = Query(False, description="Return detailed health information"),
) -> HealthResponse:
    """
    Get service health status.

    Checks the health of all registered capabilities and returns
    aggregated status information.
    """
    registry = get_capability_registry()
    capability = registry.get("HealthCheckCapability")

    input_data = HealthCheckInput(
        trace_id="",
        detailed=detailed,
    )

    result = await capability.execute(input_data)

    # Convert to health response format
    components = {c.name: c.status for c in result.components}

    return HealthResponse(
        status=result.overall_status,
        components=components,
        uptime_ms=result.uptime_ms,
    )


# ============================================================================
# Query Endpoints
# ============================================================================

@router.post("/ai/agent", response_model=QueryResponse)
async def query_agent(request: QueryRequest) -> QueryResponse:
    """
    Query AI agent with knowledge base context.

    Main endpoint for User Story 1 - Knowledge Base Query.
    Retrieves relevant context from knowledge base and generates
    AI-powered answer using configured LLM.

    Returns answer with retrieved chunks and trace_id for correlation.
    """
    registry = get_capability_registry()
    capability = registry.get("KnowledgeQueryCapability")

    if not capability:
        raise HTTPException(
            status_code=503,
            detail={"error": "SERVICE_UNAVAILABLE", "message": "Knowledge query service not available"}
        )

    import uuid
    trace_id = request.trace_id or f"trace_{uuid.uuid4().hex}"

    start_time = asyncio.get_event_loop().time()

    try:
        # Convert API request to capability input
        input_data = KnowledgeQueryInput(
            query=request.question if hasattr(request, 'question') else request.query,
            top_k=request.top_k if hasattr(request, 'top_k') else 5,
            trace_id=trace_id,
            collection_name="knowledge_base",
            model_hint=getattr(request, 'model_hint', None),
            context=getattr(request, 'context', {}),
        )

        # Execute via capability
        result = await capability.execute(input_data)

        # Convert to API response format
        chunks = [
            {
                "chunk_id": c.get("chunk_id", c.get("id", "")),
                "content": c.get("content", ""),
                "score": c.get("score", 0.0),
                "source_doc": c.get("source_doc", ""),
                "metadata": c.get("metadata", {}),
            }
            for c in result.chunks if hasattr(result, 'chunks')
        ]

        query_time_ms = (asyncio.get_event_loop().time() - start_time) * 1000

        return QueryResponse(
            answer=result.answer if hasattr(result, 'answer') else "Processing complete",
            chunks=chunks,  # type: ignore
            trace_id=result.trace_id,
            query_time_ms=query_time_ms,
        )

    except Exception as e:
        logger.error("Agent query failed", extra={"error": str(e), "trace_id": trace_id})
        raise HTTPException(
            status_code=500,
            detail={"error": "QUERY_FAILED", "message": str(e), "trace_id": trace_id}
        )


@router.post("/query", response_model=QueryResponse)
async def query_knowledge_base(request: QueryRequest) -> QueryResponse:
    """
    Query the knowledge base.

    Performs semantic search on the knowledge base and returns
    relevant chunks along with AI-generated answers.
    """
    registry = get_capability_registry()
    capability = registry.get("KnowledgeQueryCapability")

    # Convert API request to capability input
    input_data = KnowledgeQueryInput(
        query=request.query,
        top_k=request.top_k,
        trace_id=request.trace_id or "",
        collection_name="knowledge_base",
    )

    # Execute via capability
    result = await capability.execute(input_data)

    # Convert to API response format
    chunks = [
        {
            "id": c.id,
            "content": c.content,
            "metadata": c.metadata,
            "score": c.score,
        }
        for c in result.chunks
    ]

    # Mock answer for now (will be replaced by LLM inference)
    answer = f"Based on {len(chunks)} retrieved chunks, here's a response..."

    return QueryResponse(
        answer=answer,
        chunks=chunks,  # type: ignore
        trace_id=result.trace_id,
        query_time_ms=result.query_time_ms,
    )


@router.post("/external/query", response_model=ExternalKBQueryResponse)
async def query_external_kb(request: ExternalKBQueryRequest) -> ExternalKBQueryResponse:
    """
    Query the external HTTP knowledge base.

    This endpoint queries the external knowledge base service which provides
    document retrieval with support for:
    - Company-specific knowledge isolation (comp_id)
    - File type filtering (PublicDocReceive/PublicDocDispatch)
    - Vector, fulltext, and hybrid search (search_type)
    - Score threshold filtering (score_min)

    Returns retrieved chunks with metadata including document names,
    scores, and segment information.
    """
    from rag_service.capabilities.external_kb_query import (
        ExternalKBQueryCapability,
        ExternalKBQueryInput,
    )

    registry = get_capability_registry()
    capability = registry.get("ExternalKBQueryCapability")

    if not capability:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "SERVICE_UNAVAILABLE",
                "message": "External KB query service not available"
            }
        )

    import uuid
    trace_id = request.trace_id or f"ext_trace_{uuid.uuid4().hex[:8]}"

    start_time = asyncio.get_event_loop().time()

    try:
        # Convert API request to capability input
        input_data = ExternalKBQueryInput(
            query=request.query,
            comp_id=request.comp_id,
            file_type=request.file_type,
            doc_date=request.doc_date,
            keyword=request.keyword,
            top_k=request.top_k,
            score_min=request.score_min,
            search_type=request.search_type,
            trace_id=trace_id,
        )

        # Execute via capability
        result = await capability.execute(input_data)

        query_time_ms = (asyncio.get_event_loop().time() - start_time) * 1000

        # Convert to API response format
        chunks = [
            ExternalKBChunkInfo(
                id=c.get("id", ""),
                chunk_id=c.get("chunk_id", ""),
                content=c.get("content", ""),
                metadata=c.get("metadata", {}),
                score=c.get("score", 0.0),
                source_doc=c.get("source_doc", ""),
            )
            for c in result.chunks
        ]

        return ExternalKBQueryResponse(
            chunks=chunks,
            total_found=result.total_found,
            trace_id=trace_id,
            query_time_ms=query_time_ms,
        )

    except Exception as e:
        logger.error(
            "External KB query failed",
            extra={"error": str(e), "trace_id": trace_id}
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "EXTERNAL_KB_QUERY_FAILED",
                "message": str(e),
                "trace_id": trace_id
            }
        )


# ============================================================================
# Model Endpoints
# ============================================================================

@router.get("/models", response_model=ModelsResponse)
async def list_models(
    provider: str = Query("", description="Filter by provider"),
) -> ModelsResponse:
    """
    List available AI models.

    Returns all available models and providers through LiteLLM gateway.
    """
    registry = get_capability_registry()
    capability = registry.get("ModelDiscoveryCapability")

    input_data = ModelDiscoveryInput(
        provider=provider,
        detail_level="basic",
        trace_id="",
    )

    result = await capability.execute(input_data)

    # Convert to API response format
    models = [
        ModelInfo(
            id=m.id,
            name=m.name,
            provider=m.provider,
            context_length=m.context_length,
        )
        for m in result.models
    ]

    return ModelsResponse(
        models=models,
        providers=result.providers,
    )


# ============================================================================
# Document Endpoints
# ============================================================================

@router.post("/documents", response_model=DocumentUploadResponse)
async def upload_document(request: DocumentUploadRequest) -> DocumentUploadResponse:
    """
    Upload a document to the knowledge base.

    Adds a new document to the knowledge base with automatic
    chunking and embedding generation.
    """
    registry = get_capability_registry()
    capability = registry.get("DocumentManagementCapability")

    # Generate doc_id
    import uuid
    doc_id = f"doc_{uuid.uuid4().hex[:8]}"

    input_data = DocumentManagementInput(
        operation="add",
        doc_id=doc_id,
        content=request.content,
        metadata=request.metadata,
        trace_id="",
    )

    result = await capability.execute(input_data)

    return DocumentUploadResponse(
        doc_id=result.doc_id or doc_id,
        chunk_count=result.chunk_count or 5,
        trace_id=result.trace_id,
    )


@router.delete("/documents/{doc_id}", response_model=DocumentDeleteResponse)
async def delete_document(doc_id: str) -> DocumentDeleteResponse:
    """
    Delete a document from the knowledge base.

    Removes the specified document and all its chunks from
    the knowledge base.
    """
    registry = get_capability_registry()
    capability = registry.get("DocumentManagementCapability")

    input_data = DocumentManagementInput(
        operation="delete",
        doc_id=doc_id,
        trace_id="",
    )

    result = await capability.execute(input_data)

    return DocumentDeleteResponse(
        doc_id=result.doc_id or doc_id,
        trace_id=result.trace_id,
    )


@router.put("/documents/{doc_id}", response_model=DocumentUploadResponse)
async def update_document(doc_id: str, request: DocumentUploadRequest) -> DocumentUploadResponse:
    """
    Update a document in the knowledge base.

    Updates an existing document's content and metadata.
    Old chunks are removed and new chunks are indexed.
    """
    registry = get_capability_registry()
    capability = registry.get("DocumentManagementCapability")

    input_data = DocumentManagementInput(
        operation="update",
        doc_id=doc_id,
        content=request.content,
        metadata=request.metadata,
        trace_id="",
    )

    result = await capability.execute(input_data)

    return DocumentUploadResponse(
        doc_id=result.doc_id or doc_id,
        chunk_count=result.new_chunks_added or 0,
        trace_id=result.trace_id,
    )


# ============================================================================
# Trace Endpoints
# ============================================================================

@router.get("/traces/{trace_id}", response_model=TraceResponse)
async def get_trace(trace_id: str) -> TraceResponse:
    """
    Get detailed trace information by ID.

    Returns complete trace data with metrics from all three
    observability layers: Phidata (Agent), LiteLLM (LLM), Langfuse (Prompt).
    """
    from rag_service.capabilities.trace_observation import TraceObservationInput

    registry = get_capability_registry()
    capability = registry.get("TraceObservationCapability")

    if not capability:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "SERVICE_UNAVAILABLE",
                "message": "Trace observation service not available"
            }
        )

    try:
        input_data = TraceObservationInput(
            trace_id=trace_id,
            operation="get_trace",
        )

        result = await capability.execute(input_data)

        if not result.recorded or result.trace_data is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "NOT_FOUND",
                    "message": f"Trace {trace_id} not found"
                }
            )

        trace_data = result.trace_data

        return TraceResponse(
            trace_id=trace_data["trace_id"],
            request_id=trace_data["request_id"],
            request_prompt=trace_data["request_prompt"],
            user_context=trace_data["user_context"],
            start_time=trace_data["start_time"],
            end_time=trace_data.get("end_time"),
            status=trace_data["status"],
            spans=trace_data["spans"],
            phidata_data=trace_data["phidata_data"],
            litellm_data=trace_data["litellm_data"],
            langfuse_data=trace_data["langfuse_data"],
            metadata={
                "operation": result.metadata.get("operation"),
                "timestamp": result.metadata.get("timestamp"),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get trace failed", extra={"trace_id": trace_id, "error": str(e)})
        raise HTTPException(
            status_code=500,
            detail={"error": "TRACE_RETRIEVAL_FAILED", "message": str(e)}
        )


@router.get("/observability/metrics", response_model=ObservabilityMetricsResponse)
async def get_observability_metrics() -> ObservabilityMetricsResponse:
    """
    Get aggregated observability metrics.

    Returns cross-layer aggregated metrics from all three
    observability layers for system-wide analysis.
    """
    from rag_service.capabilities.trace_observation import TraceObservationInput
    from rag_service.observability.trace_manager import get_trace_manager
    from rag_service.observability.litellm_observer import get_litellm_observer
    from rag_service.observability.phidata_observer import get_phidata_observer

    try:
        # Get observers
        trace_manager = await get_trace_manager()
        litellm_observer = await get_litellm_observer()
        phidata_observer = await get_phidata_observer()

        # Get provider metrics from LiteLLM layer
        provider_metrics = await litellm_observer.get_all_provider_metrics()

        # Get tool metrics from Phidata layer
        tool_metrics = await phidata_observer.get_all_tool_metrics()

        # Get recent inferences
        recent_inferences = await litellm_observer.get_recent_inferences(limit=10)

        # Get recent executions
        recent_executions = await phidata_observer.get_recent_executions(limit=10)

        # Calculate summary statistics
        total_inferences = sum(m["total_requests"] for m in provider_metrics)
        total_cost = sum(m["total_cost"] for m in provider_metrics)

        return ObservabilityMetricsResponse(
            metrics={
                "total_inferences": total_inferences,
                "total_cost_usd": round(total_cost, 6),
                "provider_count": len(provider_metrics),
                "tool_count": len(tool_metrics),
            },
            agent_metrics={
                "tool_metrics": tool_metrics,
                "recent_executions": recent_executions[:5],
            },
            llm_metrics={
                "provider_metrics": provider_metrics,
                "recent_inferences": recent_inferences[:5],
            },
            prompt_metrics={
                "total_traces": len(trace_manager._traces),
            },
            summary={
                "timestamp": datetime.utcnow().isoformat(),
                "status": "healthy",
            },
        )

    except Exception as e:
        logger.error("Get observability metrics failed", extra={"error": str(e)})
        raise HTTPException(
            status_code=500,
            detail={"error": "METRICS_RETRIEVAL_FAILED", "message": str(e)}
        )


# ============================================================================
# Error Handlers (moved to main.py)
# ============================================================================

# Note: Exception handlers are registered in main.py at the app level,
# not at the router level. This is the correct FastAPI pattern.
