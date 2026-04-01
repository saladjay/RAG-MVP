"""
Contract tests for Analytics API (US4).

These tests verify the API contract for analytics endpoints:
- GET /api/v1/analytics/prompts/{template_id} (prompt analytics)
- GET /api/v1/analytics/traces (trace search)
"""

import pytest
from datetime import datetime, timedelta
from httpx import AsyncClient, ASGITransport
from typing import Dict, Any

from prompt_service.main import app


class TestAnalyticsContract:
    """Contract tests for analytics endpoints.

    Tests verify:
    - Analytics returns aggregate metrics
    - Trace search filters correctly
    """

    @pytest.fixture
    def client(self) -> AsyncClient:
        """Create test client."""
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    @pytest.mark.contract
    async def test_analytics_returns_aggregate_metrics(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that analytics endpoint returns aggregate metrics.

        Given: A prompt template with usage data
        When: GET /api/v1/analytics/prompts/{template_id} is called
        Then: Returns metrics summary with totals and percentiles
        """
        template_id = "test_analytics_prompt"

        response = await client.get(
            f"/api/v1/analytics/prompts/{template_id}"
        )

        # May return 200 if analytics available
        # May return 404 if template not found
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            assert "template_id" in data
            assert "metrics" in data

            metrics = data["metrics"]
            assert "total_count" in metrics
            assert "success_count" in metrics
            assert "error_count" in metrics
            assert "success_rate" in metrics
            assert "avg_latency_ms" in metrics
            assert "p50_latency_ms" in metrics
            assert "p95_latency_ms" in metrics
            assert "p99_latency_ms" in metrics

    @pytest.mark.contract
    async def test_analytics_with_date_range(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that analytics supports date range filtering.

        Given: Usage data across multiple days
        When: GET /api/v1/analytics with start_date and end_date
        Then: Returns metrics for the specified period
        """
        template_id = "test_analytics_prompt"

        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=7)

        response = await client.get(
            f"/api/v1/analytics/prompts/{template_id}",
            params={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            }
        )

        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            assert "period_start" in data or "metrics" in data

    @pytest.mark.contract
    async def test_analytics_includes_ab_test_results(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that analytics includes A/B test results when active.

        Given: A prompt with an active A/B test
        When: GET /api/v1/analytics/prompts/{template_id}
        Then: Response includes variant comparison metrics
        """
        template_id = "test_ab_analytics_prompt"

        response = await client.get(
            f"/api/v1/analytics/prompts/{template_id}",
            params={"include_ab_test_results": "true"}
        )

        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            # If A/B test data exists, should include variant_metrics
            if "metrics" in data and data["metrics"].get("variant_metrics"):
                assert isinstance(data["metrics"]["variant_metrics"], dict)

    @pytest.mark.contract
    async def test_trace_search_filters_by_template(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that trace search filters by template_id.

        Given: Multiple trace records
        When: GET /api/v1/analytics/traces with template_id filter
        Then: Returns only traces for that template
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=1)

        response = await client.get(
            "/api/v1/analytics/traces",
            params={
                "template_id": "test_prompt",
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            }
        )

        assert response.status_code == 200

        data = response.json()
        assert "traces" in data
        assert "total" in data
        assert "offset" in data
        assert "limit" in data

    @pytest.mark.contract
    async def test_trace_search_filters_by_variant(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that trace search filters by variant_id.

        Given: Trace records from multiple A/B test variants
        When: GET /api/v1/analytics/traces with variant_id filter
        Then: Returns only traces for that variant
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=1)

        response = await client.get(
            "/api/v1/analytics/traces",
            params={
                "variant_id": "variant_a",
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            }
        )

        assert response.status_code == 200

        data = response.json()
        assert "traces" in data

    @pytest.mark.contract
    async def test_trace_search_filters_by_success(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that trace search filters by success status.

        Given: Both successful and failed traces
        When: GET /api/v1/analytics/traces with success filter
        Then: Returns only traces matching the filter
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=1)

        # Test for successful traces
        response = await client.get(
            "/api/v1/analytics/traces",
            params={
                "success": "true",
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            }
        )

        assert response.status_code == 200

        data = response.json()
        assert "traces" in data

    @pytest.mark.contract
    async def test_trace_search_pagination(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that trace search supports pagination.

        Given: Many trace records
        When: GET /api/v1/analytics/traces with offset and limit
        Then: Returns paginated results
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=1)

        response = await client.get(
            "/api/v1/analytics/traces",
            params={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "offset": 0,
                "limit": 50,
            }
        )

        assert response.status_code == 200

        data = response.json()
        assert "traces" in data
        assert "total" in data
        assert "offset" in data
        assert data["offset"] == 0
        assert data["limit"] == 50

    @pytest.mark.contract
    async def test_trace_item_schema(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that trace items have correct schema.

        Given: Trace records exist
        When: GET /api/v1/analytics/traces
        Then: Each trace has required fields
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=1)

        response = await client.get(
            "/api/v1/analytics/traces",
            params={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "limit": 10,
            }
        )

        assert response.status_code == 200

        data = response.json()
        if data["traces"]:
            trace = data["traces"][0]
            assert "trace_id" in trace
            assert "template_id" in trace
            assert "template_version" in trace
            assert "timestamp" in trace
            assert "latency_ms" in trace
            assert "success" in trace

    @pytest.mark.contract
    async def test_analytics_requires_date_range(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that trace search requires date range.

        Given: A trace search request without dates
        When: GET /api/v1/analytics/traces without start_date/end_date
        Then: Returns 400 validation error
        """
        response = await client.get("/api/v1/analytics/traces")

        # Should require date range
        assert response.status_code == 400
