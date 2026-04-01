"""
API route definitions for Prompt Management Service.

This module defines all HTTP endpoints using FastAPI. Routes are
organized by functional area and follow the /api/v1 prefix.

Route Groups:
- Health: Service health check
- Prompt Retrieval: GET/POST prompts for retrieval (US1)
- Prompt Management: CRUD operations for prompts (US2)
- A/B Testing: A/B test endpoints (US3)
- Analytics: Trace analysis endpoints (US4)
"""

import uuid
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse

from prompt_service.api.schemas import (
    ABTestCreateRequest,
    ABTestListResponse,
    ABTestResponse,
    ABTestResultsResponse,
    AnalyticsResponse,
    ErrorResponse,
    HealthResponse,
    MetricsSummary,
    PromptCreateRequest,
    PromptCreateResponse,
    PromptDeleteResponse,
    PromptInfoResponse,
    PromptListResponse,
    PromptRetrieveRequest,
    PromptRetrieveResponse,
    PromptUpdateRequest,
    PromptUpdateResponse,
    RollbackRequest,
    RollbackResponse,
    Section,
    SelectWinnerRequest,
    SelectWinnerResponse,
    StructuredSectionSchema,
    TraceInsightSchema,
    TraceItem,
    TraceSearchResponse,
    VariableDefSchema,
    VariantInfo,
    VersionHistoryItem,
    VersionHistoryResponse,
)
from prompt_service.models.prompt import StructuredSection, VariableDef
from prompt_service.core.exceptions import (
    PromptNotFoundError,
    PromptServiceError,
    PromptServiceUnavailableError,
    PromptValidationError,
)
from prompt_service.core.logger import get_logger, set_trace_id
from prompt_service.services.prompt_retrieval import get_prompt_retrieval_service

logger = get_logger(__name__)


def _get_http_status_for_error(error: PromptServiceError) -> int:
    """Get the appropriate HTTP status code for a service error.

    Args:
        error: The service error

    Returns:
        HTTP status code
    """
    # First check specific exception types
    from prompt_service.core.exceptions import (
        ABTestNotFoundError,
        ABTestValidationError,
    )

    if isinstance(error, PromptNotFoundError):
        return status.HTTP_404_NOT_FOUND
    elif isinstance(error, ABTestNotFoundError):
        return status.HTTP_404_NOT_FOUND
    elif isinstance(error, PromptValidationError):
        return status.HTTP_400_BAD_REQUEST
    elif isinstance(error, ABTestValidationError):
        return status.HTTP_400_BAD_REQUEST
    elif isinstance(error, PromptServiceUnavailableError):
        return status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        return status.HTTP_500_INTERNAL_SERVER_ERROR


# Create API router
router = APIRouter(prefix="/api/v1", tags=["v1"])


# ============================================================================
# Health Endpoints
# ============================================================================

@router.get("/health", response_model=HealthResponse)
async def health_check(
    detailed: bool = Query(False, description="Return detailed health information"),
) -> HealthResponse:
    """
    Get service health status.

    Checks the health of the prompt service and returns status information.
    """
    from prompt_service.config import get_config
    from prompt_service.services.langfuse_client import get_langfuse_client

    config = get_config()
    langfuse_client = get_langfuse_client()
    langfuse_health = langfuse_client.health()

    components = {
        "langfuse": langfuse_health["status"],
        "cache": "enabled" if config.cache.enabled else "disabled",
    }

    return HealthResponse(
        status="healthy" if langfuse_health["status"] == "connected" else "degraded",
        version="0.1.0",
        components=components,
        uptime_ms=0.0,  # TODO: Track actual uptime
    )


# ============================================================================
# Prompt Retrieval Endpoints (US1)
# ============================================================================

@router.post("/prompts/{template_id}/retrieve", response_model=PromptRetrieveResponse)
async def retrieve_prompt(
    template_id: str,
    request: PromptRetrieveRequest,
) -> PromptRetrieveResponse:
    """
    Retrieve and render a prompt template.

    Retrieves the active version of a prompt template, renders it with
    the provided variables, and returns the assembled prompt.

    Args:
        template_id: The prompt template identifier
        request: The retrieve request with variables and options

    Returns:
        Rendered prompt with metadata

    Raises:
        HTTPException: If prompt not found or validation fails
    """
    # Generate trace_id for this request
    trace_id = str(uuid.uuid4())
    set_trace_id(trace_id)

    logger.info(
        "Prompt retrieve request",
        extra={
            "template_id": template_id,
            "trace_id": trace_id,
        }
    )

    try:
        retrieval_service = get_prompt_retrieval_service()

        # Retrieve and assemble the prompt
        result = await retrieval_service.retrieve(
            template_id=template_id,
            variables=request.variables,
            context=request.context,
            retrieved_docs=[doc.model_dump() for doc in request.retrieved_docs],
            version=request.options.version_id,
            trace_id=trace_id,
        )

        # Convert sections to response format
        sections_data = None
        if request.options.include_metadata and result.sections:
            sections_data = [
                Section(name=name, content=content)
                for name, content in result.sections
            ]

        return PromptRetrieveResponse(
            content=result.content,
            template_id=result.template_id,
            version_id=result.version_id,
            variant_id=result.variant_id,
            sections=sections_data,
            metadata=result.metadata,
            trace_id=trace_id,
            from_cache=result.from_cache,
        )

    except PromptNotFoundError as e:
        logger.warning(
            "Prompt not found",
            extra={
                "template_id": template_id,
                "trace_id": trace_id,
                "error": e.message,
            }
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.to_dict(),
        )

    except PromptValidationError as e:
        logger.warning(
            "Prompt validation failed",
            extra={
                "template_id": template_id,
                "trace_id": trace_id,
                "errors": e.validation_errors,
            }
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.to_dict(),
        )

    except PromptServiceUnavailableError as e:
        logger.error(
            "Service unavailable",
            extra={
                "template_id": template_id,
                "trace_id": trace_id,
                "error": e.message,
            }
        )
        # Return 503 with fallback content if available
        response_detail = e.to_dict()
        if e.fallback_provided and e.fallback_content:
            response_detail["fallback_content"] = e.fallback_content

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=response_detail,
        )

    except PromptServiceError as e:
        # This catches any PromptServiceError not already handled above
        # Use the helper to determine the correct status code
        http_status = _get_http_status_for_error(e)
        logger.error(
            "Prompt service error",
            extra={
                "template_id": template_id,
                "trace_id": trace_id,
                "error": e.message,
                "error_code": e.error_code,
                "http_status": http_status,
            }
        )
        raise HTTPException(
            status_code=http_status,
            detail=e.to_dict(),
        )


# ============================================================================
# Prompt Management Endpoints (US2)
# ============================================================================

@router.get("/prompts", response_model=PromptListResponse)
async def list_prompts(
    tag: str = Query("", description="Filter by tag"),
    search: str = Query("", description="Search in name/description"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
) -> PromptListResponse:
    """
    List all prompt templates.

    Returns a paginated list of prompt templates with optional filtering.
    """
    from prompt_service.services.prompt_management import get_prompt_management_service

    trace_id = str(uuid.uuid4())
    set_trace_id(trace_id)

    logger.info(
        "List prompts request",
        extra={"tag": tag, "search": search, "page": page, "trace_id": trace_id}
    )

    management_service = get_prompt_management_service()
    templates = await management_service.list(
        tag=tag or None,
        search=search or None,
        page=page,
        page_size=page_size,
    )

    # Convert templates to response format
    prompt_infos = []
    for template in templates:
        prompt_infos.append(PromptInfoResponse(
            template_id=template.template_id,
            name=template.name,
            description=template.description,
            version=template.version,
            sections=[
                StructuredSectionSchema(
                    name=s.name,
                    content=s.content,
                    is_required=s.is_required,
                    order=s.order,
                )
                for s in template.sections
            ],
            variables={
                name: VariableDefSchema(
                    name=name,
                    description=var_def.description,
                    type=var_def.type.value,
                    default_value=var_def.default_value,
                    is_required=var_def.is_required,
                )
                for name, var_def in template.variables.items()
            },
            tags=template.tags,
            is_active=template.is_active,
            is_published=template.is_published,
            created_at=template.created_at,
            updated_at=template.updated_at,
            created_by=template.created_by,
        ))

    return PromptListResponse(
        prompts=prompt_infos,
        total=len(prompt_infos),  # TODO: Get actual total from Langfuse
        page=page,
        page_size=page_size,
    )


@router.post("/prompts", response_model=PromptCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_prompt(request: PromptCreateRequest) -> PromptCreateResponse:
    """
    Create a new prompt template.

    Creates a new prompt template with the provided sections and variables.
    The template becomes immediately available for retrieval.
    """
    from prompt_service.services.prompt_management import get_prompt_management_service

    trace_id = str(uuid.uuid4())
    set_trace_id(trace_id)

    logger.info(
        "Create prompt request",
        extra={
            "template_id": request.template_id,
            "trace_id": trace_id,
        }
    )

    try:
        management_service = get_prompt_management_service()

        # Convert request schemas to models
        sections = [
            StructuredSection(
                name=s.name,
                content=s.content,
                is_required=s.is_required,
                order=s.order,
            )
            for s in request.sections
        ]

        variables = {
            name: VariableDef(
                name=name,
                description=v.description,
                type=v.type,
                default_value=v.default_value,
                is_required=v.is_required,
            )
            for name, v in request.variables.items()
        }

        template = await management_service.create(
            template_id=request.template_id,
            name=request.name,
            description=request.description,
            sections=sections,
            variables=variables,
            tags=request.tags,
            created_by="system",  # TODO: Get from auth context
            is_published=request.is_published,
        )

        return PromptCreateResponse(
            template_id=template.template_id,
            version=template.version,
            is_active=template.is_active,
            created_at=template.created_at,
            trace_id=trace_id,
        )

    except PromptValidationError as e:
        logger.warning(
            "Prompt validation failed",
            extra={
                "template_id": request.template_id,
                "errors": e.validation_errors,
                "trace_id": trace_id,
            }
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.to_dict(),
        )
    except PromptServiceError as e:
        http_status = _get_http_status_for_error(e)
        logger.error(
            "Prompt creation error",
            extra={
                "template_id": request.template_id,
                "error": e.message,
                "error_code": e.error_code,
                "http_status": http_status,
                "trace_id": trace_id,
            }
        )
        raise HTTPException(
            status_code=http_status,
            detail=e.to_dict(),
        )


@router.put("/prompts/{template_id}", response_model=PromptUpdateResponse)
async def update_prompt(
    template_id: str,
    request: PromptUpdateRequest,
) -> PromptUpdateResponse:
    """
    Update an existing prompt template.

    Updates a prompt template and creates a new version. The previous
    version is preserved in version history.
    """
    from prompt_service.services.prompt_management import get_prompt_management_service

    trace_id = str(uuid.uuid4())
    set_trace_id(trace_id)

    logger.info(
        "Update prompt request",
        extra={
            "template_id": template_id,
            "trace_id": trace_id,
        }
    )

    try:
        management_service = get_prompt_management_service()

        # Convert request schemas to models if provided
        sections = None
        if request.sections is not None:
            sections = [
                StructuredSection(
                    name=s.name,
                    content=s.content,
                    is_required=s.is_required,
                    order=s.order,
                )
                for s in request.sections
            ]

        variables = None
        if request.variables is not None:
            variables = {
                name: VariableDef(
                    name=name,
                    description=v.description,
                    type=v.type,
                    default_value=v.default_value,
                    is_required=v.is_required,
                )
                for name, v in request.variables.items()
            }

        # Get current version
        current = await management_service.get(template_id)
        previous_version = current.version if current else 1

        template = await management_service.update(
            template_id=template_id,
            name=request.name,
            description=request.description,
            sections=sections,
            variables=variables,
            tags=request.tags,
            change_description=request.change_description,
            updated_by="system",  # TODO: Get from auth context
        )

        return PromptUpdateResponse(
            template_id=template.template_id,
            version=template.version,
            previous_version=previous_version,
            is_active=template.is_active,
            updated_at=template.updated_at,
            trace_id=trace_id,
        )

    except PromptNotFoundError as e:
        logger.warning(
            "Prompt not found for update",
            extra={
                "template_id": template_id,
                "trace_id": trace_id,
                "error": e.message,
            }
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.to_dict(),
        )
    except PromptValidationError as e:
        logger.warning(
            "Prompt validation failed",
            extra={
                "template_id": template_id,
                "errors": e.validation_errors,
                "trace_id": trace_id,
            }
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.to_dict(),
        )
    except PromptServiceError as e:
        http_status = _get_http_status_for_error(e)
        logger.error(
            "Prompt update error",
            extra={
                "template_id": template_id,
                "error": e.message,
                "error_code": e.error_code,
                "http_status": http_status,
                "trace_id": trace_id,
            }
        )
        raise HTTPException(
            status_code=http_status,
            detail=e.to_dict(),
        )


@router.delete("/prompts/{template_id}", response_model=PromptDeleteResponse)
async def delete_prompt(template_id: str) -> PromptDeleteResponse:
    """
    Delete a prompt template.

    Performs a soft delete on the prompt template. The template
    is marked as deleted but remains in version history.
    """
    from prompt_service.services.prompt_management import get_prompt_management_service

    trace_id = str(uuid.uuid4())
    set_trace_id(trace_id)

    logger.info(
        "Delete prompt request",
        extra={
            "template_id": template_id,
            "trace_id": trace_id,
        }
    )

    try:
        management_service = get_prompt_management_service()

        deleted = await management_service.delete(
            template_id=template_id,
            deleted_by="system",  # TODO: Get from auth context
        )

        return PromptDeleteResponse(
            template_id=template_id,
            deleted=deleted,
            trace_id=trace_id,
        )

    except PromptNotFoundError as e:
        logger.warning(
            "Prompt not found for deletion",
            extra={
                "template_id": template_id,
                "trace_id": trace_id,
                "error": e.message,
            }
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.to_dict(),
        )
    except PromptServiceError as e:
        http_status = _get_http_status_for_error(e)
        logger.error(
            "Prompt deletion error",
            extra={
                "template_id": template_id,
                "error": e.message,
                "error_code": e.error_code,
                "http_status": http_status,
                "trace_id": trace_id,
            }
        )
        raise HTTPException(
            status_code=http_status,
            detail=e.to_dict(),
        )


# ============================================================================
# A/B Testing Endpoints (US3)
# ============================================================================

@router.post("/ab-tests", response_model=ABTestResponse, status_code=status.HTTP_201_CREATED)
async def create_ab_test(request: ABTestCreateRequest) -> ABTestResponse:
    """
    Create a new A/B test.

    Creates a new A/B test for comparing prompt variants.
    """
    from prompt_service.services.ab_testing import get_ab_testing_service

    trace_id = str(uuid.uuid4())
    set_trace_id(trace_id)

    logger.info(
        "Create A/B test request",
        extra={
            "template_id": request.template_id,
            "name": request.name,
            "trace_id": trace_id,
        }
    )

    try:
        from prompt_service.models.ab_test import ABTestConfig

        ab_service = get_ab_testing_service()

        # Convert request to ABTestConfig
        variants = [
            (v.variant_id, v.template_version, v.traffic_percentage, v.is_control)
            for v in request.variants
        ]

        config = ABTestConfig(
            template_id=request.template_id,
            name=request.name,
            description=request.description,
            variants=variants,
            success_metric=request.success_metric,
            min_sample_size=request.min_sample_size,
            target_improvement=request.target_improvement,
        )

        test = await ab_service.create_test(
            config=config,
            created_by="system",  # TODO: Get from auth context
        )

        # Convert to response
        variant_infos = []
        for v in test.variants:
            variant_infos.append(VariantInfo(
                variant_id=v.variant_id,
                template_version=v.template_version,
                traffic_percentage=v.traffic_percentage,
                is_control=v.is_control,
                impressions=v.impressions,
                successes=v.successes,
                success_rate=v.success_rate,
                avg_latency_ms=v.avg_latency_ms,
            ))

        return ABTestResponse(
            test_id=test.test_id,
            template_id=test.template_id,
            name=test.name,
            description=test.description,
            status=test.status.value,
            variants=variant_infos,
            success_metric=test.success_metric,
            min_sample_size=test.min_sample_size,
            target_improvement=test.target_improvement,
            created_at=test.created_at,
            started_at=test.started_at,
            ended_at=test.ended_at,
            winner_variant_id=test.winner_variant_id,
        )

    except PromptServiceError as e:
        http_status = _get_http_status_for_error(e)
        logger.error(
            "A/B test creation error",
            extra={
                "error": e.message,
                "error_code": e.error_code,
                "http_status": http_status,
                "trace_id": trace_id,
            }
        )
        raise HTTPException(
            status_code=http_status,
            detail=e.to_dict(),
        )


@router.get("/ab-tests", response_model=ABTestListResponse)
async def list_ab_tests(
    template_id: str = Query("", description="Filter by template ID"),
    status: str = Query("", description="Filter by status"),
) -> ABTestListResponse:
    """
    List all A/B tests.

    Returns a list of A/B tests with optional filtering.
    """
    from prompt_service.services.ab_testing import get_ab_testing_service

    trace_id = str(uuid.uuid4())
    set_trace_id(trace_id)

    logger.info(
        "List A/B tests request",
        extra={
            "template_id": template_id,
            "status": status,
            "trace_id": trace_id,
        }
    )

    ab_service = get_ab_testing_service()

    tests = await ab_service.list_tests(
        template_id=template_id or None,
        status=status or None,
    )

    # Convert to response format
    test_responses = []
    for test in tests:
        variant_infos = []
        for v in test.variants:
            variant_infos.append(VariantInfo(
                variant_id=v.variant_id,
                template_version=v.template_version,
                traffic_percentage=v.traffic_percentage,
                is_control=v.is_control,
                impressions=v.impressions,
                successes=v.successes,
                success_rate=v.success_rate,
                avg_latency_ms=v.avg_latency_ms,
            ))

        test_responses.append(ABTestResponse(
            test_id=test.test_id,
            template_id=test.template_id,
            name=test.name,
            description=test.description,
            status=test.status.value,
            variants=variant_infos,
            success_metric=test.success_metric,
            min_sample_size=test.min_sample_size,
            target_improvement=test.target_improvement,
            created_at=test.created_at,
            started_at=test.started_at,
            ended_at=test.ended_at,
            winner_variant_id=test.winner_variant_id,
        ))

    return ABTestListResponse(
        tests=test_responses,
        total=len(test_responses),
    )


@router.get("/ab-tests/{test_id}", response_model=ABTestResponse)
async def get_ab_test(test_id: str) -> ABTestResponse:
    """
    Get an A/B test by ID.

    Returns detailed information about a specific A/B test.
    """
    from prompt_service.services.ab_testing import get_ab_testing_service
    from prompt_service.core.exceptions import ABTestNotFoundError

    trace_id = str(uuid.uuid4())
    set_trace_id(trace_id)

    logger.info(
        "Get A/B test request",
        extra={
            "test_id": test_id,
            "trace_id": trace_id,
        }
    )

    try:
        ab_service = get_ab_testing_service()
        test = await ab_service.get_test(test_id)

        # Convert to response
        variant_infos = []
        for v in test.variants:
            variant_infos.append(VariantInfo(
                variant_id=v.variant_id,
                template_version=v.template_version,
                traffic_percentage=v.traffic_percentage,
                is_control=v.is_control,
                impressions=v.impressions,
                successes=v.successes,
                success_rate=v.success_rate,
                avg_latency_ms=v.avg_latency_ms,
            ))

        return ABTestResponse(
            test_id=test.test_id,
            template_id=test.template_id,
            name=test.name,
            description=test.description,
            status=test.status.value,
            variants=variant_infos,
            success_metric=test.success_metric,
            min_sample_size=test.min_sample_size,
            target_improvement=test.target_improvement,
            created_at=test.created_at,
            started_at=test.started_at,
            ended_at=test.ended_at,
            winner_variant_id=test.winner_variant_id,
        )

    except ABTestNotFoundError as e:
        logger.warning(
            "A/B test not found",
            extra={
                "test_id": test_id,
                "trace_id": trace_id,
                "error": e.message,
            }
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.to_dict(),
        )
    except PromptServiceError as e:
        http_status = _get_http_status_for_error(e)
        logger.error(
            "Get A/B test error",
            extra={
                "test_id": test_id,
                "error": e.message,
                "error_code": e.error_code,
                "http_status": http_status,
                "trace_id": trace_id,
            }
        )
        raise HTTPException(
            status_code=http_status,
            detail=e.to_dict(),
        )


@router.get("/ab-tests/{test_id}/results", response_model=ABTestResultsResponse)
async def get_ab_test_results(test_id: str) -> ABTestResultsResponse:
    """
    Get results for an A/B test.

    Returns calculated metrics for all variants in the test.
    """
    from prompt_service.services.ab_testing import get_ab_testing_service
    from prompt_service.core.exceptions import ABTestNotFoundError

    trace_id = str(uuid.uuid4())
    set_trace_id(trace_id)

    logger.info(
        "Get A/B test results request",
        extra={
            "test_id": test_id,
            "trace_id": trace_id,
        }
    )

    try:
        ab_service = get_ab_testing_service()
        test = await ab_service.get_test(test_id)
        metrics = await ab_service.get_results(test_id)

        # Convert to response
        metrics_result = {}
        for variant_id, variant_metrics in metrics.items():
            metrics_result[variant_id] = VariantMetricsResult(
                impressions=variant_metrics.impressions,
                successes=variant_metrics.successes,
                success_rate=variant_metrics.success_rate,
                avg_latency_ms=variant_metrics.avg_latency_ms,
                confidence_interval=variant_metrics.confidence_interval,
                is_significant=variant_metrics.is_significant,
                improvement_over_control=variant_metrics.improvement_over_control,
            )

        return ABTestResultsResponse(
            test_id=test.test_id,
            status=test.status.value,
            metrics=metrics_result,
            winner_variant_id=test.winner_variant_id,
        )

    except ABTestNotFoundError as e:
        logger.warning(
            "A/B test not found",
            extra={
                "test_id": test_id,
                "trace_id": trace_id,
                "error": e.message,
            }
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.to_dict(),
        )
    except PromptServiceError as e:
        http_status = _get_http_status_for_error(e)
        logger.error(
            "Get A/B test results error",
            extra={
                "test_id": test_id,
                "error": e.message,
                "error_code": e.error_code,
                "http_status": http_status,
                "trace_id": trace_id,
            }
        )
        raise HTTPException(
            status_code=http_status,
            detail=e.to_dict(),
        )


@router.post("/ab-tests/{test_id}/winner", response_model=SelectWinnerResponse)
async def select_ab_test_winner(
    test_id: str,
    request: SelectWinnerRequest,
) -> SelectWinnerResponse:
    """
    Select a winner for an A/B test.

    Selects the winning variant and completes the test.
    """
    from prompt_service.services.ab_testing import get_ab_testing_service
    from prompt_service.core.exceptions import ABTestNotFoundError

    trace_id = str(uuid.uuid4())
    set_trace_id(trace_id)

    logger.info(
        "Select A/B test winner request",
        extra={
            "test_id": test_id,
            "winner_variant_id": request.variant_id,
            "trace_id": trace_id,
        }
    )

    try:
        ab_service = get_ab_testing_service()
        test = await ab_service.select_winner(
            test_id=test_id,
            variant_id=request.variant_id,
            reason=request.reason,
        )

        return SelectWinnerResponse(
            test_id=test.test_id,
            winner_variant_id=test.winner_variant_id,
            status=test.status.value,
            ended_at=test.ended_at,
            trace_id=trace_id,
        )

    except ABTestNotFoundError as e:
        logger.warning(
            "A/B test not found",
            extra={
                "test_id": test_id,
                "trace_id": trace_id,
                "error": e.message,
            }
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.to_dict(),
        )
    except PromptServiceError as e:
        http_status = _get_http_status_for_error(e)
        logger.error(
            "Select A/B test winner error",
            extra={
                "test_id": test_id,
                "error": e.message,
                "error_code": e.error_code,
                "http_status": http_status,
                "trace_id": trace_id,
            }
        )
        raise HTTPException(
            status_code=http_status,
            detail=e.to_dict(),
        )


# ============================================================================
# Analytics Endpoints (US4)
# ============================================================================

@router.get("/analytics/prompts/{template_id}", response_model=AnalyticsResponse)
async def get_prompt_analytics(
    template_id: str,
    start_date: str = Query("", description="Start date (ISO format)"),
    end_date: str = Query("", description="End date (ISO format)"),
) -> AnalyticsResponse:
    """
    Get analytics for a prompt template.

    Returns aggregate metrics and insights for a template.
    """
    from prompt_service.services.trace_analysis import get_trace_analysis_service
    from datetime import datetime

    trace_id = str(uuid.uuid4())
    set_trace_id(trace_id)

    logger.info(
        "Get prompt analytics request",
        extra={
            "template_id": template_id,
            "start_date": start_date,
            "end_date": end_date,
            "trace_id": trace_id,
        }
    )

    # Parse dates if provided
    start_dt = None
    end_dt = None
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        except ValueError:
            pass
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        except ValueError:
            pass

    try:
        analysis_service = get_trace_analysis_service()

        # Get metrics
        metrics = analysis_service.aggregate_metrics(
            template_id=template_id,
            start_date=start_dt,
            end_date=end_dt,
        )

        # Get insights
        insights = analysis_service.get_insights(template_id=template_id)

        # Convert to response format
        metrics_summary = MetricsSummary(
            total_count=metrics.total_count,
            success_count=metrics.success_count,
            error_count=metrics.error_count,
            success_rate=metrics.success_rate,
            avg_latency_ms=metrics.avg_latency_ms,
            p50_latency_ms=metrics.p50_latency_ms,
            p95_latency_ms=metrics.p95_latency_ms,
            p99_latency_ms=metrics.p99_latency_ms,
            min_latency_ms=metrics.min_latency_ms,
            max_latency_ms=metrics.max_latency_ms,
            variant_metrics=metrics.variant_metrics,
        )

        insight_schemas = []
        for insight in insights:
            insight_schemas.append(TraceInsightSchema(
                insight_type=insight.insight_type,
                title=insight.title,
                description=insight.description,
                severity=insight.severity,
                data=insight.data,
                timestamp=insight.timestamp,
            ))

        return AnalyticsResponse(
            template_id=template_id,
            metrics=metrics_summary,
            insights=insight_schemas,
            period_start=start_dt,
            period_end=end_dt,
            trace_id=trace_id,
        )

    except PromptServiceError as e:
        http_status = _get_http_status_for_error(e)
        logger.error(
            "Get analytics error",
            extra={
                "template_id": template_id,
                "error": e.message,
                "error_code": e.error_code,
                "http_status": http_status,
                "trace_id": trace_id,
            }
        )
        raise HTTPException(
            status_code=http_status,
            detail=e.to_dict(),
        )


@router.get("/analytics/traces", response_model=TraceSearchResponse)
async def search_traces(
    template_id: str = Query("", description="Filter by template ID"),
    variant_id: str = Query("", description="Filter by variant ID"),
    start_date: str = Query("", description="Start date (ISO format)"),
    end_date: str = Query("", description="End date (ISO format)"),
    success_only: bool = Query(False, description="Only successful traces"),
    errors_only: bool = Query(False, description="Only failed traces"),
    min_latency: float = Query(None, description="Minimum latency"),
    max_latency: float = Query(None, description="Maximum latency"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=1000, description="Page size"),
) -> TraceSearchResponse:
    """
    Search and filter trace records.

    Returns a paginated list of traces matching the filter criteria.
    """
    from prompt_service.services.trace_analysis import get_trace_analysis_service
    from prompt_service.models.trace import TraceFilter
    from datetime import datetime

    trace_id = str(uuid.uuid4())
    set_trace_id(trace_id)

    # Validate required date range parameters
    if not start_date or not end_date:
        from prompt_service.core.exceptions import PromptValidationError
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "VALIDATION_ERROR",
                "message": "start_date and end_date query parameters are required",
                "details": {"validation_errors": ["start_date and end_date are required"]},
                "trace_id": trace_id,
            }
        )

    logger.info(
        "Search traces request",
        extra={
            "template_id": template_id,
            "variant_id": variant_id,
            "trace_id": trace_id,
        }
    )

    # Parse dates if provided
    start_dt = None
    end_dt = None
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        except ValueError:
            pass
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        except ValueError:
            pass

    try:
        analysis_service = get_trace_analysis_service()

        # Build filter
        filter_params = TraceFilter(
            template_id=template_id or None,
            variant_id=variant_id or None,
            start_date=start_dt,
            end_date=end_dt,
            success_only=success_only,
            errors_only=errors_only,
            min_latency=min_latency,
            max_latency=max_latency,
            offset=offset,
            limit=limit,
        )

        # Search traces
        traces = analysis_service.search_traces(filter_params)

        # Get total count (search without pagination)
        total_filter = TraceFilter(
            template_id=template_id or None,
            variant_id=variant_id or None,
            start_date=start_dt,
            end_date=end_dt,
            success_only=success_only,
            errors_only=errors_only,
            min_latency=min_latency,
            max_latency=max_latency,
            offset=0,
            limit=100000,  # Large limit for count
        )
        total = len(analysis_service.search_traces(total_filter))

        # Convert to response format
        trace_items = []
        for trace in traces:
            trace_items.append(TraceItem(
                trace_id=trace.trace_id,
                template_id=trace.template_id,
                template_version=trace.template_version,
                variant_id=trace.variant_id,
                timestamp=trace.timestamp,
                latency_ms=trace.latency_ms,
                total_latency_ms=trace.total_latency_ms,
                success=trace.success,
                input_variables=trace.input_variables,
                user_feedback=trace.user_feedback,
                user_rating=trace.user_rating,
            ))

        return TraceSearchResponse(
            traces=trace_items,
            total=total,
            offset=offset,
            limit=limit,
        )

    except PromptServiceError as e:
        http_status = _get_http_status_for_error(e)
        logger.error(
            "Search traces error",
            extra={
                "error": e.message,
                "error_code": e.error_code,
                "http_status": http_status,
                "trace_id": trace_id,
            }
        )
        raise HTTPException(
            status_code=http_status,
            detail=e.to_dict(),
        )


# ============================================================================
# Error Handlers
# ============================================================================

# Note: Exception handlers are registered at the app level in main.py


# ============================================================================
# Version Control Endpoints (US5)
# ============================================================================

@router.get("/prompts/{template_id}/versions", response_model=VersionHistoryResponse)
async def get_version_history(
    template_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
) -> VersionHistoryResponse:
    """
    Get version history for a prompt template.

    Returns a paginated list of all versions for the template.
    """
    from prompt_service.services.version_control import get_version_control_service

    trace_id = str(uuid.uuid4())
    set_trace_id(trace_id)

    logger.info(
        "Get version history request",
        extra={
            "template_id": template_id,
            "page": page,
            "trace_id": trace_id,
        }
    )

    try:
        version_service = get_version_control_service()

        # Get version history
        history = version_service.get_history(
            template_id=template_id,
            page=page,
            page_size=page_size,
        )

        # Convert to response format
        version_items = []
        for entry in history:
            version_items.append(VersionHistoryItem(
                template_id=entry.template_id,
                version=entry.version,
                change_description=entry.change_description,
                changed_by=entry.changed_by,
                created_at=entry.created_at,
                can_rollback=entry.can_rollback,
                rollback_count=entry.rollback_count,
            ))

        # Get total count
        all_history = version_service.get_history(template_id, page=1, page_size=10000)
        total = len(all_history)

        return VersionHistoryResponse(
            template_id=template_id,
            versions=version_items,
            total=total,
            page=page,
            page_size=page_size,
        )

    except PromptServiceError as e:
        http_status = _get_http_status_for_error(e)
        logger.error(
            "Get version history error",
            extra={
                "template_id": template_id,
                "error": e.message,
                "error_code": e.error_code,
                "http_status": http_status,
                "trace_id": trace_id,
            }
        )
        raise HTTPException(
            status_code=http_status,
            detail=e.to_dict(),
        )


@router.post("/prompts/{template_id}/rollback", response_model=RollbackResponse)
async def rollback_prompt(
    template_id: str,
    request: RollbackRequest,
) -> RollbackResponse:
    """
    Rollback a prompt template to a previous version.

    Creates a new version with the content from the target version.
    """
    from prompt_service.services.version_control import get_version_control_service
    from prompt_service.services.prompt_management import get_prompt_management_service

    trace_id = str(uuid.uuid4())
    set_trace_id(trace_id)

    logger.info(
        "Rollback prompt request",
        extra={
            "template_id": template_id,
            "target_version": request.target_version,
            "trace_id": trace_id,
        }
    )

    try:
        # Get current version before rollback
        management_service = get_prompt_management_service()
        current = await management_service.get(template_id)
        previous_version = current.version if current else 1

        version_service = get_version_control_service()

        # Perform rollback
        rolled_back_template = await version_service.rollback(
            template_id=template_id,
            target_version=request.target_version,
            rolled_back_by="system",  # TODO: Get from auth context
        )

        # Invalidate cache
        from prompt_service.middleware.cache import get_cache
        cache = get_cache()
        cache.invalidate(template_id)

        return RollbackResponse(
            template_id=template_id,
            previous_version=previous_version,
            new_version=rolled_back_template.version,
            target_version=request.target_version,
            rolled_back_at=rolled_back_template.updated_at,
            trace_id=trace_id,
        )

    except PromptNotFoundError as e:
        logger.warning(
            "Prompt not found for rollback",
            extra={
                "template_id": template_id,
                "trace_id": trace_id,
                "error": e.message,
            }
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.to_dict(),
        )
    except PromptValidationError as e:
        logger.warning(
            "Rollback validation failed",
            extra={
                "template_id": template_id,
                "errors": e.validation_errors,
                "trace_id": trace_id,
            }
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.to_dict(),
        )
    except PromptServiceError as e:
        http_status = _get_http_status_for_error(e)
        logger.error(
            "Rollback error",
            extra={
                "template_id": template_id,
                "error": e.message,
                "error_code": e.error_code,
                "http_status": http_status,
                "trace_id": trace_id,
            }
        )
        raise HTTPException(
            status_code=http_status,
            detail=e.to_dict(),
        )


# ============================================================================
# Additional endpoints will be added in subsequent user stories:
# - A/B Testing (US3): POST /ab-tests, GET /ab-tests, POST /ab-tests/{id}/winner
# - Analytics (US4): GET /analytics/prompts/{id}, GET /analytics/traces
# ============================================================================
