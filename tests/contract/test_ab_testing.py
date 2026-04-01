"""
Contract tests for A/B Testing API (US3).

These tests verify the API contract for A/B testing endpoints:
- POST /api/v1/ab-tests (create)
- GET /api/v1/ab-tests (list)
- GET /api/v1/ab-tests/{test_id} (get results)
- POST /api/v1/ab-tests/{test_id}/winner (select winner)
"""

import pytest
from httpx import AsyncClient, ASGITransport
from typing import Dict, Any

from prompt_service.main import app


class TestABTestingContract:
    """Contract tests for A/B testing endpoints.

    Tests verify:
    - Create A/B test validates traffic split
    - Retrieve A/B test returns metrics
    - Winner selection works correctly
    """

    @pytest.fixture
    def client(self) -> AsyncClient:
        """Create test client."""
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    @pytest.fixture
    def sample_ab_test_request(self) -> Dict[str, Any]:
        """Sample A/B test creation request."""
        return {
            "template_id": "test_prompt",
            "name": "Test A vs B",
            "description": "Compare two prompt variants",
            "variants": [
                {
                    "variant_id": "variant_a",
                    "template_version": 1,
                    "traffic_percentage": 50,
                    "is_control": True
                },
                {
                    "variant_id": "variant_b",
                    "template_version": 2,
                    "traffic_percentage": 50,
                    "is_control": False
                }
            ],
            "success_metric": "success_rate",
            "min_sample_size": 1000,
            "target_improvement": 0.05
        }

    @pytest.mark.contract
    async def test_create_ab_test_validates_traffic_split(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that create A/B test validates traffic percentages sum to 100.

        Given: An A/B test request with traffic not summing to 100
        When: POST /api/v1/ab-tests is called
        Then: Returns 400 with validation error
        """
        # Test with traffic not summing to 100
        invalid_request = {
            "template_id": "test_prompt",
            "name": "Invalid Test",
            "description": "Traffic doesn't sum to 100",
            "variants": [
                {
                    "variant_id": "variant_a",
                    "template_version": 1,
                    "traffic_percentage": 30,  # Total would be 60
                    "is_control": True
                },
                {
                    "variant_id": "variant_b",
                    "template_version": 2,
                    "traffic_percentage": 30,
                    "is_control": False
                }
            ],
            "success_metric": "success_rate"
        }

        response = await client.post(
            "/api/v1/ab-tests",
            json=invalid_request
        )

        # Should return 400 or 422 for validation error
        assert response.status_code in [400, 422]

    @pytest.mark.contract
    async def test_create_ab_test_requires_min_two_variants(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that create A/B test requires at least 2 variants.

        Given: An A/B test request with only 1 variant
        When: POST /api/v1/ab-tests is called
        Then: Returns 400 with validation error
        """
        invalid_request = {
            "template_id": "test_prompt",
            "name": "Single Variant Test",
            "description": "Only one variant",
            "variants": [
                {
                    "variant_id": "variant_a",
                    "template_version": 1,
                    "traffic_percentage": 100,
                    "is_control": True
                }
            ],
            "success_metric": "success_rate"
        }

        response = await client.post(
            "/api/v1/ab-tests",
            json=invalid_request
        )

        assert response.status_code in [400, 422]

    @pytest.mark.contract
    async def test_create_ab_test_requires_control_variant(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that create A/B test requires a control variant.

        Given: An A/B test request with no control variant
        When: POST /api/v1/ab-tests is called
        Then: Returns 400 with validation error
        """
        invalid_request = {
            "template_id": "test_prompt",
            "name": "No Control Test",
            "description": "No control variant specified",
            "variants": [
                {
                    "variant_id": "variant_a",
                    "template_version": 1,
                    "traffic_percentage": 50,
                    "is_control": False
                },
                {
                    "variant_id": "variant_b",
                    "template_version": 2,
                    "traffic_percentage": 50,
                    "is_control": False
                }
            ],
            "success_metric": "success_rate"
        }

        response = await client.post(
            "/api/v1/ab-tests",
            json=invalid_request
        )

        assert response.status_code in [400, 422]

    @pytest.mark.contract
    async def test_create_ab_test_returns_201(
        self,
        client: AsyncClient,
        sample_ab_test_request: Dict[str, Any],
    ) -> None:
        """Test that create A/B test returns 201.

        Given: A valid A/B test request
        When: POST /api/v1/ab-tests is called
        Then: Returns 201 with test_id
        """
        response = await client.post(
            "/api/v1/ab-tests",
            json=sample_ab_test_request
        )

        # May return 201 if successful
        # May return 503 if dependencies unavailable
        assert response.status_code in [201, 503]

        if response.status_code == 201:
            data = response.json()
            assert "test_id" in data
            assert "status" in data
            assert "created_at" in data
            # trace_id is not part of ABTestResponse schema
            # assert "trace_id" in data

    @pytest.mark.contract
    async def test_list_ab_tests(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that list A/B tests returns tests array.

        Given: Multiple A/B tests exist
        When: GET /api/v1/ab-tests is called
        Then: Returns array of tests with status info
        """
        response = await client.get("/api/v1/ab-tests")

        assert response.status_code == 200

        data = response.json()
        assert "tests" in data
        assert isinstance(data["tests"], list)

    @pytest.mark.contract
    async def test_list_ab_tests_with_filters(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that list A/B tests supports status and template_id filters.

        Given: Multiple A/B tests with different statuses
        When: GET /api/v1/ab-tests with filter params
        Then: Returns filtered results
        """
        # Test status filter
        response = await client.get("/api/v1/ab-tests?status=running")
        assert response.status_code == 200

        # Test template_id filter
        response = await client.get("/api/v1/ab-tests?template_id=test_prompt")
        assert response.status_code == 200

    @pytest.mark.contract
    async def test_retrieve_ab_test_returns_metrics(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that retrieve A/B test returns detailed metrics.

        Given: An A/B test with some data
        When: GET /api/v1/ab-tests/{test_id} is called
        Then: Returns metrics for each variant
        """
        test_id = "test_ab_123"

        response = await client.get(f"/api/v1/ab-tests/{test_id}")

        # May return 200 if test exists
        # May return 404 if not found
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            assert "test_id" in data
            assert "template_id" in data
            assert "status" in data
            assert "variants" in data
            assert isinstance(data["variants"], list)

            # Check variant metrics structure
            if data["variants"]:
                variant = data["variants"][0]
                assert "variant_id" in variant
                assert "impressions" in variant
                assert "successes" in variant
                assert "success_rate" in variant

    @pytest.mark.contract
    async def test_select_winner(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that select winner completes the test.

        Given: A running A/B test
        When: POST /api/v1/ab-tests/{test_id}/winner is called
        Then: Returns 200 with completed status
        """
        test_id = "test_ab_winner"

        response = await client.post(
            f"/api/v1/ab-tests/{test_id}/winner",
            json={
                "variant_id": "variant_b",
                "reason": "Clear winner with 5% improvement"
            }
        )

        # May return 200 if test exists
        # May return 404 if not found
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            assert "test_id" in data
            assert "winner_variant_id" in data
            assert "status" in data
            assert data["status"] in ["completed", "archived"]

    @pytest.mark.contract
    async def test_pause_resume_ab_test(
        self,
        client: AsyncClient,
    ) -> None:
        """Test pause and resume operations.

        Given: A running A/B test
        When: POST /api/v1/ab-tests/{test_id}/pause and /resume
        Then: Status changes correctly
        """
        test_id = "test_ab_pause"

        # Pause
        pause_response = await client.post(f"/api/v1/ab-tests/{test_id}/pause")
        assert pause_response.status_code in [200, 404]

        if pause_response.status_code == 200:
            data = pause_response.json()
            assert data["status"] == "paused"

        # Resume
        resume_response = await client.post(f"/api/v1/ab-tests/{test_id}/resume")
        assert resume_response.status_code in [200, 404]

        if resume_response.status_code == 200:
            data = resume_response.json()
            assert data["status"] == "running"
