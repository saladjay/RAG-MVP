"""
A/B Testing data models for Prompt Management Service.

This module defines the data models for A/B testing prompt variants:
- ABTest: Configuration for comparing prompt variants
- PromptVariant: A specific version in an A/B test
- ABTestStatus: Enum for test status

The models support:
- Deterministic hash-based variant assignment
- Traffic split configuration
- Metrics tracking per variant
- Winner selection and test completion
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ABTestStatus(str, Enum):
    """Status of an A/B test.

    Values:
        DRAFT: Test is being configured
        RUNNING: Test is active and routing traffic
        PAUSED: Test is temporarily paused
        COMPLETED: Test finished with winner selected
        ARCHIVED: Test is no longer relevant
    """

    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class PromptVariant(BaseModel):
    """A specific version of a prompt used in A/B testing.

    Attributes:
        variant_id: Unique variant identifier (e.g., "variant_a")
        template_id: Source prompt template identifier
        template_version: Specific template version to use
        traffic_percentage: Traffic percentage (0-100)
        is_control: Whether this is the baseline/control variant
        impressions: Number of times this variant was shown
        successes: Number of successful outcomes
        total_latency_ms: Cumulative latency for averaging
        created_at: Creation timestamp
    """

    variant_id: str = Field(..., description="Variant ID")
    template_id: str = Field(..., description="Template ID")
    template_version: int = Field(..., description="Template version")
    traffic_percentage: float = Field(
        ...,
        ge=0,
        le=100,
        description="Traffic percentage"
    )
    is_control: bool = Field(default=False, description="Is control variant")
    impressions: int = Field(default=0, ge=0, description="Impressions")
    successes: int = Field(default=0, ge=0, description="Successful outcomes")
    total_latency_ms: float = Field(default=0.0, ge=0, description="Total latency")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Created at")

    @property
    def success_rate(self) -> float:
        """Calculate success rate for this variant.

        Returns:
            Success rate (0-1) or 0 if no impressions
        """
        if self.impressions == 0:
            return 0.0
        return self.successes / self.impressions

    @property
    def avg_latency_ms(self) -> float:
        """Calculate average latency per request.

        Returns:
            Average latency in milliseconds
        """
        if self.impressions == 0:
            return 0.0
        return self.total_latency_ms / self.impressions


class VariantMetrics(BaseModel):
    """Metrics for an A/B test variant.

    Attributes:
        impressions: Number of times shown
        successes: Number of successful outcomes
        success_rate: Success rate (0-1)
        avg_latency_ms: Average latency
        confidence_interval: 95% confidence interval if available
        is_significant: Whether results are statistically significant
        improvement_over_control: Improvement vs control variant
    """

    impressions: int = Field(..., ge=0, description="Impressions")
    successes: int = Field(..., ge=0, description="Successes")
    success_rate: float = Field(..., ge=0, le=1, description="Success rate")
    avg_latency_ms: float = Field(..., ge=0, description="Average latency")
    confidence_interval: Optional[List[float]] = Field(
        default=None,
        description="95% CI"
    )
    is_significant: bool = Field(default=False, description="Statistically significant")
    improvement_over_control: Optional[float] = Field(
        default=None,
        description="Improvement vs control"
    )


class ABTest(BaseModel):
    """Configuration for an A/B test comparing prompt variants.

    Attributes:
        test_id: Unique test identifier
        template_id: Prompt template being tested
        name: Human-readable test name
        description: Test hypothesis and goals
        variants: Competing prompt variants
        status: Current test status
        success_metric: Metric to optimize (success_rate, latency)
        min_sample_size: Minimum samples for significance
        target_improvement: Target improvement (5% = 0.05)
        created_at: Creation timestamp
        started_at: When test started
        ended_at: When test ended
        winner_variant_id: Winning variant (if completed)
        results: Additional results data
    """

    test_id: str = Field(..., description="Test ID")
    template_id: str = Field(..., description="Template ID")
    name: str = Field(..., description="Test name")
    description: str = Field(..., description="Test description")
    variants: List[PromptVariant] = Field(..., description="Test variants")
    status: ABTestStatus = Field(default=ABTestStatus.DRAFT, description="Test status")
    success_metric: str = Field(default="success_rate", description="Success metric")
    min_sample_size: int = Field(default=1000, ge=1, description="Min sample size")
    target_improvement: float = Field(default=0.05, ge=0, description="Target improvement")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Created at")
    started_at: Optional[datetime] = Field(default=None, description="Started at")
    ended_at: Optional[datetime] = Field(default=None, description="Ended at")
    winner_variant_id: Optional[str] = Field(default=None, description="Winner variant ID")
    results: Dict[str, Any] = Field(default_factory=dict, description="Results data")

    def get_variant(self, variant_id: str) -> Optional[PromptVariant]:
        """Get a variant by ID.

        Args:
            variant_id: Variant identifier

        Returns:
            Prompt variant or None if not found
        """
        for variant in self.variants:
            if variant.variant_id == variant_id:
                return variant
        return None

    def get_control_variant(self) -> Optional[PromptVariant]:
        """Get the control (baseline) variant.

        Returns:
            Control variant or None if not found
        """
        for variant in self.variants:
            if variant.is_control:
                return variant
        return None

    def validate_traffic_split(self) -> bool:
        """Validate that traffic percentages sum to 100.

        Returns:
            True if valid, False otherwise
        """
        total = sum(v.traffic_percentage for v in self.variants)
        return abs(total - 100.0) < 0.01  # Allow small floating point errors

    def calculate_metrics(self) -> Dict[str, VariantMetrics]:
        """Calculate metrics for all variants.

        Returns:
            Dictionary mapping variant_id to metrics
        """
        metrics = {}

        control = self.get_control_variant()
        control_rate = control.success_rate if control else 0.5

        for variant in self.variants:
            improvement = None
            if control and not variant.is_control:
                improvement = variant.success_rate - control_rate

            metrics[variant.variant_id] = VariantMetrics(
                impressions=variant.impressions,
                successes=variant.successes,
                success_rate=variant.success_rate,
                avg_latency_ms=variant.avg_latency_ms,
                # TODO: Calculate actual confidence interval
                is_significant=variant.impressions >= self.min_sample_size,
                improvement_over_control=improvement,
            )

        return metrics


@dataclass
class ABTestAssignment:
    """Result of an A/B test variant assignment.

    Attributes:
        test_id: The A/B test identifier
        variant_id: Assigned variant identifier
        template_id: Template being tested
        template_version: Version of the variant
        assigned_at: When assignment was made
    """

    test_id: str
    variant_id: str
    template_id: str
    template_version: int
    assigned_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ABTestConfig:
    """Configuration for creating a new A/B test.

    Attributes:
        template_id: Template to test
        name: Test name
        description: Test description
        variants: List of (variant_id, template_version, traffic%, is_control)
        success_metric: Metric to optimize
        min_sample_size: Minimum samples for significance
        target_improvement: Target improvement threshold
    """

    template_id: str
    name: str
    description: str
    variants: List[tuple[str, int, float, bool]]  # (variant_id, version, traffic%, is_control)
    success_metric: str = "success_rate"
    min_sample_size: int = 1000
    target_improvement: float = 0.05
