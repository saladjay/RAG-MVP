"""
QA Pipeline API routes for RAG Service.

This module provides HTTP endpoints for question-answering functionality
including query processing, streaming responses, and health checks.
"""

from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from rag_service.api.qa_schemas import (
    QAQueryRequest,
    QAQueryResponse,
    QAErrorResponse,
    FallbackErrorType,
    QAMetadata,
)
from rag_service.capabilities.qa_pipeline import (
    QAPipelineCapability,
    QAPipelineInput,
    QAPipelineMetadata,
)
from rag_service.capabilities.model_inference import ModelInferenceCapability
from rag_service.capabilities.external_kb_query import ExternalKBQueryCapability
from rag_service.config import get_settings
from rag_service.core.exceptions import GenerationError, RetrievalError
from rag_service.core.logger import get_logger


# Module logger
logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/qa", tags=["QA"])

# Global capability instance (will be initialized on startup)
_qa_capability: QAPipelineCapability = None


def get_qa_capability() -> QAPipelineCapability:
    """Get or initialize the QA pipeline capability."""
    global _qa_capability
    if _qa_capability is None:
        settings = get_settings()
        _qa_capability = QAPipelineCapability(
            external_kb_capability=ExternalKBQueryCapability(),
            model_inference_capability=None,  # Will be initialized in execute()
        )
    return _qa_capability


@router.post("/query", response_model=QAQueryResponse)
async def qa_query(
    request: QAQueryRequest,
    http_request: Request,
) -> QAQueryResponse:
    """
    Process a question-answering query.

    This endpoint orchestrates the complete QA pipeline:
    - Query rewriting (if enabled)
    - Knowledge base retrieval
    - Answer generation
    - Hallucination detection (if enabled)

    Args:
        request: QA query request with question and optional context.
        http_request: HTTP request for trace ID extraction.

    Returns:
        Generated answer with sources and metadata.

    Raises:
        HTTPException: For validation errors or service failures.
    """
    trace_id = http_request.headers.get("X-Trace-ID", "")
    if not trace_id:
        import uuid
        trace_id = str(uuid.uuid4())[:8]

    logger.info(
        "QA query request received",
        extra={
            "trace_id": trace_id,
            "query": request.query[:100],
        },
    )

    try:
        # Validate request
        if not request.query or not request.query.strip():
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_query",
                    "message": "Query cannot be empty",
                    "trace_id": trace_id,
                },
            )

        # Validate context company_id format if provided
        if request.context and request.context.company_id:
            company_id = request.context.company_id
            if not (company_id.startswith("N") and company_id[1:].isdigit()):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "invalid_query",
                        "message": "Invalid company_id format (expected N followed by digits, e.g., N000131)",
                        "trace_id": trace_id,
                    },
                )

        # Get capability and execute
        capability = get_qa_capability()
        options = request.options or {}

        pipeline_input = QAPipelineInput(
            query=request.query,
            context=request.context,
            options=options,
            trace_id=trace_id,
        )

        result = await capability.execute(pipeline_input)

        logger.info(
            "QA query completed successfully",
            extra={
                "trace_id": trace_id,
                "retrieval_count": result.pipeline_metadata.retrieval_count,
                "has_sources": len(result.sources) > 0,
            },
        )

        # Convert QAPipelineMetadata to QAMetadata for API response
        api_metadata = QAMetadata(
            trace_id=result.pipeline_metadata.trace_id,
            query_rewritten=result.pipeline_metadata.query_rewritten,
            original_query=result.pipeline_metadata.original_query,
            rewritten_query=result.pipeline_metadata.rewritten_query,
            retrieval_count=result.pipeline_metadata.retrieval_count,
            timing_ms=result.pipeline_metadata.timing,
        )

        # Return response
        return QAQueryResponse(
            answer=result.answer,
            sources=result.sources,
            hallucination_status=result.hallucination_status,
            metadata=api_metadata,
        )

    except HTTPException:
        raise

    except RetrievalError as e:
        logger.error(
            "QA query retrieval failed",
            extra={"trace_id": trace_id, "error": str(e)},
        )
        # Return fallback response for retrieval errors
        raise HTTPException(
            status_code=503,
            detail={
                "error": "kb_unavailable",
                "message": "知识库暂时无法访问，请稍后再试",
                "trace_id": trace_id,
                "is_fallback": True,
            },
        )

    except GenerationError as e:
        logger.error(
            "QA query generation failed",
            extra={"trace_id": trace_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "generation_failed",
                "message": "生成答案时发生错误，请稍后重试",
                "detail": str(e) if get_settings().server.log_level == "DEBUG" else None,
                "trace_id": trace_id,
            },
        )

    except Exception as e:
        logger.error(
            "QA query unexpected error",
            extra={"trace_id": trace_id, "error": str(e)},
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": "内部服务器错误",
                "trace_id": trace_id,
            },
        )


@router.post("/query/stream")
async def qa_query_stream(
    request: QAQueryRequest,
    http_request: Request,
) -> StreamingResponse:
    """
    Process a QA query with streaming response.

    This endpoint streams the answer tokens as they are generated.
    Hallucination detection runs asynchronously after completion.

    Args:
        request: QA query request with question and optional context.
        http_request: HTTP request for trace ID extraction.

    Returns:
        Server-Sent Events stream with answer tokens.

    Raises:
        HTTPException: For validation errors or service failures.
    """
    trace_id = http_request.headers.get("X-Trace-ID", "")
    if not trace_id:
        import uuid
        trace_id = str(uuid.uuid4())[:8]

    logger.info(
        "QA query stream request received",
        extra={"trace_id": trace_id, "query": request.query[:100]},
    )

    # Validate request
    if not request.query or not request.query.strip():
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_query",
                "message": "Query cannot be empty",
                "trace_id": trace_id,
            },
        )

    # Validate context company_id format if provided
    if request.context and request.context.company_id:
        company_id = request.context.company_id
        if not (company_id.startswith("N") and company_id[1:].isdigit()):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_query",
                    "message": "Invalid company_id format (expected N followed by digits, e.g., N000131)",
                    "trace_id": trace_id,
                },
            )

    async def generate_stream():
        """Generate streaming response with tokens."""
        try:
            capability = get_qa_capability()
            options = request.options or {}

            # Create streaming input
            from rag_service.capabilities.qa_pipeline import QAPipelineInput

            pipeline_input = QAPipelineInput(
                query=request.query,
                context=request.context,
                options=options,
                trace_id=trace_id,
            )

            # Stream tokens from the capability
            hallucination_status = {"checked": False, "passed": False, "confidence": 0.0}

            async for token in capability.stream_execute(pipeline_input):
                # Yield token in SSE format
                yield f"data: {token}\n\n"

            # After streaming completes, update hallucination status if enabled
            if options.enable_hallucination_check:
                # Hallucination check runs in background
                # The status will be available via the header
                hallucination_status = {"checked": True, "passed": True, "confidence": 0.0}

            # Send completion signal
            yield "data: [DONE]\n\n"

        except RetrievalError as e:
            logger.error(
                "QA query stream retrieval failed",
                extra={"trace_id": trace_id, "error": str(e)},
            )
            # Send error message as stream
            error_msg = "知识库暂时无法访问，请稍后再试。"
            for char in error_msg:
                yield f"data: {char}\n\n"
            yield "data: [DONE]\n\n"

        except GenerationError as e:
            logger.error(
                "QA query stream generation failed",
                extra={"trace_id": trace_id, "error": str(e)},
            )
            # Send error message as stream
            error_msg = "生成答案时发生错误，请稍后重试。"
            for char in error_msg:
                yield f"data: {char}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(
                "QA query stream unexpected error",
                extra={"trace_id": trace_id, "error": str(e)},
                exc_info=True,
            )
            # Send error message as stream
            error_msg = "内部服务器错误。"
            for char in error_msg:
                yield f"data: {char}\n\n"
            yield "data: [DONE]\n\n"

    # Create streaming response with headers
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "X-Hallucination-Checked": "pending",
            "X-Trace-ID": trace_id,
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/health")
async def qa_health_check(request: Request) -> Dict[str, Any]:
    """
    Health check for QA pipeline components.

    Returns status of external KB, LiteLLM, hallucination detector,
    and fallback service.

    Args:
        request: HTTP request.

    Returns:
        Health status information.
    """
    try:
        capability = get_qa_capability()
        health = await capability.get_health()
        return health
    except Exception as e:
        logger.error(f"QA health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
        }


# Include router in main app
# In main.py, add:
# from rag_service.api.qa_routes import router as qa_router
# app.include_router(qa_router)
