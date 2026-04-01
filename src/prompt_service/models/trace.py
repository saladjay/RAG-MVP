"""
Trace data models for Prompt Management Service.

This module defines the data models for tracing prompt execution:
- TraceRecord: Execution data linking prompt usage to outcomes
- EvaluationMetrics: Aggregated metrics for analytics
- TraceFilter: Filter options for trace searches

The models support:
- Recording individual prompt executions
- Aggregating metrics for analytics
- Filtering and searching traces
- Computing percentiles and error rates
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TraceRecord(BaseModel):
    """A single prompt execution trace.

    Links prompt version to input, output, and metrics.

    Attributes:
        trace_id: Unique trace identifier
        template_id: Prompt template used
        template_version: Specific version
        variant_id: Variant if A/B test
        input_variables: Variables provided
        context: Runtime context (user_id, session_id, etc.)
        retrieved_docs: Documents included in prompt
        rendered_prompt: Final assembled prompt
        model_output: LLM response (if provided)
        output_metadata: Additional output metadata
        latency_ms: Prompt retrieval latency
        total_latency_ms: End-to-end latency
        success: Whether outcome was successful
        user_feedback: User feedback (if provided)
        user_rating: User rating 1-5 scale
        timestamp: Execution timestamp
    """

    trace_id: str = Field(..., description="Trace ID")
    template_id: str = Field(..., description="Template ID")
    template_version: int = Field(..., description="Template version")
    variant_id: Optional[str] = Field(default=None, description="Variant ID if A/B test")
    input_variables: Dict[str, Any] = Field(default_factory=dict, description="Input variables")
    context: Dict[str, Any] = Field(default_factory=dict, description="Runtime context")
    retrieved_docs: List[Dict[str, Any]] = Field(default_factory=list, description="Retrieved docs")
    rendered_prompt: str = Field(..., description="Rendered prompt")
    model_output: Optional[str] = Field(default=None, description="LLM output")
    output_metadata: Dict[str, Any] = Field(default_factory=dict, description="Output metadata")
    latency_ms: float = Field(default=0.0, ge=0, description="Prompt latency")
    total_latency_ms: float = Field(default=0.0, ge=0, description="Total latency")
    success: bool = Field(default=True, description="Success status")
    user_feedback: Optional[str] = Field(default=None, description="User feedback")
    user_rating: Optional[int] = Field(default=None, ge=1, le=5, description="User rating")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Timestamp")


class EvaluationMetrics(BaseModel):
    """Aggregated metrics for prompt performance.

    Attributes:
        total_count: Total number of executions
        success_count: Number of successful executions
        error_count: Number of failed executions
        success_rate: Success rate (0-1)
        avg_latency_ms: Average latency
        p50_latency_ms: 50th percentile latency
        p95_latency_ms: 95th percentile latency
        p99_latency_ms: 99th percentile latency
        min_latency_ms: Minimum latency
        max_latency_ms: Maximum latency
        variant_metrics: Metrics per variant (if A/B test)
        error_patterns: Common error patterns
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
    error_patterns: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Error patterns"
    )


@dataclass
class TraceFilter:
    """Filter options for trace searches.

    Attributes:
        template_id: Filter by template ID
        variant_id: Filter by variant ID
        start_date: Start of date range
        end_date: End of date range
        success_only: Only successful traces
        errors_only: Only failed traces
        min_latency: Minimum latency filter
        max_latency: Maximum latency filter
        limit: Maximum results to return
        offset: Pagination offset
    """

    template_id: Optional[str] = None
    variant_id: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    success_only: bool = False
    errors_only: bool = False
    min_latency: Optional[float] = None
    max_latency: Optional[float] = None
    limit: int = 100
    offset: int = 0


@dataclass
class TraceInsight:
    """Insight derived from trace analysis.

    Attributes:
        insight_type: Type of insight (performance, error, usage)
        title: Insight title
        description: Insight description
        severity: Severity level (info, warning, critical)
        data: Supporting data
        timestamp: When insight was generated
    """

    insight_type: str
    title: str
    description: str
    severity: str = "info"
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
