"""
API request and response schemas for Prompt Management Service.

This module defines all Pydantic models used for API request/response
validation. Schemas are organized by functional area.

Schema Groups:
- Health: Health check responses
- Error: Error response formats
- Prompt Retrieval: Prompt retrieve requests/responses (US1)
- Prompt Management: Prompt CRUD operations (US2)
- A/B Test: A/B test configuration and results (US3)
- Analytics: Trace analysis and metrics (US4)
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ============================================================================
# Health Schemas
# ============================================================================

class HealthResponse(BaseModel):
    """Health check response.

    Attributes:
        status: Overall health status (healthy, degraded, unhealthy)
        version: Service version
        components: Status of individual components
        uptime_ms: Service uptime in milliseconds
    """

    status: str = Field(..., description="Health status")
    version: str = Field(..., description="Service version")
    components: Dict[str, str] = Field(default_factory=dict, description="Component statuses")
    uptime_ms: float = Field(default=0.0, description="Uptime in milliseconds")


# ============================================================================
# Error Schemas
# ============================================================================

class ErrorResponse(BaseModel):
    """Error response format.

    Attributes:
        error: Machine-readable error code
        message: Human-readable error message
        details: Additional error context
        trace_id: Request trace identifier
    """

    error: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Error details")
    trace_id: Optional[str] = Field(default=None, description="Trace identifier")


# ============================================================================
# Prompt Retrieval Schemas (US1)
# ============================================================================

class RetrievedDoc(BaseModel):
    """A retrieved document for prompt inclusion.

    Attributes:
        id: Document identifier
        content: Document content
        metadata: Additional metadata
    """

    id: str = Field(..., description="Document ID")
    content: str = Field(..., description="Document content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata")


class PromptRetrieveOptions(BaseModel):
    """Options for prompt retrieval.

    Attributes:
        version_id: Specific version to retrieve (optional)
        include_metadata: Include version metadata in response
    """

    version_id: Optional[int] = Field(default=None, description="Specific version")
    include_metadata: bool = Field(default=False, description="Include metadata")


class PromptRetrieveRequest(BaseModel):
    """Request for prompt retrieval.

    Attributes:
        variables: Variable values for interpolation
        context: Additional context (user_id, session_id, etc.)
        retrieved_docs: Retrieved documents for inclusion
        options: Retrieval options
    """

    variables: Dict[str, Any] = Field(default_factory=dict, description="Variable values")
    context: Dict[str, Any] = Field(default_factory=dict, description="Runtime context")
    retrieved_docs: List[RetrievedDoc] = Field(
        default_factory=list,
        description="Retrieved documents"
    )
    options: PromptRetrieveOptions = Field(
        default_factory=PromptRetrieveOptions,
        description="Retrieval options"
    )


class Section(BaseModel):
    """A prompt section in the response.

    Attributes:
        name: Section label
        content: Section content
    """

    name: str = Field(..., description="Section name")
    content: str = Field(..., description="Section content")


class PromptRetrieveResponse(BaseModel):
    """Response from prompt retrieval.

    Attributes:
        content: Fully rendered prompt text
        template_id: Template identifier
        version_id: Version that was used
        variant_id: A/B test variant ID (if applicable)
        sections: Rendered sections (if include_metadata)
        metadata: Version metadata
        trace_id: Request trace identifier
        from_cache: Whether response was cached
    """

    content: str = Field(..., description="Rendered prompt")
    template_id: str = Field(..., description="Template ID")
    version_id: int = Field(..., description="Version used")
    variant_id: Optional[str] = Field(default=None, description="Variant ID if A/B test")
    sections: Optional[List[Section]] = Field(default=None, description="Rendered sections")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Version metadata")
    trace_id: str = Field(..., description="Trace identifier")
    from_cache: bool = Field(default=False, description="From cache")


# ============================================================================
# Prompt Management Schemas (US2)
# ============================================================================

class StructuredSectionSchema(BaseModel):
    """Structured section for API requests/responses.

    Attributes:
        name: Section name
        content: Section content
        is_required: Whether section is required
        order: Assembly order
    """

    name: str = Field(..., description="Section name")
    content: str = Field(..., description="Section content")
    is_required: bool = Field(default=True, description="Whether required")
    order: int = Field(default=0, description="Assembly order")


class VariableDefSchema(BaseModel):
    """Variable definition for API requests/responses.

    Attributes:
        name: Variable name
        description: Variable description
        type: Variable type
        default_value: Default value
        is_required: Whether value is required
    """

    name: str = Field(..., description="Variable name")
    description: str = Field(..., description="Variable description")
    type: str = Field(default="string", description="Variable type")
    default_value: Optional[Any] = Field(default=None, description="Default value")
    is_required: bool = Field(default=True, description="Whether required")


class PromptCreateRequest(BaseModel):
    """Request to create a new prompt template.

    Attributes:
        template_id: Template identifier
        name: Human-readable name
        description: Purpose and usage
        sections: Ordered prompt sections
        variables: Variable definitions
        tags: Categorization tags
        is_published: Whether to publish immediately
    """

    template_id: str = Field(..., description="Template identifier")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="Purpose and usage")
    sections: List[StructuredSectionSchema] = Field(..., description="Prompt sections")
    variables: Dict[str, VariableDefSchema] = Field(
        default_factory=dict,
        description="Variable definitions"
    )
    tags: List[str] = Field(default_factory=list, description="Tags")
    is_published: bool = Field(default=False, description="Publish immediately")


class PromptUpdateRequest(BaseModel):
    """Request to update an existing prompt template.

    Attributes:
        name: Human-readable name
        description: Purpose and usage
        sections: Ordered prompt sections
        variables: Variable definitions
        tags: Categorization tags
        change_description: Description of changes
    """

    name: Optional[str] = Field(default=None, description="Human-readable name")
    description: Optional[str] = Field(default=None, description="Purpose and usage")
    sections: Optional[List[StructuredSectionSchema]] = Field(
        default=None,
        description="Prompt sections"
    )
    variables: Optional[Dict[str, VariableDefSchema]] = Field(
        default=None,
        description="Variable definitions"
    )
    tags: Optional[List[str]] = Field(default=None, description="Tags")
    change_description: str = Field(..., description="Change description")


class PromptInfoResponse(BaseModel):
    """Response with prompt template information.

    Attributes:
        template_id: Template identifier
        name: Human-readable name
        description: Purpose and usage
        version: Current version
        sections: Ordered prompt sections
        variables: Variable definitions
        tags: Categorization tags
        is_active: Whether this is the active version
        is_published: Whether published
        created_at: Creation timestamp
        updated_at: Last update timestamp
        created_by: Creator user ID
    """

    template_id: str = Field(..., description="Template identifier")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="Purpose and usage")
    version: int = Field(..., description="Current version")
    sections: List[StructuredSectionSchema] = Field(..., description="Prompt sections")
    variables: Dict[str, VariableDefSchema] = Field(..., description="Variable definitions")
    tags: List[str] = Field(..., description="Tags")
    is_active: bool = Field(..., description="Is active version")
    is_published: bool = Field(..., description="Is published")
    created_at: datetime = Field(..., description="Creation time")
    updated_at: datetime = Field(..., description="Last update")
    created_by: str = Field(..., description="Creator")


class PromptListResponse(BaseModel):
    """Response with list of prompt templates.

    Attributes:
        prompts: List of prompt templates
        total: Total count
        page: Current page number
        page_size: Page size
    """

    prompts: List[PromptInfoResponse] = Field(..., description="Prompt list")
    total: int = Field(..., description="Total count")
    page: int = Field(..., description="Current page")
    page_size: int = Field(..., description="Page size")


class PromptCreateResponse(BaseModel):
    """Response from prompt creation.

    Attributes:
        template_id: Template identifier
        version: Created version
        is_active: Whether active
        created_at: Creation timestamp
        trace_id: Trace identifier
    """

    template_id: str = Field(..., description="Template identifier")
    version: int = Field(..., description="Created version")
    is_active: bool = Field(..., description="Is active")
    created_at: datetime = Field(..., description="Creation time")
    trace_id: str = Field(..., description="Trace identifier")


class PromptUpdateResponse(BaseModel):
    """Response from prompt update.

    Attributes:
        template_id: Template identifier
        version: New version
        previous_version: Previous version
        is_active: Whether active
        updated_at: Update timestamp
        trace_id: Trace identifier
    """

    template_id: str = Field(..., description="Template identifier")
    version: int = Field(..., description="New version")
    previous_version: int = Field(..., description="Previous version")
    is_active: bool = Field(..., description="Is active")
    updated_at: datetime = Field(..., description="Update time")
    trace_id: str = Field(..., description="Trace identifier")


class PromptDeleteResponse(BaseModel):
    """Response from prompt deletion.

    Attributes:
        template_id: Template identifier
        deleted: Whether deleted
        trace_id: Trace identifier
    """

    template_id: str = Field(..., description="Template identifier")
    deleted: bool = Field(..., description="Deleted")
    trace_id: str = Field(..., description="Trace identifier")


# ============================================================================
# Common Response Wrapper
# ============================================================================

class TimestampedResponse(BaseModel):
    """Base response with timestamp.

    Attributes:
        timestamp: Response timestamp
    """

    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response time")


# ============================================================================
# A/B Testing Schemas (US3)
# ============================================================================

class VariantConfig(BaseModel):
    """Configuration for a single variant in A/B test.

    Attributes:
        variant_id: Unique variant identifier
        template_version: Template version to use
        traffic_percentage: Traffic percentage (0-100)
        is_control: Whether this is the control variant
    """

    variant_id: str = Field(..., description="Variant identifier")
    template_version: int = Field(..., ge=1, description="Template version")
    traffic_percentage: float = Field(..., ge=0, le=100, description="Traffic percentage")
    is_control: bool = Field(default=False, description="Is control variant")


class ABTestCreateRequest(BaseModel):
    """Request to create a new A/B test.

    Attributes:
        template_id: Template to test
        name: Test name
        description: Test description and hypothesis
        variants: Variant configurations
        success_metric: Metric to optimize (success_rate, latency)
        min_sample_size: Minimum samples for significance
        target_improvement: Target improvement threshold (5% = 0.05)
    """

    template_id: str = Field(..., description="Template to test")
    name: str = Field(..., description="Test name")
    description: str = Field(..., description="Test description")
    variants: List[VariantConfig] = Field(
        ...,
        min_items=2,
        max_items=5,
        description="Test variants"
    )
    success_metric: str = Field(default="success_rate", description="Success metric")
    min_sample_size: int = Field(default=1000, ge=1, description="Min sample size")
    target_improvement: float = Field(default=0.05, ge=0, description="Target improvement")


class VariantInfo(BaseModel):
    """Information about a test variant.

    Attributes:
        variant_id: Variant identifier
        template_version: Template version used
        traffic_percentage: Allocated traffic percentage
        is_control: Whether this is the control variant
        impressions: Number of impressions
        successes: Number of successful outcomes
        success_rate: Calculated success rate
        avg_latency_ms: Average latency
    """

    variant_id: str = Field(..., description="Variant identifier")
    template_version: int = Field(..., description="Template version")
    traffic_percentage: float = Field(..., description="Traffic percentage")
    is_control: bool = Field(..., description="Is control variant")
    impressions: int = Field(default=0, ge=0, description="Impressions")
    successes: int = Field(default=0, ge=0, description="Successes")
    success_rate: float = Field(default=0, ge=0, le=1, description="Success rate")
    avg_latency_ms: float = Field(default=0, ge=0, description="Average latency")


class ABTestResponse(BaseModel):
    """Response with A/B test information.

    Attributes:
        test_id: Test identifier
        template_id: Template being tested
        name: Test name
        description: Test description
        status: Test status
        variants: Test variants
        success_metric: Metric being optimized
        min_sample_size: Minimum sample size
        target_improvement: Target improvement
        created_at: Creation time
        started_at: Start time
        ended_at: End time
        winner_variant_id: Winning variant (if completed)
    """

    test_id: str = Field(..., description="Test identifier")
    template_id: str = Field(..., description="Template ID")
    name: str = Field(..., description="Test name")
    description: str = Field(..., description="Test description")
    status: str = Field(..., description="Test status")
    variants: List[VariantInfo] = Field(..., description="Test variants")
    success_metric: str = Field(..., description="Success metric")
    min_sample_size: int = Field(..., description="Min sample size")
    target_improvement: float = Field(..., description="Target improvement")
    created_at: datetime = Field(..., description="Created at")
    started_at: Optional[datetime] = Field(default=None, description="Started at")
    ended_at: Optional[datetime] = Field(default=None, description="Ended at")
    winner_variant_id: Optional[str] = Field(default=None, description="Winner variant ID")


class ABTestListResponse(BaseModel):
    """Response with list of A/B tests.

    Attributes:
        tests: List of A/B tests
        total: Total count
    """

    tests: List[ABTestResponse] = Field(..., description="Test list")
    total: int = Field(..., description="Total count")


class VariantMetricsResult(BaseModel):
    """Metrics for a variant.

    Attributes:
        impressions: Number of impressions
        successes: Number of successes
        success_rate: Success rate
        avg_latency_ms: Average latency
        confidence_interval: 95% confidence interval
        is_significant: Statistically significant
        improvement_over_control: Improvement vs control
    """

    impressions: int = Field(..., description="Impressions")
    successes: int = Field(..., description="Successes")
    success_rate: float = Field(..., description="Success rate")
    avg_latency_ms: float = Field(..., description="Average latency")
    confidence_interval: Optional[List[float]] = Field(default=None, description="95% CI")
    is_significant: bool = Field(default=False, description="Statistically significant")
    improvement_over_control: Optional[float] = Field(default=None, description="Improvement vs control")


class ABTestResultsResponse(BaseModel):
    """Response with A/B test results.

    Attributes:
        test_id: Test identifier
        status: Test status
        metrics: Metrics per variant
        winner_variant_id: Current winner (if any)
    """

    test_id: str = Field(..., description="Test identifier")
    status: str = Field(..., description="Test status")
    metrics: Dict[str, VariantMetricsResult] = Field(..., description="Variant metrics")
    winner_variant_id: Optional[str] = Field(default=None, description="Winner variant ID")


class SelectWinnerRequest(BaseModel):
    """Request to select a winner for an A/B test.

    Attributes:
        variant_id: Winning variant ID
        reason: Reason for selection
    """

    variant_id: str = Field(..., description="Winning variant ID")
    reason: str = Field(default="", description="Reason for selection")


class SelectWinnerResponse(BaseModel):
    """Response from winner selection.

    Attributes:
        test_id: Test identifier
        winner_variant_id: Selected winner
        status: New test status
        ended_at: End time
        trace_id: Trace identifier
    """

    test_id: str = Field(..., description="Test identifier")
    winner_variant_id: str = Field(..., description="Winner variant ID")
    status: str = Field(..., description="Test status")
    ended_at: datetime = Field(..., description="Ended at")
    trace_id: str = Field(..., description="Trace identifier")


# ============================================================================
# Analytics Schemas (US4)
# ============================================================================

class TraceItem(BaseModel):
    """A single trace record in API responses.

    Attributes:
        trace_id: Trace identifier
        template_id: Template used
        template_version: Version used
        variant_id: Variant ID if A/B test
        timestamp: Execution timestamp
        latency_ms: Latency in milliseconds
        total_latency_ms: Total latency
        success: Success status
        input_variables: Input variables
        user_feedback: User feedback
        user_rating: User rating
    """

    trace_id: str = Field(..., description="Trace ID")
    template_id: str = Field(..., description="Template ID")
    template_version: int = Field(..., description="Template version")
    variant_id: Optional[str] = Field(default=None, description="Variant ID")
    timestamp: datetime = Field(..., description="Timestamp")
    latency_ms: float = Field(..., description="Latency")
    total_latency_ms: float = Field(default=0.0, description="Total latency")
    success: bool = Field(..., description="Success")
    input_variables: Dict[str, Any] = Field(default_factory=dict, description="Input variables")
    user_feedback: Optional[str] = Field(default=None, description="User feedback")
    user_rating: Optional[int] = Field(default=None, description="User rating")


class MetricsSummary(BaseModel):
    """Summary metrics for a prompt template.

    Attributes:
        total_count: Total executions
        success_count: Successful executions
        error_count: Failed executions
        success_rate: Success rate
        avg_latency_ms: Average latency
        p50_latency_ms: P50 latency
        p95_latency_ms: P95 latency
        p99_latency_ms: P99 latency
        min_latency_ms: Minimum latency
        max_latency_ms: Maximum latency
        variant_metrics: Metrics per variant
    """

    total_count: int = Field(..., ge=0, description="Total count")
    success_count: int = Field(..., ge=0, description="Success count")
    error_count: int = Field(..., ge=0, description="Error count")
    success_rate: float = Field(..., ge=0, le=1, description="Success rate")
    avg_latency_ms: float = Field(..., ge=0, description="Average latency")
    p50_latency_ms: float = Field(default=0.0, ge=0, description="P50 latency")
    p95_latency_ms: float = Field(default=0.0, ge=0, description="P95 latency")
    p99_latency_ms: float = Field(default=0.0, ge=0, description="P99 latency")
    min_latency_ms: float = Field(default=0.0, ge=0, description="Min latency")
    max_latency_ms: float = Field(default=0.0, ge=0, description="Max latency")
    variant_metrics: Optional[Dict[str, Dict[str, Any]]] = Field(
        default=None,
        description="Metrics per variant"
    )


class TraceInsightSchema(BaseModel):
    """An insight from trace analysis.

    Attributes:
        insight_type: Type of insight
        title: Insight title
        description: Insight description
        severity: Severity level
        data: Supporting data
        timestamp: When generated
    """

    insight_type: str = Field(..., description="Insight type")
    title: str = Field(..., description="Title")
    description: str = Field(..., description="Description")
    severity: str = Field(default="info", description="Severity")
    data: Dict[str, Any] = Field(default_factory=dict, description="Supporting data")
    timestamp: datetime = Field(..., description="Timestamp")


class AnalyticsResponse(BaseModel):
    """Response from analytics endpoint.

    Attributes:
        template_id: Template identifier
        metrics: Aggregate metrics
        insights: Generated insights
        period_start: Start of analysis period
        period_end: End of analysis period
        trace_id: Request trace identifier
    """

    template_id: str = Field(..., description="Template ID")
    metrics: MetricsSummary = Field(..., description="Metrics summary")
    insights: List[TraceInsightSchema] = Field(default_factory=list, description="Insights")
    period_start: Optional[datetime] = Field(default=None, description="Period start")
    period_end: Optional[datetime] = Field(default=None, description="Period end")
    trace_id: str = Field(..., description="Trace ID")


class TraceSearchResponse(BaseModel):
    """Response from trace search endpoint.

    Attributes:
        traces: List of traces
        total: Total count
        offset: Pagination offset
        limit: Page size
    """

    traces: List[TraceItem] = Field(..., description="Traces")
    total: int = Field(..., description="Total count")
    offset: int = Field(..., description="Offset")
    limit: int = Field(..., description="Limit")


# ============================================================================
# Version Control Schemas (US5)
# ============================================================================

class VersionHistoryItem(BaseModel):
    """A version in the template history.

    Attributes:
        template_id: Template identifier
        version: Version number
        change_description: Description of changes
        changed_by: User who made the change
        created_at: When version was created
        can_rollback: Whether this version can be restored
        rollback_count: Number of times rolled back to this version
    """

    template_id: str = Field(..., description="Template ID")
    version: int = Field(..., description="Version number")
    change_description: str = Field(..., description="Change description")
    changed_by: str = Field(..., description="User who made the change")
    created_at: datetime = Field(..., description="Created at")
    can_rollback: bool = Field(default=True, description="Can rollback")
    rollback_count: int = Field(default=0, ge=0, description="Rollback count")


class VersionHistoryResponse(BaseModel):
    """Response with version history.

    Attributes:
        template_id: Template identifier
        versions: List of version history entries
        total: Total number of versions
        page: Current page number
        page_size: Page size
    """

    template_id: str = Field(..., description="Template ID")
    versions: List[VersionHistoryItem] = Field(..., description="Version history")
    total: int = Field(..., description="Total count")
    page: int = Field(..., description="Page number")
    page_size: int = Field(..., description="Page size")


class RollbackRequest(BaseModel):
    """Request to rollback to a previous version.

    Attributes:
        target_version: Version to rollback to
        reason: Reason for the rollback
    """

    target_version: int = Field(..., ge=1, description="Target version")
    reason: str = Field(default="", description="Reason for rollback")


class RollbackResponse(BaseModel):
    """Response from rollback operation.

    Attributes:
        template_id: Template identifier
        previous_version: Version before rollback
        new_version: New version created
        target_version: Version that was restored
        rolled_back_at: When rollback was performed
        trace_id: Trace identifier
    """

    template_id: str = Field(..., description="Template ID")
    previous_version: int = Field(..., description="Previous version")
    new_version: int = Field(..., description="New version")
    target_version: int = Field(..., description="Target version")
    rolled_back_at: datetime = Field(..., description="Rolled back at")
    trace_id: str = Field(..., description="Trace ID")
