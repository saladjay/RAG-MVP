"""
A/B Testing Service for prompt variant comparison.

This service handles:
- Creating and managing A/B tests
- Deterministic variant assignment based on user_id hash
- Metrics tracking for each variant
- Winner selection and test completion

The service uses a deterministic hash-based routing algorithm to ensure
consistent user assignment to variants across sessions.
"""

import hashlib
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from prompt_service.config import get_config
from prompt_service.core.exceptions import ABTestNotFoundError, ABTestValidationError
from prompt_service.core.logger import get_logger
from prompt_service.middleware.cache import get_cache
from prompt_service.models.ab_test import (
    ABTest,
    ABTestAssignment,
    ABTestConfig,
    ABTestStatus,
    PromptVariant,
    VariantMetrics,
)

logger = get_logger(__name__)


class ABTestingService:
    """Service for A/B testing prompt variants.

    This service manages A/B tests for prompt templates, including:
    - Test creation and configuration
    - Deterministic variant routing (hash-based)
    - Metrics tracking and aggregation
    - Winner selection

    Attributes:
        _cache: Storage for active tests
        _config: Service configuration
    """

    def __init__(self):
        """Initialize the A/B testing service."""
        self._config = get_config()
        self._cache = {}  # In-memory storage for active tests

        # In production, this would use a persistent store
        # For now, we'll use in-memory dict with test_id as key

        logger.info("ABTestingService initialized")

    async def create_test(
        self,
        config: ABTestConfig,
        created_by: str = "system",
    ) -> ABTest:
        """Create a new A/B test.

        Args:
            config: Test configuration
            created_by: Creator user ID

        Returns:
            Created A/B test

        Raises:
            ABTestValidationError: If validation fails
        """
        # Validate configuration
        self._validate_test_config(config)

        # Generate test_id
        test_id = f"ab_test_{uuid.uuid4().hex[:8]}"

        # Build variants
        variants = []
        for variant_id, version, traffic, is_control in config.variants:
            variants.append(PromptVariant(
                variant_id=variant_id,
                template_id=config.template_id,
                template_version=version,
                traffic_percentage=traffic,
                is_control=is_control,
            ))

        # Create test
        test = ABTest(
            test_id=test_id,
            template_id=config.template_id,
            name=config.name,
            description=config.description,
            variants=variants,
            status=ABTestStatus.DRAFT,
            success_metric=config.success_metric,
            min_sample_size=config.min_sample_size,
            target_improvement=config.target_improvement,
        )

        # Store test
        self._cache[test_id] = test

        logger.info(
            "A/B test created",
            extra={
                "test_id": test_id,
                "template_id": config.template_id,
                "variant_count": len(variants),
                "created_by": created_by,
            }
        )

        return test

    async def start_test(
        self,
        test_id: str,
    ) -> ABTest:
        """Start an A/B test (begins routing traffic).

        Args:
            test_id: Test identifier

        Returns:
            Updated test with RUNNING status

        Raises:
            ABTestNotFoundError: If test not found
        """
        test = self._get_test(test_id)

        if test.status != ABTestStatus.DRAFT:
            raise ABTestValidationError(
                message=f"Cannot start test with status: {test.status.value}",
                validation_errors=["Test must be in DRAFT status"],
                trace_id=str(uuid.uuid4()),
            )

        test.status = ABTestStatus.RUNNING
        test.started_at = datetime.utcnow()

        logger.info(
            "A/B test started",
            extra={
                "test_id": test_id,
                "template_id": test.template_id,
            }
        )

        return test

    async def pause_test(
        self,
        test_id: str,
    ) -> ABTest:
        """Pause an A/B test (stops routing traffic).

        Args:
            test_id: Test identifier

        Returns:
            Updated test with PAUSED status

        Raises:
            ABTestNotFoundError: If test not found
        """
        test = self._get_test(test_id)

        if test.status != ABTestStatus.RUNNING:
            raise ABTestValidationError(
                message=f"Cannot pause test with status: {test.status.value}",
                validation_errors=["Test must be RUNNING"],
                trace_id=str(uuid.uuid4()),
            )

        test.status = ABTestStatus.PAUSED

        logger.info(
            "A/B test paused",
            extra={"test_id": test_id}
        )

        return test

    async def resume_test(
        self,
        test_id: str,
    ) -> ABTest:
        """Resume a paused A/B test.

        Args:
            test_id: Test identifier

        Returns:
            Updated test with RUNNING status

        Raises:
            ABTestNotFoundError: If test not found
        """
        test = self._get_test(test_id)

        if test.status != ABTestStatus.PAUSED:
            raise ABTestValidationError(
                message=f"Cannot resume test with status: {test.status.value}",
                validation_errors=["Test must be PAUSED"],
                trace_id=str(uuid.uuid4()),
            )

        test.status = ABTestStatus.RUNNING

        logger.info(
            "A/B test resumed",
            extra={"test_id": test_id}
        )

        return test

    def assign_variant(
        self,
        test_id: str,
        user_id: str,
    ) -> Optional[str]:
        """Assign a variant for the given user.

        Uses deterministic hash-based routing to ensure consistent
        assignment for the same user_id across requests.

        Args:
            test_id: The A/B test identifier
            user_id: User identifier for routing

        Returns:
            Variant ID if test is running, None otherwise

        Raises:
            ABTestNotFoundError: If test not found
        """
        test = self._get_test(test_id)

        # Only assign if test is running
        if test.status != ABTestStatus.RUNNING:
            return None

        # Calculate hash-based bucket
        hash_input = f"{user_id}:{test_id}"
        hash_value = int(hashlib.sha256(hash_input.encode()).hexdigest(), 16)
        bucket = hash_value % 100

        # Select variant based on traffic percentage
        cumulative = 0
        for variant in test.variants:
            cumulative += variant.traffic_percentage
            if bucket < cumulative:
                # Record impression
                variant.impressions += 1
                return variant.variant_id

        # Fallback to control variant
        control = test.get_control_variant()
        if control:
            control.impressions += 1
            return control.variant_id

        return None

    def record_impression(
        self,
        test_id: str,
        variant_id: str,
    ) -> None:
        """Record a variant impression (explicit call).

        Args:
            test_id: The A/B test identifier
            variant_id: The variant that was shown

        Raises:
            ABTestNotFoundError: If test or variant not found
        """
        test = self._get_test(test_id)
        variant = test.get_variant(variant_id)

        if variant:
            variant.impressions += 1

    def record_outcome(
        self,
        test_id: str,
        variant_id: str,
        success: bool,
        latency_ms: float = 0,
    ) -> None:
        """Record an outcome for a variant.

        Also records an impression since an outcome implies the variant was shown.

        Args:
            test_id: The A/B test identifier
            variant_id: The variant that was used
            success: Whether the outcome was successful
            latency_ms: Response latency in milliseconds

        Raises:
            ABTestNotFoundError: If test or variant not found
        """
        test = self._get_test(test_id)
        variant = test.get_variant(variant_id)

        if variant:
            variant.impressions += 1
            if success:
                variant.successes += 1
            variant.total_latency_ms += latency_ms

    async def get_test(
        self,
        test_id: str,
    ) -> ABTest:
        """Get an A/B test by ID.

        Args:
            test_id: Test identifier

        Returns:
            The A/B test

        Raises:
            ABTestNotFoundError: If test not found
        """
        return self._get_test(test_id)

    def _get_test(self, test_id: str) -> ABTest:
        """Get test from cache (internal method).

        Args:
            test_id: Test identifier

        Returns:
            The A/B test

        Raises:
            ABTestNotFoundError: If test not found
        """
        test = self._cache.get(test_id)
        if test is None:
            raise ABTestNotFoundError(
                test_id=test_id,
                trace_id=str(uuid.uuid4()),
            )
        return test

    async def list_tests(
        self,
        template_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[ABTest]:
        """List all A/B tests with optional filtering.

        Args:
            template_id: Filter by template
            status: Filter by status

        Returns:
            List of A/B tests
        """
        tests = list(self._cache.values())

        # Apply filters
        if template_id:
            tests = [t for t in tests if t.template_id == template_id]
        if status:
            tests = [t for t in tests if t.status.value == status]

        return tests

    async def get_results(
        self,
        test_id: str,
    ) -> Dict[str, VariantMetrics]:
        """Get calculated results for an A/B test.

        Args:
            test_id: Test identifier

        Returns:
            Dictionary of variant metrics

        Raises:
            ABTestNotFoundError: If test not found
        """
        test = await self.get_test(test_id)
        return test.calculate_metrics()

    async def select_winner(
        self,
        test_id: str,
        variant_id: str,
        reason: str = "",
    ) -> ABTest:
        """Select a winner and complete the A/B test.

        Args:
            test_id: Test identifier
            variant_id: Winning variant ID
            reason: Reason for selection

        Returns:
            Updated test with COMPLETED status

        Raises:
            ABTestNotFoundError: If test or variant not found
            ABTestValidationError: If test is not running
        """
        test = await self.get_test(test_id)

        # Validate test is running or paused
        if test.status not in (ABTestStatus.RUNNING, ABTestStatus.PAUSED):
            raise ABTestValidationError(
                message=f"Cannot select winner for test with status: {test.status.value}",
                validation_errors=["Test must be RUNNING or PAUSED"],
                trace_id=str(uuid.uuid4()),
            )

        # Validate variant exists
        variant = test.get_variant(variant_id)
        if variant is None:
            raise ABTestValidationError(
                message=f"Variant not found: {variant_id}",
                validation_errors=[f"Variant {variant_id} not in test"],
                trace_id=str(uuid.uuid4()),
            )

        # Update test
        test.status = ABTestStatus.COMPLETED
        test.ended_at = datetime.utcnow()
        test.winner_variant_id = variant_id
        test.results["winner_reason"] = reason

        # Invalidate cache for the template (winner becomes active)
        cache = get_cache()
        cache.invalidate(test.template_id)

        logger.info(
            "A/B test winner selected",
            extra={
                "test_id": test_id,
                "winner_variant_id": variant_id,
                "reason": reason,
            }
        )

        return test

    def get_active_test_for_template(
        self,
        template_id: str,
    ) -> Optional[ABTest]:
        """Get the active A/B test for a template.

        Args:
            template_id: Template identifier

        Returns:
            Active A/B test or None
        """
        for test in self._cache.values():
            if (
                test.template_id == template_id
                and test.status == ABTestStatus.RUNNING
            ):
                return test
        return None

    def _validate_test_config(self, config: ABTestConfig) -> None:
        """Validate A/B test configuration.

        Args:
            config: Test configuration to validate

        Raises:
            ABTestValidationError: If validation fails
        """
        errors = []

        # Check variants
        if len(config.variants) < 2:
            errors.append("A/B test must have at least 2 variants")

        if len(config.variants) > 5:
            errors.append("A/B test cannot have more than 5 variants")

        # Check traffic percentages
        total_traffic = sum(traffic for _, _, traffic, _ in config.variants)
        if abs(total_traffic - 100.0) > 0.01:
            errors.append(f"Traffic percentages must sum to 100, got {total_traffic}")

        # Check for control variant
        has_control = any(is_control for _, _, _, is_control in config.variants)
        if not has_control:
            errors.append("A/B test must have exactly one control variant")

        if errors:
            raise ABTestValidationError(
                message="A/B test configuration validation failed",
                validation_errors=errors,
                trace_id=str(uuid.uuid4()),
            )


# Global service instance
_service: Optional[ABTestingService] = None


def get_ab_testing_service() -> ABTestingService:
    """Get the global A/B testing service instance.

    Returns:
        A/B testing service instance
    """
    global _service
    if _service is None:
        _service = ABTestingService()
    return _service


def reset_ab_testing_service() -> None:
    """Reset the global service instance.

    This is primarily useful for testing.
    """
    global _service
    _service = None
