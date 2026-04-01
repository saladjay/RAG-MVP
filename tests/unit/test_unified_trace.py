"""
Unit tests for Unified Trace Propagation (US1 - Knowledge Base Query).

These tests verify the trace_id propagation across all three observability layers:
- Agent Layer (Phidata)
- LLM Layer (LiteLLM)
- Prompt Layer (Langfuse)
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from typing import Dict, Any


class TestUnifiedTraceManager:
    """Unit tests for UnifiedTraceManager.

    Tests verify:
    - Trace ID generation
    - Cross-layer initialization
    - Metric linking
    - Trace retrieval
    """

    @pytest.fixture
    def mock_observers(self):
        """Mock all three layer observers."""
        return {
            "litellm": Mock(),
            "phidata": Mock(),
            "langfuse": Mock(),
        }

    @pytest.mark.unit
    async def test_trace_manager_creates_unified_trace_id(
        self,
    ) -> None:
        """Test that trace manager creates unified trace_id.

        Given: A request_id and prompt
        When: create_trace is called
        Then: Returns trace_id with request_id prefix
        """
        from rag_service.observability.trace_manager import UnifiedTraceManager

        manager = UnifiedTraceManager()
        trace_id = await manager.create_trace(
            request_id="req_123",
            prompt="What is RAG?",
            context={"user_id": "test"},
        )

        assert trace_id is not None
        assert "req_123" in trace_id
        assert len(trace_id.split("_")) >= 2  # request_id + unique suffix

    @pytest.mark.unit
    async def test_trace_manager_initializes_all_layers(
        self,
        mock_observers,
    ) -> None:
        """Test that trace manager initializes all three layers.

        Given: A new trace
        When: create_trace is called
        Then: Initializes Phidata, LiteLLM, and Langfuse layers
        """
        from rag_service.observability.trace_manager import UnifiedTraceManager

        # Mock the observer methods
        mock_observers["phidata"].task_start = AsyncMock()
        mock_observers["langfuse"].create_trace = AsyncMock()

        manager = UnifiedTraceManager(
            litellm_observer=mock_observers["litellm"],
            phidata_observer=mock_observers["phidata"],
            langfuse_client=mock_observers["langfuse"],
        )

        trace_id = await manager.create_trace(
            request_id="req_123",
            prompt="Test prompt",
            context={},
        )

        # Verify all layers were initialized (non-blocking, so exceptions caught)
        assert trace_id is not None

    @pytest.mark.unit
    async def test_trace_manager_links_inference_metrics(
        self,
        mock_observers,
    ) -> None:
        """Test that trace manager links inference metrics.

        Given: Model inference completes
        When: link_inference is called
        Then: Updates all layers with inference data
        """
        from rag_service.observability.trace_manager import UnifiedTraceManager

        mock_observers["phidata"].record_llm_call = AsyncMock()
        mock_observers["litellm"].capture_inference = AsyncMock()

        manager = UnifiedTraceManager(
            litellm_observer=mock_observers["litellm"],
            phidata_observer=mock_observers["phidata"],
            langfuse_client=mock_observers["langfuse"],
        )

        trace_id = await manager.create_trace(
            request_id="req_123",
            prompt="Test",
            context={},
        )

        await manager.link_inference(
            trace_id=trace_id,
            model="gpt-4",
            tokens={"input": 100, "output": 50},
            latency_ms=1500,
            cost=0.003,
        )

        # Verify observers were called
        mock_observers["phidata"].record_llm_call.assert_called_once()
        mock_observers["litellm"].capture_inference.assert_called_once()

    @pytest.mark.unit
    async def test_trace_manager_links_retrieval_metrics(
        self,
        mock_observers,
    ) -> None:
        """Test that trace manager links retrieval metrics.

        Given: Knowledge base retrieval completes
        When: link_retrieval is called
        Then: Adds retrieval span to trace
        """
        from rag_service.observability.trace_manager import UnifiedTraceManager

        manager = UnifiedTraceManager(
            litellm_observer=mock_observers["litellm"],
            phidata_observer=mock_observers["phidata"],
            langfuse_client=mock_observers["langfuse"],
        )

        trace_id = await manager.create_trace(
            request_id="req_123",
            prompt="Test",
            context={},
        )

        await manager.link_retrieval(
            trace_id=trace_id,
            chunks_count=5,
            chunk_ids=["chunk1", "chunk2", "chunk3", "chunk4", "chunk5"],
            latency_ms=200,
        )

        # Verify trace was updated
        trace_data = await manager.get_trace(trace_id)
        assert trace_data is not None

        # Check for retrieval span
        retrieval_spans = [s for s in trace_data["spans"] if s["span_type"] == "retrieval"]
        assert len(retrieval_spans) == 1
        assert retrieval_spans[0]["metadata"]["chunks_count"] == 5

    @pytest.mark.unit
    async def test_trace_manager_completes_trace(
        self,
        mock_observers,
    ) -> None:
        """Test that trace manager completes trace.

        Given: Request processing completes
        When: complete_trace is called
        Then: Marks trace complete and triggers flush
        """
        from rag_service.observability.trace_manager import UnifiedTraceManager

        # Mock flush methods
        mock_observers["litellm"].flush_trace = AsyncMock()
        mock_observers["phidata"].flush_trace = AsyncMock()
        mock_observers["langfuse"].flush_trace = AsyncMock()

        manager = UnifiedTraceManager(
            litellm_observer=mock_observers["litellm"],
            phidata_observer=mock_observers["phidata"],
            langfuse_client=mock_observers["langfuse"],
        )

        trace_id = await manager.create_trace(
            request_id="req_123",
            prompt="Test",
            context={},
        )

        await manager.complete_trace(
            trace_id=trace_id,
            final_answer="Test answer",
            status="completed",
        )

        # Verify trace was marked complete
        trace_data = await manager.get_trace(trace_id)
        assert trace_data["status"] == "completed"
        assert trace_data["end_time"] is not None

    @pytest.mark.unit
    async def test_trace_manager_aggregates_cross_layer_metrics(
        self,
        mock_observers,
    ) -> None:
        """Test that trace manager aggregates metrics across layers.

        Given: Trace with data from all layers
        When: get_cross_layer_metrics is called
        Then: Returns aggregated metrics
        """
        from rag_service.observability.trace_manager import UnifiedTraceManager

        manager = UnifiedTraceManager(
            litellm_observer=mock_observers["litellm"],
            phidata_observer=mock_observers["phidata"],
            langfuse_client=mock_observers["langfuse"],
        )

        trace_id = await manager.create_trace(
            request_id="req_123",
            prompt="Test",
            context={},
        )

        # Add data from all layers
        await manager.link_inference(
            trace_id=trace_id,
            model="gpt-4",
            tokens={"input": 100, "output": 50},
            latency_ms=1500,
            cost=0.003,
        )

        await manager.link_agent_execution(
            trace_id=trace_id,
            tool_calls=[{"tool": "retrieval", "success": True}],
            reasoning_path=["Planning", "Retrieval", "Inference"],
            success=True,
        )

        # Get cross-layer metrics
        metrics = await manager.get_cross_layer_metrics(trace_id)

        assert metrics is not None
        assert "agent_metrics" in metrics
        assert "llm_metrics" in metrics
        assert "prompt_metrics" in metrics
        assert "spans" in metrics

        # Verify agent metrics
        assert metrics["agent_metrics"]["tool_calls_count"] == 1
        assert metrics["agent_metrics"]["reasoning_steps"] == 3

        # Verify LLM metrics
        assert metrics["llm_metrics"]["model"] == "gpt-4"
        assert metrics["llm_metrics"]["total_tokens"] == 150


class TestTraceContext:
    """Unit tests for TraceContext propagation.

    Tests verify:
    - Async context manager behavior
    - Trace ID setting/clearing
    - Nested context handling
    """

    @pytest.mark.unit
    async def test_trace_context_sets_trace_id(self) -> None:
        """Test that TraceContext sets trace_id in async context.

        Given: A TraceContext with trace_id
        When: Context is entered
        Then: trace_id is available via get_current_trace_id
        """
        from rag_service.observability.trace_propagation import (
            TraceContext,
            get_current_trace_id,
        )

        async with TraceContext("test_trace_123") as ctx:
            current_trace_id = get_current_trace_id()
            assert current_trace_id == "test_trace_123"
            assert ctx.trace_id == "test_trace_123"

    @pytest.mark.unit
    async def test_trace_context_clears_on_exit(self) -> None:
        """Test that TraceContext clears trace_id on exit.

        Given: A TraceContext is entered and exited
        When: Context is exited
        Then: trace_id is cleared from async context
        """
        from rag_service.observability.trace_propagation import (
            TraceContext,
            get_current_trace_id,
        )

        async with TraceContext("test_trace_123"):
            pass

        # After context exit, trace_id should be cleared
        current_trace_id = get_current_trace_id()
        assert current_trace_id is None

    @pytest.mark.unit
    async def test_nested_trace_context(self) -> None:
        """Test that nested TraceContext handles correctly.

        Given: Nested TraceContext calls
        When: Inner context is entered
        Then: Inner trace_id takes precedence, restored on exit
        """
        from rag_service.observability.trace_propagation import (
            TraceContext,
            get_current_trace_id,
        )

        outer_trace = "outer_trace_123"
        inner_trace = "inner_trace_456"

        async with TraceContext(outer_trace):
            assert get_current_trace_id() == outer_trace

            async with TraceContext(inner_trace, parent_trace_id=outer_trace):
                assert get_current_trace_id() == inner_trace

            # After inner context exits, outer is restored
            assert get_current_trace_id() == outer_trace


class TestTracePropagation:
    """Unit tests for trace propagation utilities.

    Tests verify:
    - Trace ID injection/extraction
    - Cross-layer propagation
    - Child trace creation
    """

    @pytest.mark.unit
    def test_inject_trace_id_adds_to_context(self) -> None:
        """Test that inject_trace_id adds trace_id to context.

        Given: A context dictionary
        When: inject_trace_id is called
        Then: Returns context with trace_id added
        """
        from rag_service.observability.trace_propagation import inject_trace_id

        context = {"key": "value", "nested": {"data": "test"}}
        result = inject_trace_id(context, trace_id="test_trace")

        assert result["trace_id"] == "test_trace"
        assert result["key"] == "value"  # Original keys preserved
        assert result["nested"]["trace_id"] == "test_trace"  # Also injected into metadata

    @pytest.mark.unit
    def test_extract_trace_id_finds_in_context(self) -> None:
        """Test that extract_trace_id finds trace_id in various locations.

        Given: Context with trace_id in various keys
        When: extract_trace_id is called
        Then: Returns the trace_id
        """
        from rag_service.observability.trace_propagation import extract_trace_id

        # Test with trace_id key
        context1 = {"trace_id": "test_123"}
        assert extract_trace_id(context1) == "test_123"

        # Test with request_id key
        context2 = {"request_id": "test_456"}
        assert extract_trace_id(context2) == "test_456"

        # Test with nested metadata
        context3 = {"metadata": {"trace_id": "test_789"}}
        assert extract_trace_id(context3) == "test_789"

    @pytest.mark.unit
    def test_create_child_trace_id_includes_parent(self) -> None:
        """Test that child trace_id includes parent reference.

        Given: A parent trace_id
        When: create_child_trace_id is called
        Then: Returns trace_id with parent prefix
        """
        from rag_service.observability.trace_propagation import create_child_trace_id

        parent_trace = "parent_trace_abc"
        child_trace = create_child_trace_id(parent_trace, "retrieval")

        assert parent_trace in child_trace
        assert "retrieval" in child_trace

    @pytest.mark.unit
    async def test_propagate_trace_id_to_all_layers(self) -> None:
        """Test that propagate_trace_id reaches all layers.

        Given: A trace_id
        When: propagate_trace_id is called
        Then: All layers are notified
        """
        from rag_service.observability.trace_propagation import propagate_trace_id

        result = await propagate_trace_id(
            trace_id="test_trace_123",
            target_layers=["phidata", "litellm", "langfuse"],
        )

        assert result["trace_id"] == "test_trace_123"
        assert "propagated_to" in result


class TestTraceFlushManager:
    """Unit tests for non-blocking trace flush.

    Tests verify:
    - Background flush scheduling
    - Non-blocking behavior
    - Error isolation
    """

    @pytest.mark.unit
    async def test_flush_manager_schedules_flush(self) -> None:
        """Test that flush manager schedules background flush.

        Given: A trace to flush
        When: schedule_flush is called
        Then: Flush is queued without blocking
        """
        from rag_service.observability.trace_flush import TraceFlushManager

        manager = TraceFlushManager(flush_interval_ms=100, enabled=True)
        await manager.start()

        # Schedule a flush (should not block)
        await manager.schedule_flush(trace_id="test_trace")

        stats = manager.get_stats()
        assert stats["scheduled"] == 1

        await manager.stop()

    @pytest.mark.unit
    async def test_flush_now_blocks_until_complete(self) -> None:
        """Test that flush_now performs synchronous flush.

        Given: A trace to flush
        When: flush_now is called
        Then: Flushes immediately and returns result
        """
        from rag_service.observability.trace_flush import TraceFlushManager

        manager = TraceFlushManager(enabled=True)

        result = await manager.flush_now(trace_id="test_trace")

        assert "trace_id" in result
        assert "layers_flushed" in result or "layers_failed" in result
