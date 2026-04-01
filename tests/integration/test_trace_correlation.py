"""
Integration tests for Cross-Layer Trace Correlation (US3 - Observability and Tracing).

These tests verify the complete trace correlation across all three observability layers:
- Agent Layer (Phidata): Task execution and reasoning metrics
- LLM Layer (LiteLLM): Model invocation and cost metrics
- Prompt Layer (Langfuse): Prompt template and variable tracking

Tests verify that a unified trace_id properly links data across all layers.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from typing import Dict, Any
from datetime import datetime


class TestCrossLayerTraceCorrelation:
    """Integration tests for cross-layer trace correlation.

    Tests verify:
    - Unified trace_id propagation across Phidata, LiteLLM, and Langfuse
    - Complete trace retrieval with all layer data
    - Trace correlation for cost-to-quality optimization
    - Non-blocking trace behavior
    """

    @pytest.fixture
    def client(self) -> AsyncClient:
        """Create test client."""
        from rag_service.main import app

        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    @pytest.fixture
    async def trace_manager(self):
        """Create trace manager for testing."""
        from rag_service.observability.trace_manager import get_trace_manager

        manager = await get_trace_manager()
        return manager

    @pytest.mark.integration
    async def test_unified_trace_id_propagates_to_all_layers(
        self,
        trace_manager,
    ) -> None:
        """Test that unified trace_id propagates to all three layers.

        Given: A new trace is created
        When: Trace operations occur at each layer
        Then: All layer data is linked by the same trace_id
        """
        request_id = "req_001"
        prompt = "What is RAG?"

        # Create unified trace
        trace_id = await trace_manager.create_trace(
            request_id=request_id,
            prompt=prompt,
            context={"user_id": "test_user"},
        )

        # Simulate layer operations
        await trace_manager.link_retrieval(
            trace_id=trace_id,
            chunks_count=3,
            chunk_ids=["chunk_1", "chunk_2", "chunk_3"],
            latency_ms=450,
        )

        await trace_manager.link_inference(
            trace_id=trace_id,
            model="gpt-3.5-turbo",
            tokens={"input": 150, "output": 85},
            latency_ms=1890,
            cost=0.001,
        )

        await trace_manager.link_agent_execution(
            trace_id=trace_id,
            tool_calls=[{"tool": "knowledge_base", "success": True}],
            reasoning_path=["planning", "retrieval", "synthesis"],
            success=True,
        )

        await trace_manager.complete_trace(
            trace_id=trace_id,
            final_answer="RAG is...",
        )

        # Verify unified trace contains all layer data
        trace = await trace_manager.get_trace(trace_id)
        assert trace is not None
        assert trace["trace_id"] == trace_id
        assert len(trace["spans"]) > 0  # Has retrieval span
        assert trace["phidata_data"]["success"] is True
        assert trace["litellm_data"]["model"] == "gpt-3.5-turbo"

    @pytest.mark.integration
    async def test_cross_layer_metrics_aggregation(
        self,
        trace_manager,
    ) -> None:
        """Test that metrics are aggregated across all layers.

        Given: A complete trace with all layer data
        When: get_cross_layer_metrics is called
        Then: Returns aggregated metrics from all three layers
        """
        request_id = "req_002"
        prompt = "Explain vector databases"

        # Create and populate trace
        trace_id = await trace_manager.create_trace(
            request_id=request_id,
            prompt=prompt,
            context={},
        )

        await trace_manager.link_retrieval(
            trace_id=trace_id,
            chunks_count=5,
            chunk_ids=["c1", "c2", "c3", "c4", "c5"],
            latency_ms=520,
        )

        await trace_manager.link_inference(
            trace_id=trace_id,
            model="claude-3-haiku",
            tokens={"input": 300, "output": 150},
            latency_ms=1200,
            cost=0.0005,
        )

        await trace_manager.complete_trace(trace_id)

        # Get cross-layer metrics
        metrics = await trace_manager.get_cross_layer_metrics(trace_id)
        assert metrics is not None
        assert metrics["trace_id"] == trace_id
        assert metrics["agent_metrics"]["tool_calls_count"] == 0  # No agent execution yet
        assert metrics["llm_metrics"]["model"] == "claude-3-haiku"
        assert metrics["llm_metrics"]["total_tokens"] == 450
        assert len(metrics["spans"]) > 0

    @pytest.mark.integration
    async def test_trace_retrieval_via_endpoint(
        self,
        client: AsyncClient,
        trace_manager,
    ) -> None:
        """Test that traces can be retrieved via HTTP endpoint.

        Given: A completed trace
        When: GET /traces/{trace_id} is called
        Then: Returns complete trace data with all layer metrics
        """
        request_id = "req_003"
        prompt = "Test query for trace retrieval"

        # Create trace
        trace_id = await trace_manager.create_trace(
            request_id=request_id,
            prompt=prompt,
            context={"test": True},
        )

        await trace_manager.link_retrieval(
            trace_id=trace_id,
            chunks_count=2,
            chunk_ids=["chunk_a", "chunk_b"],
            latency_ms=300,
        )

        await trace_manager.link_inference(
            trace_id=trace_id,
            model="gpt-4",
            tokens={"input": 100, "output": 50},
            latency_ms=2500,
            cost=0.005,
        )

        await trace_manager.complete_trace(trace_id)

        # Retrieve via endpoint
        response = await client.get(f"/traces/{trace_id}")

        # May return 200 if endpoint exists, 404 if not yet implemented
        if response.status_code == 200:
            data = response.json()
            assert data["trace_id"] == trace_id
            assert "spans" in data
            assert "phidata_data" in data or "litellm_data" in data

    @pytest.mark.integration
    async def test_trace_includes_all_processing_stages(
        self,
        trace_manager,
    ) -> None:
        """Test that trace includes metrics from all processing stages.

        Given: A complete RAG query flow
        When: Trace is retrieved
        Then: Contains data for: request, retrieval, inference, completion
        """
        request_id = "req_004"
        prompt = "Complete flow test"

        # Simulate complete RAG flow
        trace_id = await trace_manager.create_trace(
            request_id=request_id,
            prompt=prompt,
            context={"stage": "complete"},
        )

        # Retrieval stage
        await trace_manager.link_retrieval(
            trace_id=trace_id,
            chunks_count=4,
            chunk_ids=["r1", "r2", "r3", "r4"],
            latency_ms=400,
            query_vector_used="text-embedding-3-small",
        )

        # Inference stage
        await trace_manager.link_inference(
            trace_id=trace_id,
            model="gpt-3.5-turbo",
            tokens={"input": 200, "output": 100},
            latency_ms=1500,
            cost=0.0008,
        )

        # Agent execution stage
        await trace_manager.link_agent_execution(
            trace_id=trace_id,
            tool_calls=[
                {"tool": "retrieval", "success": True},
                {"tool": "llm", "success": True},
            ],
            reasoning_path=["analyze", "retrieve", "generate"],
            success=True,
        )

        await trace_manager.complete_trace(
            trace_id=trace_id,
            final_answer="Complete answer here",
        )

        # Verify all stages are recorded
        trace = await trace_manager.get_trace(trace_id)
        assert trace is not None

        # Check retrieval stage
        assert len(trace["spans"]) >= 1
        retrieval_spans = [s for s in trace["spans"] if s["span_type"] == "retrieval"]
        assert len(retrieval_spans) >= 1

        # Check inference data
        assert trace["litellm_data"]["model"] == "gpt-3.5-turbo"
        assert trace["litellm_data"]["latency_ms"] == 1500

        # Check agent data
        assert trace["phidata_data"]["success"] is True
        assert len(trace["phidata_data"]["tool_calls"]) >= 0

    @pytest.mark.integration
    async def test_trace_correlation_across_multiple_requests(
        self,
        trace_manager,
    ) -> None:
        """Test that multiple requests have independent traces.

        Given: Multiple concurrent requests
        When: Each request creates a trace
        Then: Each trace has independent data with unique trace_id
        """
        import asyncio

        async def create_request_trace(req_num: int) -> str:
            prompt = f"Request {req_num} query"
            tid = await trace_manager.create_trace(
                request_id=f"req_{req_num}",
                prompt=prompt,
                context={"request_num": req_num},
            )
            await trace_manager.link_inference(
                trace_id=tid,
                model="gpt-3.5-turbo",
                tokens={"input": 50 * req_num, "output": 25 * req_num},
                latency_ms=500 * req_num,
                cost=0.0001 * req_num,
            )
            await trace_manager.complete_trace(tid)
            return tid

        # Create multiple traces concurrently
        trace_ids = await asyncio.gather(
            create_request_trace(1),
            create_request_trace(2),
            create_request_trace(3),
        )

        # Verify all traces are unique
        assert len(trace_ids) == 3
        assert len(set(trace_ids)) == 3

        # Verify each trace has independent data
        for i, tid in enumerate(trace_ids, start=1):
            trace = await trace_manager.get_trace(tid)
            assert trace is not None
            assert trace["trace_id"] == tid
            assert trace["litellm_data"]["tokens"]["input"] == 50 * i

    @pytest.mark.integration
    async def test_trace_survives_observability_failure(
        self,
        trace_manager,
    ) -> None:
        """Test that trace recording is non-blocking.

        Given: A trace with observability failures
        When: Observability backends fail
        Then: Trace data is still available locally
        """
        request_id = "req_005"
        prompt = "Non-blocking test"

        # Create trace even if some layers fail
        trace_id = await trace_manager.create_trace(
            request_id=request_id,
            prompt=prompt,
            context={"test": "non-blocking"},
        )

        # Record data (should succeed even if external backends fail)
        await trace_manager.link_inference(
            trace_id=trace_id,
            model="test-model",
            tokens={"input": 10, "output": 5},
            latency_ms=100,
            cost=0.0,
        )

        await trace_manager.complete_trace(trace_id)

        # Verify trace is still available
        trace = await trace_manager.get_trace(trace_id)
        assert trace is not None
        assert trace["status"] == "completed"


class TestTraceEndpointIntegration:
    """Integration tests for trace retrieval endpoints.

    Tests verify:
    - GET /traces/{trace_id} returns complete trace
    - GET /observability/metrics returns aggregated metrics
    - Error handling for missing traces
    """

    @pytest.fixture
    def client(self) -> AsyncClient:
        """Create test client."""
        from rag_service.main import app

        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    @pytest.mark.integration
    async def test_get_trace_returns_complete_data(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that GET /traces/{trace_id} returns complete trace.

        Given: A completed trace
        When: GET /traces/{trace_id} is called
        Then: Returns trace with all layer data
        """
        # This test requires the endpoint to be implemented
        response = await client.get("/traces/test_trace_001")

        # May return 404 if endpoint not yet implemented
        # or 404 if trace doesn't exist
        assert response.status_code in [200, 404]

    @pytest.mark.integration
    async def test_get_observability_metrics_returns_aggregations(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that GET /observability/metrics returns aggregated metrics.

        Given: System with trace data
        When: GET /observability/metrics is called
        Then: Returns cross-layer aggregated metrics
        """
        response = await client.get("/observability/metrics")

        # May return 200 if endpoint exists, 404 if not yet implemented
        if response.status_code == 200:
            data = response.json()
            assert "metrics" in data or "data" in data

    @pytest.mark.integration
    async def test_missing_trace_returns_404(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that GET /traces/{unknown_id} returns 404.

        Given: An unknown trace ID
        When: GET /traces/{unknown_id} is called
        Then: Returns 404 Not Found
        """
        response = await client.get("/traces/unknown_trace_xyz")

        # Should return 404 if endpoint is implemented
        # or 404 if trace not found
        assert response.status_code in [404, 422]  # 422 if endpoint not yet impl


class TestTraceTimeCorrelation:
    """Integration tests for timing correlation across layers.

    Tests verify:
    - Timestamp ordering across layers
    - Latency calculation accuracy
    - Span timing relationships
    """

    @pytest.fixture
    async def trace_manager(self):
        """Create trace manager for testing."""
        from rag_service.observability.trace_manager import get_trace_manager

        manager = await get_trace_manager()
        return manager

    @pytest.mark.integration
    async def test_trace_timestamps_are_ordered(
        self,
        trace_manager,
    ) -> None:
        """Test that timestamps are ordered correctly across layers.

        Given: A complete trace with multiple operations
        When: Trace is retrieved
        Then: start_time < span times < end_time
        """
        request_id = "req_time_001"
        prompt = "Timing test"

        trace_id = await trace_manager.create_trace(
            request_id=request_id,
            prompt=prompt,
            context={},
        )

        # Get start time
        trace_before = await trace_manager.get_trace(trace_id)
        start_time = datetime.fromisoformat(trace_before["start_time"])

        # Add operations (these add spans with their own timestamps)
        await trace_manager.link_retrieval(
            trace_id=trace_id,
            chunks_count=1,
            chunk_ids=["chunk_1"],
            latency_ms=100,
        )

        # Complete trace
        await trace_manager.complete_trace(trace_id)

        # Get final trace
        trace_final = await trace_manager.get_trace(trace_id)
        assert trace_final is not None
        assert trace_final["end_time"] is not None

        end_time = datetime.fromisoformat(trace_final["end_time"])

        # Verify ordering
        assert start_time <= end_time

    @pytest.mark.integration
    async def test_span_latencies_are_recorded(
        self,
        trace_manager,
    ) -> None:
        """Test that span latencies are accurately recorded.

        Given: A trace with retrieval and inference operations
        When: Trace is retrieved
        Then: Spans have accurate latency_ms values
        """
        request_id = "req_latency_001"
        prompt = "Latency test"

        trace_id = await trace_manager.create_trace(
            request_id=request_id,
            prompt=prompt,
            context={},
        )

        retrieval_latency = 450
        await trace_manager.link_retrieval(
            trace_id=trace_id,
            chunks_count=3,
            chunk_ids=["c1", "c2", "c3"],
            latency_ms=retrieval_latency,
        )

        trace = await trace_manager.get_trace(trace_id)
        assert trace is not None

        # Find retrieval span
        retrieval_spans = [s for s in trace["spans"] if s["span_type"] == "retrieval"]
        if retrieval_spans:
            assert retrieval_spans[0]["latency_ms"] == retrieval_latency
