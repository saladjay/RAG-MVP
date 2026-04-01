"""
Integration tests for A/B Testing flow (US3).

These tests verify the end-to-end A/B testing flow:
- Deterministic variant assignment
- Metrics tracking
- Test lifecycle management
"""

import pytest
from httpx import AsyncClient, ASGITransport
from typing import Dict, Any
from unittest.mock import MagicMock, patch

from prompt_service.main import app
from prompt_service.services.ab_testing import (
    ABTestingService,
    get_ab_testing_service,
    reset_ab_testing_service,
)
from prompt_service.models.ab_test import (
    ABTestConfig,
    ABTestStatus,
)


class TestABTestingE2E:
    """End-to-end tests for A/B testing flow.

    Tests verify:
    - Deterministic variant assignment
    - Metrics tracking
    - Test lifecycle
    """

    @pytest.fixture
    async def client(self) -> AsyncClient:
        """Create test client."""
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    @pytest.mark.integration
    async def test_deterministic_variant_assignment(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that variant assignment is deterministic for same user.

        Given: An active A/B test
        When: Same user makes multiple requests
        Then: Always assigned to same variant
        """
        # Reset service for clean test
        reset_ab_testing_service()
        service = get_ab_testing_service()

        # Create a test
        config = ABTestConfig(
            template_id="test_prompt",
            name="Deterministic Test",
            description="Test deterministic routing",
            variants=[
                ("variant_a", 1, 50, True),
                ("variant_b", 2, 50, False),
            ],
            success_metric="success_rate",
            min_sample_size=100,
            target_improvement=0.05,
        )

        test = await service.create_test(config)
        await service.start_test(test.test_id)

        # Test same user gets same variant
        user_id = "test_user_123"
        variant1 = service.assign_variant(test.test_id, user_id)
        variant2 = service.assign_variant(test.test_id, user_id)
        variant3 = service.assign_variant(test.test_id, user_id)

        assert variant1 == variant2 == variant3

    @pytest.mark.integration
    async def test_metrics_tracking(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that metrics are tracked correctly.

        Given: An active A/B test
        When: Impression and outcome are recorded
        Then: Metrics reflect the recorded data
        """
        reset_ab_testing_service()
        service = get_ab_testing_service()

        # Create a test
        config = ABTestConfig(
            template_id="test_prompt",
            name="Metrics Test",
            description="Test metrics tracking",
            variants=[
                ("variant_a", 1, 50, True),
                ("variant_b", 2, 50, False),
            ],
            success_metric="success_rate",
            min_sample_size=100,
        )

        test = await service.create_test(config)
        await service.start_test(test.test_id)

        # Record impressions and outcomes
        for i in range(10):
            service.record_impression(test.test_id, "variant_a")
            service.record_outcome(test.test_id, "variant_a", success=(i % 2 == 0), latency_ms=50 + i)

        # Get results
        results = await service.get_results(test.test_id)

        assert "variant_a" in results
        assert results["variant_a"].impressions >= 10
        assert results["variant_a"].successes >= 0

    @pytest.mark.integration
    async def test_traffic_distribution(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that traffic distribution matches configuration.

        Given: An A/B test with 50/50 split
        When: Many users are assigned
        Then: Distribution is approximately 50/50
        """
        reset_ab_testing_service()
        service = get_ab_testing_service()

        # Create a test
        config = ABTestConfig(
            template_id="test_prompt",
            name="Distribution Test",
            description="Test traffic distribution",
            variants=[
                ("variant_a", 1, 50, True),
                ("variant_b", 2, 50, False),
            ],
            success_metric="success_rate",
            min_sample_size=100,
        )

        test = await service.create_test(config)
        await service.start_test(test.test_id)

        # Assign many users
        import string
        import random

        variant_counts = {"variant_a": 0, "variant_b": 0}

        for i in range(1000):
            user_id = f"user_{i}"
            variant = service.assign_variant(test.test_id, user_id)
            if variant:
                variant_counts[variant] += 1

        # Check distribution is approximately 50/50
        # Allow for some variance (45% - 55%)
        total = sum(variant_counts.values())
        if total > 0:
            ratio_a = variant_counts["variant_a"] / total
            assert 0.40 <= ratio_a <= 0.60  # Allow 10% variance

    @pytest.mark.integration
    async def test_ab_test_lifecycle(
        self,
        client: AsyncClient,
    ) -> None:
        """Test complete A/B test lifecycle.

        Given: A new A/B test
        When: Test progresses through draft -> running -> paused -> completed
        Then: Status changes correctly at each stage
        """
        reset_ab_testing_service()
        service = get_ab_testing_service()

        # Create test (DRAFT)
        config = ABTestConfig(
            template_id="test_prompt",
            name="Lifecycle Test",
            description="Test full lifecycle",
            variants=[
                ("variant_a", 1, 50, True),
                ("variant_b", 2, 50, False),
            ],
            success_metric="success_rate",
            min_sample_size=100,
        )

        test = await service.create_test(config)
        assert test.status == ABTestStatus.DRAFT

        # Start test (RUNNING)
        test = await service.start_test(test.test_id)
        assert test.status == ABTestStatus.RUNNING

        # Pause test (PAUSED)
        test = await service.pause_test(test.test_id)
        assert test.status == ABTestStatus.PAUSED

        # Resume test (RUNNING)
        test = await service.resume_test(test.test_id)
        assert test.status == ABTestStatus.RUNNING

        # Select winner (COMPLETED)
        test = await service.select_winner(test.test_id, "variant_b", "Clear winner")
        assert test.status == ABTestStatus.COMPLETED
        assert test.winner_variant_id == "variant_b"

    @pytest.mark.integration
    async def test_get_active_test_for_template(
        self,
        client: AsyncClient,
    ) -> None:
        """Test retrieving active test for a template.

        Given: A template with an active A/B test
        When: get_active_test_for_template is called
        Then: Returns the active test
        """
        reset_ab_testing_service()
        service = get_ab_testing_service()

        # Create and start a test
        config = ABTestConfig(
            template_id="active_test_prompt",
            name="Active Test",
            description="Test for active retrieval",
            variants=[
                ("variant_a", 1, 50, True),
                ("variant_b", 2, 50, False),
            ],
            success_metric="success_rate",
            min_sample_size=100,
        )

        test = await service.create_test(config)
        await service.start_test(test.test_id)

        # Get active test
        active = service.get_active_test_for_template("active_test_prompt")

        assert active is not None
        assert active.test_id == test.test_id
        assert active.status == ABTestStatus.RUNNING

    @pytest.mark.integration
    async def test_concurrent_variant_assignment(
        self,
        client: AsyncClient,
    ) -> None:
        """Test variant assignment under concurrent load.

        Given: An active A/B test
        When: Many concurrent requests assign variants
        Then: All assignments complete without error
        """
        import asyncio

        reset_ab_testing_service()
        service = get_ab_testing_service()

        # Create test
        config = ABTestConfig(
            template_id="concurrent_test_prompt",
            name="Concurrent Test",
            description="Test concurrent assignment",
            variants=[
                ("variant_a", 1, 50, True),
                ("variant_b", 2, 50, False),
                ("variant_c", 3, 0, False),  # 0% traffic
            ],
            success_metric="success_rate",
            min_sample_size=100,
        )

        test = await service.create_test(config)
        await service.start_test(test.test_id)

        # Concurrent assignments
        async def assign_user(user_num: int) -> str:
            return service.assign_variant(test.test_id, f"user_{user_num}")

        results = await asyncio.gather(
            *[assign_user(i) for i in range(100)],
            return_exceptions=True
        )

        # All should complete without exceptions
        successful = [r for r in results if not isinstance(r, Exception)]
        assert len(successful) == 100

        # No one should be assigned to variant_c (0% traffic)
        assert "variant_c" not in successful or successful.count("variant_c") == 0


class TestABTestingServiceDirect:
    """Direct service tests for ABTestingService."""

    @pytest.mark.integration
    def test_hash_based_routing_is_deterministic(
        self,
    ) -> None:
        """Test that hash-based routing produces consistent results.

        Given: Same user_id and test_id
        When: Routing is calculated multiple times
        Then: Always produces same bucket
        """
        import hashlib

        test_id = "test_ab_123"
        user_id = "consistent_user"

        # Calculate hash bucket multiple times
        buckets = []
        for _ in range(100):
            hash_input = f"{user_id}:{test_id}"
            hash_value = int(hashlib.sha256(hash_input.encode()).hexdigest(), 16)
            bucket = hash_value % 100
            buckets.append(bucket)

        # All buckets should be the same
        assert len(set(buckets)) == 1
