"""
Unit tests for TraceAnalysisService.

Tests verify:
- Metrics aggregation
- Percentile calculation
- Error pattern detection
"""

import pytest
from datetime import datetime, timedelta
from typing import List

from prompt_service.services.trace_analysis import (
    TraceAnalysisService,
    get_trace_analysis_service,
    reset_trace_analysis_service,
)
from prompt_service.models.trace import TraceRecord, TraceFilter


class TestTraceAnalysisService:
    """Unit tests for TraceAnalysisService."""

    @pytest.fixture
    def service(self) -> TraceAnalysisService:
        """Get a fresh service instance for each test."""
        reset_trace_analysis_service()
        return get_trace_analysis_service()

    @pytest.fixture
    def sample_traces(self) -> List[TraceRecord]:
        """Create sample trace records for testing."""
        traces = []
        base_time = datetime.utcnow()

        # Create traces with varying latencies and success rates
        for i in range(100):
            trace = TraceRecord(
                trace_id=f"trace_{i}",
                template_id="test_prompt",
                template_version=1,
                variant_id="variant_a" if i % 2 == 0 else "variant_b",
                input_variables={"input": f"test_{i}"},
                context={},
                retrieved_docs=[],
                rendered_prompt=f"Prompt {i}",
                model_output=f"Response {i}",
                latency_ms=50 + (i % 50),  # 50-99ms range
                total_latency_ms=100 + (i % 50),  # 100-149ms range
                success=True if i % 10 != 0 else False,  # 10% failure rate
                timestamp=base_time - timedelta(seconds=i),
            )
            traces.append(trace)

        return traces

    def test_metrics_aggregation(
        self,
        service: TraceAnalysisService,
        sample_traces: List[TraceRecord],
    ) -> None:
        """Test that metrics are aggregated correctly.

        Given: A collection of trace records
        When: aggregate_metrics is called
        Then: Returns correct summary statistics
        """
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
                latency_ms=trace.latency_ms,
                success=trace.success,
            )

        # Get metrics
        metrics = service.aggregate_metrics(
            template_id="test_prompt",
        )

        assert metrics is not None
        assert metrics.total_count == 100

        # Success rate should be approximately 90% (10% failure rate)
        expected_successes = 90  # 100 - 10 failures
        assert metrics.success_count == expected_successes
        assert metrics.error_count == 10
        assert abs(metrics.success_rate - 0.9) < 0.01

    def test_percentile_calculation(
        self,
        service: TraceAnalysisService,
    ) -> None:
        """Test that percentiles are calculated correctly.

        Given: Trace records with known latencies
        When: aggregate_metrics is called
        Then: P50, P95, P99 percentiles match expected values
        """
        # Create traces with predictable latencies
        base_time = datetime.utcnow()
        for i in range(100):
            latency = 50 + i  # 50-149ms range
            service.record_trace(
                trace_id=f"trace_{i}",
                template_id="percentile_test",
                template_version=1,
                rendered_prompt="test",
                input_variables={},
                context={},
                retrieved_docs=[],
                latency_ms=latency,
                total_latency_ms=latency * 2,
                success=True,
            )

        metrics = service.aggregate_metrics(
            template_id="percentile_test",
        )

        # Verify percentiles (based on total_latency_ms which is latency * 2)
        # total_latency_ms range: 100-298 (100 values)
        # P50 should be around 199ms (median of 100-298)
        assert 190 <= metrics.p50_latency_ms <= 205

        # P95 should be around 285ms
        assert 280 <= metrics.p95_latency_ms <= 290

        # P99 should be around 295ms
        assert 290 <= metrics.p99_latency_ms <= 298

    def test_aggregate_with_date_filter(
        self,
        service: TraceAnalysisService,
    ) -> None:
        """Test aggregation with date range filtering.

        Given: Traces spanning multiple time periods
        When: aggregate_metrics is called with date range
        Then: Only traces within range are included
        """
        base_time = datetime.utcnow()

        # Create traces at different times
        for i in range(10):
            trace_time = base_time - timedelta(hours=i)
            service.record_trace(
                trace_id=f"trace_{i}",
                template_id="date_test",
                template_version=1,
                rendered_prompt="test",
                input_variables={},
                context={},
                retrieved_docs=[],
                latency_ms=100,
                success=True,
                timestamp=trace_time,
            )

        # Filter to only recent traces (last 3 hours)
        start_date = base_time - timedelta(hours=3)
        end_date = base_time + timedelta(hours=1)

        metrics = service.aggregate_metrics(
            template_id="date_test",
            start_date=start_date,
            end_date=end_date,
        )

        # Should include traces from last 3 hours (indices 0, 1, 2, 3)
        # Note: trace 3 is exactly at the 3-hour boundary and is included (>=)
        assert metrics.total_count == 4

    def test_search_traces_with_filters(
        self,
        service: TraceAnalysisService,
        sample_traces: List[TraceRecord],
    ) -> None:
        """Test trace search with various filters.

        Given: A collection of trace records
        When: search_traces is called with different filters
        Then: Returns only matching traces
        """
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

        # Search by variant
        filter_params = TraceFilter(
            template_id="test_prompt",
            variant_id="variant_a",
            start_date=datetime.utcnow() - timedelta(hours=1),
            end_date=datetime.utcnow() + timedelta(minutes=1),
            offset=0,
            limit=100,
        )

        results = service.search_traces(filter_params)

        # Should only return variant_a traces (approximately 50%)
        assert len(results) == 50
        assert all(t.variant_id == "variant_a" for t in results)

    def test_search_success_only_filter(
        self,
        service: TraceAnalysisService,
    ) -> None:
        """Test search with success_only filter.

        Given: A mix of successful and failed traces
        When: search_traces is called with success_only=True
        Then: Returns only successful traces
        """
        base_time = datetime.utcnow()

        # Create mix of success/failure
        for i in range(20):
            service.record_trace(
                trace_id=f"trace_{i}",
                template_id="success_test",
                template_version=1,
                rendered_prompt="test",
                input_variables={},
                context={},
                retrieved_docs=[],
                success=(i % 2 == 0),  # Half success, half failure
            )

        filter_params = TraceFilter(
            template_id="success_test",
            start_date=base_time - timedelta(hours=1),
            end_date=base_time + timedelta(minutes=1),
            success_only=True,
            offset=0,
            limit=100,
        )

        results = service.search_traces(filter_params)

        # Should only return successful traces (approximately half)
        assert len(results) == 10
        assert all(t.success for t in results)

    def test_search_with_latency_filter(
        self,
        service: TraceAnalysisService,
    ) -> None:
        """Test search with latency filters.

        Given: Traces with varying latencies
        When: search_traces is called with min/max latency
        Then: Returns only traces within latency range
        """
        base_time = datetime.utcnow()

        # Create traces with different latencies
        for i in range(10):
            service.record_trace(
                trace_id=f"trace_{i}",
                template_id="latency_test",
                template_version=1,
                rendered_prompt="test",
                input_variables={},
                context={},
                retrieved_docs=[],
                total_latency_ms=100 + i * 50,  # 100-550ms
                success=True,
            )

        filter_params = TraceFilter(
            template_id="latency_test",
            start_date=base_time - timedelta(hours=1),
            end_date=base_time + timedelta(minutes=1),
            min_latency=200,
            max_latency=300,
            offset=0,
            limit=100,
        )

        results = service.search_traces(filter_params)

        # Should only return traces with latency 200-300ms
        # That's i=2 (200ms), i=3 (250ms), i=4 (300ms)
        # But 300 is inclusive, so it's included
        assert len(results) == 3
        assert all(200 <= t.total_latency_ms <= 300 for t in results)

    def test_search_pagination(
        self,
        service: TraceAnalysisService,
    ) -> None:
        """Test search with pagination.

        Given: Many trace records
        When: search_traces is called with offset and limit
        Then: Returns correct page of results
        """
        base_time = datetime.utcnow()

        # Create 25 traces
        for i in range(25):
            service.record_trace(
                trace_id=f"trace_{i}",
                template_id="pagination_test",
                template_version=1,
                rendered_prompt="test",
                input_variables={},
                context={},
                retrieved_docs=[],
                success=True,
            )

        # Get first page
        filter_params = TraceFilter(
            template_id="pagination_test",
            start_date=base_time - timedelta(hours=1),
            end_date=base_time + timedelta(minutes=1),
            offset=0,
            limit=10,
        )

        page1 = service.search_traces(filter_params)
        assert len(page1) == 10

        # Get second page
        filter_params.offset = 10
        page2 = service.search_traces(filter_params)
        assert len(page2) == 10

        # Get third page
        filter_params.offset = 20
        page3 = service.search_traces(filter_params)
        assert len(page3) == 5

    def test_get_insights_error_detection(
        self,
        service: TraceAnalysisService,
    ) -> None:
        """Test that insights detect error patterns.

        Given: Traces with high error rate
        When: get_insights is called
        Then: Returns insight about high error rate
        """
        base_time = datetime.utcnow()

        # Create traces with 20% error rate (above 10% threshold)
        for i in range(100):
            service.record_trace(
                trace_id=f"trace_{i}",
                template_id="insight_test",
                template_version=1,
                rendered_prompt="test",
                input_variables={},
                context={},
                retrieved_docs=[],
                success=(i % 5 != 0),  # 20% failure rate
            )

        insights = service.get_insights("insight_test")

        # Should have error insight
        assert len(insights) > 0

        error_insight = next(
            (i for i in insights if i.insight_type == "error"),
            None
        )
        assert error_insight is not None
        assert "error rate" in error_insight.title.lower()

    def test_get_insights_performance_detection(
        self,
        service: TraceAnalysisService,
    ) -> None:
        """Test that insights detect performance issues.

        Given: Traces with slow performance
        When: get_insights is called
        Then: Returns insight about slow performance
        """
        base_time = datetime.utcnow()

        # Create slow traces (P95 > 5000ms)
        for i in range(10):
            service.record_trace(
                trace_id=f"trace_{i}",
                template_id="slow_test",
                template_version=1,
                rendered_prompt="test",
                input_variables={},
                context={},
                retrieved_docs=[],
                total_latency_ms=6000 + i * 1000,  # 6000-15000ms
                success=True,
            )

        insights = service.get_insights("slow_test")

        # Should have performance insight
        perf_insight = next(
            (i for i in insights if i.insight_type == "performance"),
            None
        )
        assert perf_insight is not None

    def test_update_trace(
        self,
        service: TraceAnalysisService,
    ) -> None:
        """Test updating an existing trace.

        Given: A trace record
        When: update_trace is called with new values
        Then: Trace is updated with new values
        """
        # Create a trace
        trace_id = "update_test_trace"
        service.record_trace(
            trace_id=trace_id,
            template_id="update_test",
            template_version=1,
            rendered_prompt="original",
            input_variables={},
            context={},
            retrieved_docs=[],
        )

        # Update the trace
        updated = service.update_trace(
            trace_id=trace_id,
            model_output="Updated output",
            total_latency_ms=250.0,
            success=True,
            user_feedback="Good result",
            user_rating=5,
        )

        assert updated is not None
        assert updated.model_output == "Updated output"
        assert updated.total_latency_ms == 250.0
        assert updated.user_feedback == "Good result"
        assert updated.user_rating == 5

    def test_update_nonexistent_trace(
        self,
        service: TraceAnalysisService,
    ) -> None:
        """Test updating a non-existent trace.

        Given: No trace exists
        When: update_trace is called with non-existent trace_id
        Then: Returns None
        """
        result = service.update_trace(
            trace_id="nonexistent_trace",
            model_output="test",
        )

        assert result is None

    def test_max_traces_limit(
        self,
        service: TraceAnalysisService,
    ) -> None:
        """Test that service respects max_traces limit.

        Given: A service with max_traces=100
        When: More than 100 traces are recorded
        Then: Only keeps the most recent 100 traces
        """
        # Create service with small limit
        reset_trace_analysis_service()
        limited_service = TraceAnalysisService(max_traces=50)

        # Record more than limit
        for i in range(100):
            limited_service.record_trace(
                trace_id=f"trace_{i}",
                template_id="limit_test",
                template_version=1,
                rendered_prompt="test",
                input_variables={},
                context={},
                retrieved_docs=[],
            )

        # Get all traces (should be limited to 50)
        filter_params = TraceFilter(
            template_id="limit_test",
            start_date=datetime.utcnow() - timedelta(hours=1),
            end_date=datetime.utcnow() + timedelta(minutes=1),
            offset=0,
            limit=200,
        )

        results = limited_service.search_traces(filter_params)

        # Should have at most 50 traces
        assert len(results) <= 50

    def test_aggregate_metrics_with_no_data(
        self,
        service: TraceAnalysisService,
    ) -> None:
        """Test aggregation when no traces exist.

        Given: No trace records for a template
        When: aggregate_metrics is called
        Then: Returns zero metrics
        """
        metrics = service.aggregate_metrics(
            template_id="nonexistent_template",
        )

        assert metrics.total_count == 0
        assert metrics.success_count == 0
        assert metrics.error_count == 0
        assert metrics.success_rate == 1.0  # Default to 100% when no data
        assert metrics.avg_latency_ms == 0.0
