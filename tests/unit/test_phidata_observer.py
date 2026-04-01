"""
Unit tests for Phidata Observer (US3 - Observability and Tracing).

These tests verify the Agent Layer observer functionality including:
- Task execution tracking
- Tool call recording
- Reasoning path capture
- Agent execution metrics
"""

import pytest
from datetime import datetime
from typing import Dict, Any


class TestPhidataObserverTaskTracking:
    """Unit tests for Phidata observer task tracking.

    Tests verify:
    - Task initialization
    - Task completion
    - Task retrieval
    """

    @pytest.fixture
    async def observer(self):
        """Create Phidata observer for testing."""
        from rag_service.observability.phidata_observer import PhidataObserver

        # Reset any existing observer
        from rag_service.observability.phidata_observer import reset_phidata_observer
        reset_phidata_observer()

        observer = PhidataObserver()
        return observer

    @pytest.mark.unit
    async def test_task_start_creates_execution_record(
        self,
        observer,
    ) -> None:
        """Test that task_start creates a new execution record.

        Given: A trace_id and request_id
        When: task_start is called
        Then: Execution record is created with correct metadata
        """
        trace_id = "trace_task_001"
        request_id = "req_001"

        await observer.task_start(
            trace_id=trace_id,
            request_id=request_id,
            task_name="test-task",
        )

        execution = await observer.get_execution(trace_id)
        assert execution is not None
        assert execution["trace_id"] == trace_id
        assert execution["request_id"] == request_id
        assert execution["task_name"] == "test-task"
        assert execution["status"] == "running"

    @pytest.mark.unit
    async def test_task_start_sets_default_task_name(
        self,
        observer,
    ) -> None:
        """Test that task_start uses default task name.

        Given: A trace_id without task_name
        When: task_start is called without task_name
        Then: Uses "rag-task" as default
        """
        trace_id = "trace_task_002"

        await observer.task_start(
            trace_id=trace_id,
            request_id="req_002",
        )

        execution = await observer.get_execution(trace_id)
        assert execution["task_name"] == "rag-task"

    @pytest.mark.unit
    async def test_get_execution_returns_none_for_unknown(
        self,
        observer,
    ) -> None:
        """Test that get_execution returns None for unknown trace.

        Given: An unknown trace_id
        When: get_execution is called
        Then: Returns None
        """
        execution = await observer.get_execution("unknown_trace")
        assert execution is None


class TestPhidataObserverToolCallTracking:
    """Unit tests for Phidata observer tool call tracking.

    Tests verify:
    - Tool call recording
    - Tool call success/failure
    - Tool call metrics aggregation
    - Tool call retrieval
    """

    @pytest.fixture
    async def observer(self):
        """Create Phidata observer for testing."""
        from rag_service.observability.phidata_observer import PhidataObserver

        observer = PhidataObserver()
        return observer

    @pytest.mark.unit
    async def test_record_tool_call_stores_tool_data(
        self,
        observer,
    ) -> None:
        """Test that record_tool_call stores tool invocation data.

        Given: A tool call with input and output
        When: record_tool_call is called
        Then: Tool call is stored with correct data
        """
        trace_id = "trace_tool_001"

        await observer.task_start(trace_id=trace_id, request_id="req_001")

        await observer.record_tool_call(
            trace_id=trace_id,
            tool_name="knowledge_base",
            input_data={"query": "test query"},
            output_data={"chunks": ["chunk1", "chunk2"]},
            latency_ms=150,
            success=True,
        )

        tool_calls = await observer.get_tool_calls(trace_id)
        assert len(tool_calls) == 1
        assert tool_calls[0]["tool_name"] == "knowledge_base"
        assert tool_calls[0]["success"] is True
        assert tool_calls[0]["latency_ms"] == 150

    @pytest.mark.unit
    async def test_record_tool_call_handles_failure(
        self,
        observer,
    ) -> None:
        """Test that record_tool_call records failures.

        Given: A tool call that fails
        When: record_tool_call is called with success=False
        Then: Error message is recorded
        """
        trace_id = "trace_tool_002"

        await observer.task_start(trace_id=trace_id, request_id="req_002")

        await observer.record_tool_call(
            trace_id=trace_id,
            tool_name="retrieval",
            input_data={"query": "test"},
            success=False,
            error_message="Connection timeout",
        )

        tool_calls = await observer.get_tool_calls(trace_id)
        assert len(tool_calls) == 1
        assert tool_calls[0]["success"] is False
        assert tool_calls[0]["error_message"] == "Connection timeout"

    @pytest.mark.unit
    async def test_record_multiple_tool_calls(
        self,
        observer,
    ) -> None:
        """Test that multiple tool calls are recorded.

        Given: Multiple tool calls in sequence
        When: record_tool_call is called multiple times
        Then: All tool calls are recorded in order
        """
        trace_id = "trace_tool_003"

        await observer.task_start(trace_id=trace_id, request_id="req_003")

        await observer.record_tool_call(
            trace_id=trace_id,
            tool_name="tool1",
            input_data={},
            latency_ms=100,
        )

        await observer.record_tool_call(
            trace_id=trace_id,
            tool_name="tool2",
            input_data={},
            latency_ms=200,
        )

        tool_calls = await observer.get_tool_calls(trace_id)
        assert len(tool_calls) == 2
        assert tool_calls[0]["tool_name"] == "tool1"
        assert tool_calls[1]["tool_name"] == "tool2"

    @pytest.mark.unit
    async def test_get_tool_calls_returns_empty_for_unknown_trace(
        self,
        observer,
    ) -> None:
        """Test that get_tool_calls returns empty list for unknown trace.

        Given: An unknown trace_id
        When: get_tool_calls is called
        Then: Returns empty list
        """
        tool_calls = await observer.get_tool_calls("unknown_trace")
        assert tool_calls == []

    @pytest.mark.unit
    async def test_get_tool_metrics_aggregates_by_tool(
        self,
        observer,
    ) -> None:
        """Test that get_tool_metrics returns aggregated metrics.

        Given: Multiple calls to the same tool
        When: get_tool_metrics is called
        Then: Returns aggregated metrics (count, success_rate, avg_latency)
        """
        tool_name = "knowledge_base"
        trace_id = "trace_metrics_001"

        await observer.task_start(trace_id=trace_id, request_id="req_001")

        # Record multiple tool calls
        await observer.record_tool_call(
            trace_id=trace_id,
            tool_name=tool_name,
            input_data={},
            latency_ms=100,
            success=True,
        )

        await observer.record_tool_call(
            trace_id=trace_id,
            tool_name=tool_name,
            input_data={},
            latency_ms=200,
            success=True,
        )

        await observer.record_tool_call(
            trace_id=trace_id,
            tool_name=tool_name,
            input_data={},
            latency_ms=50,
            success=False,
        )

        metrics = await observer.get_tool_metrics(tool_name)
        assert metrics is not None
        assert metrics["tool_name"] == tool_name
        assert metrics["total_calls"] == 3
        assert metrics["successful_calls"] == 2
        assert metrics["failed_calls"] == 1
        assert metrics["success_rate"] == 2 / 3
        assert metrics["average_latency_ms"] == (100 + 200 + 50) / 3

    @pytest.mark.unit
    async def test_get_tool_metrics_returns_none_for_unknown_tool(
        self,
        observer,
    ) -> None:
        """Test that get_tool_metrics returns None for unknown tool.

        Given: An unknown tool name
        When: get_tool_metrics is called
        Then: Returns None
        """
        metrics = await observer.get_tool_metrics("unknown_tool")
        assert metrics is None


class TestPhidataObserverReasoningPathTracking:
    """Unit tests for Phidata observer reasoning path tracking.

    Tests verify:
    - Reasoning step recording
    - Step type categorization
    - Reasoning path retrieval
    """

    @pytest.fixture
    async def observer(self):
        """Create Phidata observer for testing."""
        from rag_service.observability.phidata_observer import PhidataObserver

        observer = PhidataObserver()
        return observer

    @pytest.mark.unit
    async def test_record_reasoning_step_stores_step(
        self,
        observer,
    ) -> None:
        """Test that record_reasoning_step stores reasoning step.

        Given: A reasoning step with type and description
        When: record_reasoning_step is called
        Then: Step is stored with correct data
        """
        trace_id = "trace_reasoning_001"

        await observer.task_start(trace_id=trace_id, request_id="req_001")

        await observer.record_reasoning_step(
            trace_id=trace_id,
            step_type="planning",
            description="Analyze user query",
            metadata={"complexity": "medium"},
        )

        reasoning_path = await observer.get_reasoning_path(trace_id)
        assert len(reasoning_path) == 1
        assert reasoning_path[0]["step_type"] == "planning"
        assert reasoning_path[0]["description"] == "Analyze user query"

    @pytest.mark.unit
    async def test_record_reasoning_step_supports_all_types(
        self,
        observer,
    ) -> None:
        """Test that all reasoning step types are supported.

        Given: Different step types
        When: record_reasoning_step is called with each type
        Then: All steps are recorded correctly
        """
        trace_id = "trace_reasoning_002"

        await observer.task_start(trace_id=trace_id, request_id="req_002")

        step_types = ["planning", "tool_selection", "result_evaluation", "conclusion"]

        for step_type in step_types:
            await observer.record_reasoning_step(
                trace_id=trace_id,
                step_type=step_type,
                description=f"Step {step_type}",
            )

        reasoning_path = await observer.get_reasoning_path(trace_id)
        assert len(reasoning_path) == 4

        recorded_types = [step["step_type"] for step in reasoning_path]
        for step_type in step_types:
            assert step_type in recorded_types

    @pytest.mark.unit
    async def test_get_reasoning_path_returns_empty_for_unknown(
        self,
        observer,
    ) -> None:
        """Test that get_reasoning_path returns empty list for unknown.

        Given: An unknown trace_id
        When: get_reasoning_path is called
        Then: Returns empty list
        """
        reasoning_path = await observer.get_reasoning_path("unknown_trace")
        assert reasoning_path == []


class TestPhidataObserverExecutionRecording:
    """Unit tests for Phidata observer execution recording.

    Tests verify:
    - Complete execution summary
    - Task completion status
    - Total latency tracking
    """

    @pytest.fixture
    async def observer(self):
        """Create Phidata observer for testing."""
        from rag_service.observability.phidata_observer import PhidataObserver

        observer = PhidataObserver()
        return observer

    @pytest.mark.unit
    async def test_record_execution_completes_task(
        self,
        observer,
    ) -> None:
        """Test that record_execution marks task as completed.

        Given: A running task
        When: record_execution is called with success=True
        Then: Task is marked as completed
        """
        trace_id = "trace_exec_001"

        await observer.task_start(trace_id=trace_id, request_id="req_001")

        await observer.record_execution(
            trace_id=trace_id,
            tool_calls=[{"tool": "kb"}],
            reasoning_path=["step1"],
            success=True,
            total_latency_ms=500,
        )

        execution = await observer.get_execution(trace_id)
        assert execution is not None
        assert execution["status"] == "completed"
        assert execution["success"] is True
        assert execution["total_latency_ms"] == 500

    @pytest.mark.unit
    async def test_record_execution_handles_failure(
        self,
        observer,
    ) -> None:
        """Test that record_execution handles task failure.

        Given: A running task that fails
        When: record_execution is called with success=False
        Then: Task is marked as failed
        """
        trace_id = "trace_exec_002"

        await observer.task_start(trace_id=trace_id, request_id="req_002")

        await observer.record_execution(
            trace_id=trace_id,
            tool_calls=[],
            reasoning_path=[],
            success=False,
        )

        execution = await observer.get_execution(trace_id)
        assert execution["status"] == "failed"
        assert execution["success"] is False

    @pytest.mark.unit
    async def test_record_execution_sets_end_time(
        self,
        observer,
    ) -> None:
        """Test that record_execution sets end_time.

        Given: A running task
        When: record_execution is called
        Then: end_time is set
        """
        trace_id = "trace_exec_003"

        await observer.task_start(trace_id=trace_id, request_id="req_003")

        execution_before = await observer.get_execution(trace_id)
        assert execution_before["end_time"] is None

        await observer.record_execution(
            trace_id=trace_id,
            tool_calls=[],
            reasoning_path=[],
            success=True,
        )

        execution_after = await observer.get_execution(trace_id)
        assert execution_after["end_time"] is not None


class TestPhidataObserverLLMCalls:
    """Unit tests for Phidata observer LLM call tracking.

    Tests verify:
    - LLM call recording
    - Token tracking
    - Model tracking
    """

    @pytest.fixture
    async def observer(self):
        """Create Phidata observer for testing."""
        from rag_service.observability.phidata_observer import PhidataObserver

        observer = PhidataObserver()
        return observer

    @pytest.mark.unit
    async def test_record_llm_call_stores_model_data(
        self,
        observer,
    ) -> None:
        """Test that record_llm_call stores LLM invocation data.

        Given: An LLM call during agent execution
        When: record_llm_call is called
        Then: Model and token data is recorded
        """
        trace_id = "trace_llm_001"

        await observer.task_start(trace_id=trace_id, request_id="req_001")

        await observer.record_llm_call(
            trace_id=trace_id,
            model="gpt-4",
            tokens={"input": 100, "output": 50},
        )

        execution = await observer.get_execution(trace_id)
        assert execution is not None
        assert len(execution["llm_calls"]) == 1
        assert execution["llm_calls"][0]["model"] == "gpt-4"
        assert execution["llm_calls"][0]["tokens"]["input"] == 100
        assert execution["llm_calls"][0]["tokens"]["output"] == 50

    @pytest.mark.unit
    async def test_record_multiple_llm_calls(
        self,
        observer,
    ) -> None:
        """Test that multiple LLM calls are recorded.

        Given: Multiple LLM calls during agent execution
        When: record_llm_call is called multiple times
        Then: All calls are recorded
        """
        trace_id = "trace_llm_002"

        await observer.task_start(trace_id=trace_id, request_id="req_002")

        await observer.record_llm_call(
            trace_id=trace_id,
            model="gpt-3.5-turbo",
            tokens={"input": 50, "output": 25},
        )

        await observer.record_llm_call(
            trace_id=trace_id,
            model="claude-3-haiku",
            tokens={"input": 75, "output": 40},
        )

        execution = await observer.get_execution(trace_id)
        assert len(execution["llm_calls"]) == 2
        assert execution["llm_calls"][0]["model"] == "gpt-3.5-turbo"
        assert execution["llm_calls"][1]["model"] == "claude-3-haiku"


class TestPhidataObserverToolMetrics:
    """Unit tests for Phidata observer tool metrics.

    Tests verify:
    - All tool metrics retrieval
    - Per-tool metrics calculation
    - Success rate calculation
    """

    @pytest.fixture
    async def observer(self):
        """Create Phidata observer for testing."""
        from rag_service.observability.phidata_observer import PhidataObserver

        observer = PhidataObserver()
        return observer

    @pytest.mark.unit
    async def test_get_all_tool_metrics_returns_all_tools(
        self,
        observer,
    ) -> None:
        """Test that get_all_tool_metrics returns all tools.

        Given: Multiple tools with calls
        When: get_all_tool_metrics is called
        Then: Returns metrics for all tools
        """
        trace_id = "trace_all_metrics_001"

        await observer.task_start(trace_id=trace_id, request_id="req_001")

        # Record calls for different tools
        await observer.record_tool_call(
            trace_id=trace_id,
            tool_name="tool_a",
            input_data={},
            latency_ms=100,
            success=True,
        )

        await observer.record_tool_call(
            trace_id=trace_id,
            tool_name="tool_b",
            input_data={},
            latency_ms=200,
            success=True,
        )

        all_metrics = await observer.get_all_tool_metrics()
        tool_names = [m["tool_name"] for m in all_metrics]
        assert "tool_a" in tool_names
        assert "tool_b" in tool_names

    @pytest.mark.unit
    async def test_get_recent_executions(
        self,
        observer,
    ) -> None:
        """Test that get_recent_executions returns recent records.

        Given: Multiple completed executions
        When: get_recent_executions is called
        Then: Returns most recent executions first
        """
        # Create multiple executions
        for i in range(3):
            trace_id = f"trace_recent_{i}"
            await observer.task_start(trace_id=trace_id, request_id=f"req_{i}")
            await observer.record_execution(
                trace_id=trace_id,
                tool_calls=[],
                reasoning_path=[],
                success=True,
            )

        recent = await observer.get_recent_executions(limit=2)
        assert len(recent) == 2

    @pytest.mark.unit
    async def test_flush_trace_is_non_blocking(
        self,
        observer,
    ) -> None:
        """Test that flush_trace completes without blocking.

        Given: An execution record
        When: flush_trace is called
        Then: Completes without raising
        """
        trace_id = "trace_flush_001"

        await observer.task_start(trace_id=trace_id, request_id="req_001")

        # Should not raise
        await observer.flush_trace(trace_id)
