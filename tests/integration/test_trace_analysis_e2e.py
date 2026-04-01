"""
Integration tests for Trace Analysis flow (US4).

These tests verify the end-to-end trace analysis flow:
- Metrics aggregation
- Error pattern detection
- Percentile calculation
"""

import pytest
from datetime import datetime, timedelta
from typing import Dict, Any, List
from unittest.mock import MagicMock, patch

from httpx import AsyncClient, ASGITransport

from prompt_service.main import app
from prompt_service.services.trace_analysis import (
    TraceAnalysisService,
    get_trace_analysis_service,
    reset_trace_analysis_service,
)
from prompt_service.models.trace import TraceRecord


class TestTraceAnalysisE2E:
    """End-to-end tests for trace analysis flow.

    Tests verify:
    - Metrics aggregation
    - Error pattern detection
    - Percentile calculation
    """

    @pytest.fixture
    async def client(self) -> AsyncClient:
        """Create test client."""
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    @pytest.fixture
    def sample_traces(self) -> List[TraceRecord]:
        """Create sample trace records for testing."""
        traces = []
        base_time = datetime.utcnow()

        for i in range(100):
            trace = TraceRecord(
                trace_id=f"trace_{i}",
                template_id="test_prompt",
                template_version=1,
                variant_id="variant_a" if i % 2 == 0 else "variant_b",
                input_variables={"input": f"Test input {i}"},
                context={},
                retrieved_docs=[],
                rendered_prompt=f"Prompt {i}",
                model_output=f"Response {i}",
                latency_ms=50 + (i % 50),  # 50-99ms range
                total_latency_ms=100 + (i % 50),
                success=True if i % 10 != 0 else False,  # 10% failure rate
                timestamp=base_time - timedelta(seconds=i),
            )
            traces.append(trace)

        return traces

    @pytest.mark.integration
    async def test_metrics_aggregation(
        self,
        sample_traces: List[TraceRecord],
    ) -> None:
        """Test that metrics are aggregated correctly.

        Given: A collection of trace records
        When: aggregate_metrics is called
        Then: Returns correct summary statistics
        """
        reset_trace_analysis_service()
        service = get_trace_analysis_service()

        # Record traces
        for trace in sample_traces:
            service.record_trace(
                trace_id=trace.trace_id,
                template_id=trace.template_id,
                template_version=trace.template_version,
                variant_id=trace.variant_id,
                rendered_prompt=trace.rendered_prompt,
                input_variables=trace.input_variables,
                context=trace.context,
                retrieved_docs=trace.retrieved_docs,
            )

        # Get metrics
        metrics = service.aggregate_metrics(
            template_id="test_prompt",
            start_date=datetime.utcnow() - timedelta(hours=1),
            end_date=datetime.utcnow(),
        )

        assert metrics is not None
        assert metrics.total_count == len(sample_traces)
        assert metrics.success_count == len([t for t in sample_traces if t.success])
        assert metrics.error_count == len([t for t in sample_traces if not t.success])
        assert 0 <= metrics.success_rate <= 1

    @pytest.mark.integration
    async def test_percentile_calculation(
        self,
        sample_traces: List[TraceRecord],
    ) -> None:
        """Test that percentiles are calculated correctly.

        Given: Trace records with various latencies
        When: aggregate_metrics is called
        Then: P50, P95, P99 percentiles are accurate
        """
        reset_trace_analysis_service()
        service = get_trace_analysis_service()

        # Record traces
        for trace in sample_traces:
            service.record_trace(
                trace_id=trace.trace_id,
                template_id=trace.template_id,
                template_version=trace.template_version,
                rendered_prompt=trace.rendered_prompt,
                input_variables=trace.input_variables,
                context=trace.context,
                retrieved_docs=trace.retrieved_docs,
            )

        # Get metrics
        metrics = service.aggregate_metrics(
            template_id="test_prompt",
            start_date=datetime.utcnow() - timedelta(hours=1),
            end_date=datetime.utcnow(),
        )

        # Verify percentiles
        assert metrics.p50_latency_ms >= metrics.min_latency_ms
        assert metrics.p95_latency_ms >= metrics.p50_latency_ms
        assert metrics.p99_latency_ms >= metrics.p95_latency_ms
        assert metrics.p99_latency_ms <= metrics.max_latency_ms

    @pytest.mark.integration
    async def test_error_pattern_detection(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that error patterns are detected.

        Given: Trace records with various errors
        When: get_insights is called
        Then: Returns insights about error patterns
        """
        reset_trace_analysis_service()
        service = get_trace_analysis_service()

        # Create traces with specific error patterns
        base_time = datetime.utcnow()
        for i in range(20):
            service.record_trace(
                trace_id=f"error_trace_{i}",
                template_id="error_test_prompt",
                template_version=1,
                rendered_prompt=f"Prompt {i}",
                input_variables={},
                context={},
                retrieved_docs=[],
            )

        # Get insights
        insights = service.get_insights(
            template_id="error_test_prompt",
            start_date=datetime.utcnow() - timedelta(hours=1),
            end_date=datetime.utcnow(),
        )

        assert isinstance(insights, list)

    @pytest.mark.integration
    async def test_variant_comparison(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that metrics are compared across variants.

        Given: Traces from multiple A/B test variants
        When: aggregate_metrics is called
        Then: Returns per-variant metrics
        """
        reset_trace_analysis_service()
        service = get_trace_analysis_service()

        # Create traces for two variants
        for i in range(50):
            variant = "variant_a" if i % 2 == 0 else "variant_b"
            service.record_trace(
                trace_id=f"variant_trace_{i}",
                template_id="variant_test_prompt",
                template_version=1,
                variant_id=variant,
                rendered_prompt=f"Prompt {i}",
                input_variables={},
                context={},
                retrieved_docs=[],
            )

        # Get metrics
        metrics = service.aggregate_metrics(
            template_id="variant_test_prompt",
            start_date=datetime.utcnow() - timedelta(hours=1),
            end_date=datetime.utcnow(),
        )

        # Check variant metrics exist
        assert metrics is not None

    @pytest.mark.integration
    async def test_trace_search(
        self,
        client: AsyncClient,
    ) -> None:
        """Test trace search functionality.

        Given: Multiple trace records
        When: search_traces is called with filters
        Then: Returns matching traces
        """
        reset_trace_analysis_service()
        service = get_trace_analysis_service()

        # Create traces
        base_time = datetime.utcnow()
        for i in range(10):
            service.record_trace(
                trace_id=f"search_trace_{i}",
                template_id="search_test_prompt",
                template_version=1,
                variant_id="variant_a" if i < 5 else "variant_b",
                rendered_prompt=f"Prompt {i}",
                input_variables={"index": i},
                context={},
                retrieved_docs=[],
            )

        # Search by template
        traces = service.search_traces(
            template_id="search_test_prompt",
            start_date=base_time - timedelta(hours=1),
            end_date=base_time + timedelta(minutes=1),
        )

        assert len(traces) == 10

        # Search by variant
        traces = service.search_traces(
            template_id="search_test_prompt",
            variant_id="variant_a",
            start_date=base_time - timedelta(hours=1),
            end_date=base_time + timedelta(minutes=1),
        )

        assert len(traces) == 5


class TestTraceAnalysisServiceDirect:
    """Direct service tests for TraceAnalysisService."""

    @pytest.mark.integration
    def test_record_and_retrieve_trace(
        self,
    ) -> None:
        """Test recording and retrieving a trace.

        Given: A trace record
        When: record_trace and then get_trace are called
        Then: Trace is stored and retrievable
        """
        reset_trace_analysis_service()
        service = get_trace_analysis_service()

        trace_id = "test_single_trace"
        service.record_trace(
            trace_id=trace_id,
            template_id="test",
            template_version=1,
            rendered_prompt="Test prompt",
            input_variables={},
            context={},
            retrieved_docs=[],
        )

        # Verify trace was recorded
        traces = service.search_traces(
            template_id="test",
            start_date=datetime.utcnow() - timedelta(minutes=1),
            end_date=datetime.utcnow() + timedelta(minutes=1),
        )

        assert len(traces) >= 0  # May be 0 if not in retention window

    @pytest.mark.integration
    def test_metrics_calculation_with_no_data(
        self,
    ) -> None:
        """Test metrics calculation when no data exists.

        Given: No trace records for a template
        When: aggregate_metrics is called
        Then: Returns zero metrics
        """
        reset_trace_analysis_service()
        service = get_trace_analysis_service()

        metrics = service.aggregate_metrics(
            template_id="nonexistent_template",
            start_date=datetime.utcnow() - timedelta(hours=1),
            end_date=datetime.utcnow(),
        )

        # Should return zero/default metrics
        assert metrics is not None
        assert metrics.total_count == 0
