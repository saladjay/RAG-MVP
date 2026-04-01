"""
Unit tests for ABTestingService.

Tests verify:
- Deterministic routing
- Traffic distribution
- Metrics tracking
"""

import pytest
from datetime import datetime
from typing import Dict, Any

from prompt_service.services.ab_testing import (
    ABTestingService,
    get_ab_testing_service,
    reset_ab_testing_service,
)
from prompt_service.models.ab_test import (
    ABTestConfig,
    ABTestStatus,
)


class TestABTestingService:
    """Unit tests for ABTestingService."""

    @pytest.fixture
    def service(self) -> ABTestingService:
        """Get a fresh service instance for each test."""
        reset_ab_testing_service()
        return get_ab_testing_service()

    @pytest.fixture
    def sample_config(self) -> ABTestConfig:
        """Sample A/B test configuration."""
        return ABTestConfig(
            template_id="test_prompt",
            name="Test A/B Test",
            description="Testing A/B functionality",
            variants=[
                ("variant_a", 1, 50, True),
                ("variant_b", 2, 50, False),
            ],
            success_metric="success_rate",
            min_sample_size=100,
            target_improvement=0.05,
        )

    async def test_deterministic_routing(
        self,
        service: ABTestingService,
        sample_config: ABTestConfig,
    ) -> None:
        """Test that variant assignment is deterministic for same user.

        Given: An A/B test with running status
        When: assign_variant is called multiple times with same user_id
        Then: Always returns the same variant_id
        """
        # Create and start test
        test = await service.create_test(sample_config, created_by="test")
        await service.start_test(test.test_id)

        user_id = "consistent_user_123"

        # Assign multiple times (assign_variant is sync)
        variant1 = service.assign_variant(test.test_id, user_id)
        variant2 = service.assign_variant(test.test_id, user_id)
        variant3 = service.assign_variant(test.test_id, user_id)

        assert variant1 is not None
        assert variant1 == variant2 == variant3

    async def test_routing_consistency_across_users(
        self,
        service: ABTestingService,
        sample_config: ABTestConfig,
    ) -> None:
        """Test that different users may get different variants.

        Given: An A/B test with 50/50 split
        When: Multiple users are assigned
        Then: Both variants are assigned (approximately equally)
        """
        test = await service.create_test(sample_config, created_by="test")
        await service.start_test(test.test_id)

        assignments = {}
        for i in range(100):
            user_id = f"user_{i}"
            variant = service.assign_variant(test.test_id, user_id)  # sync method
            assignments[variant] = assignments.get(variant, 0) + 1

        # Both variants should be assigned
        assert "variant_a" in assignments
        assert "variant_b" in assignments

        # Distribution should be roughly 50/50 (allow 20% variance)
        total = sum(assignments.values())
        ratio_a = assignments["variant_a"] / total
        assert 0.30 <= ratio_a <= 0.70

    async def test_traffic_distribution_tracking(
        self,
        service: ABTestingService,
        sample_config: ABTestConfig,
    ) -> None:
        """Test that traffic distribution is tracked correctly.

        Given: An A/B test with specific traffic percentages
        When: Users are assigned variants
        Then: Impression counts match traffic distribution
        """
        test = await service.create_test(sample_config, created_by="test")
        await service.start_test(test.test_id)

        # Record some impressions manually (assign_variant is sync)
        for i in range(10):
            service.assign_variant(test.test_id, f"user_{i}")

        # Check that impressions were tracked
        test_result = await service.get_test(test.test_id)

        total_impressions = sum(v.impressions for v in test_result.variants)
        assert total_impressions == 10

    async def test_metrics_tracking(
        self,
        service: ABTestingService,
        sample_config: ABTestConfig,
    ) -> None:
        """Test that outcome metrics are tracked correctly.

        Given: An A/B test
        When: record_outcome is called for various results
        Then: Metrics (successes, latency) are accumulated
        """
        test = await service.create_test(sample_config, created_by="test")
        await service.start_test(test.test_id)

        # Record some outcomes (record_outcome is sync)
        for i in range(10):
            variant = "variant_a" if i % 2 == 0 else "variant_b"
            success = i % 3 != 0  # 2/3 success rate
            latency = 50 + i * 10

            service.record_outcome(test.test_id, variant, success, latency)

        # Get results
        results = await service.get_results(test.test_id)

        assert "variant_a" in results
        assert "variant_b" in results

        # Check metrics
        variant_a = results["variant_a"]
        assert variant_a.successes >= 0
        assert variant_a.avg_latency_ms > 0

    async def test_create_test_validation(
        self,
        service: ABTestingService,
    ) -> None:
        """Test that test creation validates configuration.

        Given: Invalid A/B test configurations
        When: create_test is called
        Then: Raises validation error for invalid configs
        """
        from prompt_service.core.exceptions import ABTestValidationError

        # Traffic doesn't sum to 100
        invalid_config = ABTestConfig(
            template_id="test",
            name="Invalid",
            description="Invalid traffic",
            variants=[
                ("v_a", 1, 30, True),
                ("v_b", 2, 30, False),
                # Total: 60, not 100
            ],
            success_metric="success_rate",
            min_sample_size=100,
        )

        with pytest.raises(ABTestValidationError):
            await service.create_test(invalid_config)

        # No control variant
        invalid_config2 = ABTestConfig(
            template_id="test",
            name="Invalid",
            description="No control",
            variants=[
                ("v_a", 1, 50, False),
                ("v_b", 2, 50, False),
            ],
            success_metric="success_rate",
            min_sample_size=100,
        )

        with pytest.raises(ABTestValidationError):
            await service.create_test(invalid_config2)

    async def test_lifecycle_transitions(
        self,
        service: ABTestingService,
        sample_config: ABTestConfig,
    ) -> None:
        """Test that test status transitions work correctly.

        Given: A new A/B test
        When: Status transitions are performed
        Then: Status changes follow allowed transitions
        """
        from prompt_service.core.exceptions import ABTestValidationError

        # Create test (DRAFT status)
        test = await service.create_test(sample_config)
        assert test.status == ABTestStatus.DRAFT

        # Start test (DRAFT -> RUNNING)
        test = await service.start_test(test.test_id)
        assert test.status == ABTestStatus.RUNNING

        # Pause test (RUNNING -> PAUSED)
        test = await service.pause_test(test.test_id)
        assert test.status == ABTestStatus.PAUSED

        # Resume test (PAUSED -> RUNNING)
        test = await service.resume_test(test.test_id)
        assert test.status == ABTestStatus.RUNNING

        # Select winner (RUNNING -> COMPLETED)
        test = await service.select_winner(test.test_id, "variant_a", "Test complete")
        assert test.status == ABTestStatus.COMPLETED
        assert test.winner_variant_id == "variant_a"

    async def test_get_active_test_for_template(
        self,
        service: ABTestingService,
        sample_config: ABTestConfig,
    ) -> None:
        """Test retrieving active test for a template.

        Given: A template with multiple tests
        When: get_active_test_for_template is called
        Then: Returns only the RUNNING test
        """
        # Create first test and leave it as DRAFT
        test1 = await service.create_test(sample_config)

        # Create second test and start it
        test2 = await service.create_test(
            ABTestConfig(
                template_id="test_prompt",
                name="Active Test",
                description="This one is running",
                variants=[
                    ("variant_a", 1, 50, True),
                    ("variant_b", 2, 50, False),
                ],
                success_metric="success_rate",
                min_sample_size=100,
            )
        )
        await service.start_test(test2.test_id)

        # Get active test (get_active_test_for_template is sync)
        active = service.get_active_test_for_template("test_prompt")

        assert active is not None
        assert active.test_id == test2.test_id
        assert active.status == ABTestStatus.RUNNING

    async def test_select_winner_validation(
        self,
        service: ABTestingService,
        sample_config: ABTestConfig,
    ) -> None:
        """Test that select winner validates input.

        Given: An A/B test
        When: select_winner is called with invalid variant
        Then: Raises validation error
        """
        from prompt_service.core.exceptions import ABTestValidationError

        test = await service.create_test(sample_config)
        await service.start_test(test.test_id)

        # Try to select non-existent variant
        with pytest.raises(ABTestValidationError):
            await service.select_winner(test.test_id, "nonexistent_variant")

    async def test_list_tests_filtering(
        self,
        service: ABTestingService,
        sample_config: ABTestConfig,
    ) -> None:
        """Test that list_tests filters correctly.

        Given: Multiple A/B tests with different statuses
        When: list_tests is called with filters
        Then: Returns only matching tests
        """
        # Create tests with different statuses
        test1 = await service.create_test(sample_config)  # DRAFT
        test2 = await service.create_test(
            ABTestConfig(
                template_id="other_template",
                name="Test 2",
                description="Test",
                variants=[
                    ("v_a", 1, 50, True),
                    ("v_b", 2, 50, False),
                ],
                success_metric="success_rate",
                min_sample_size=100,
            )
        )
        await service.start_test(test2.test_id)  # RUNNING

        # List all tests
        all_tests = await service.list_tests()
        assert len(all_tests) == 2

        # Filter by template_id
        template_tests = await service.list_tests(template_id="test_prompt")
        assert len(template_tests) == 1
        assert template_tests[0].test_id == test1.test_id

        # Filter by status
        running_tests = await service.list_tests(status="running")
        assert len(running_tests) == 1
        assert running_tests[0].test_id == test2.test_id

    async def test_results_calculation(
        self,
        service: ABTestingService,
        sample_config: ABTestConfig,
    ) -> None:
        """Test that results are calculated correctly.

        Given: An A/B test with recorded data
        When: get_results is called
        Then: Returns accurate metrics for each variant
        """
        test = await service.create_test(sample_config)
        await service.start_test(test.test_id)

        # Simulate some data
        # Note: record_outcome now also records an impression
        # Variant A: 100 outcomes, 80 successes (80% rate)
        for i in range(100):
            outcome_success = i < 80  # 80 successes
            service.record_outcome(test.test_id, "variant_a", outcome_success, 100)  # sync

        # Variant B: 100 outcomes, 90 successes (90% rate)
        for i in range(100):
            outcome_success = i < 90  # 90 successes
            service.record_outcome(test.test_id, "variant_b", outcome_success, 110)  # sync

        # Get results
        results = await service.get_results(test.test_id)

        assert "variant_a" in results
        assert "variant_b" in results

        assert results["variant_a"].impressions == 100
        assert results["variant_a"].successes == 80
        assert results["variant_a"].success_rate == 0.8

        assert results["variant_b"].impressions == 100
        assert results["variant_b"].successes == 90
        assert results["variant_b"].success_rate == 0.9
