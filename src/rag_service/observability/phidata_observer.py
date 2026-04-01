"""
Phidata Observer for Agent Layer Observability.

This module provides metrics capture for the Agent Layer using Phidata.
It handles:
- Execution steps tracking
- Tools called during agent execution
- Reasoning paths and decision chains
- Tool call success/failure rates

The Phidata observer is part of the three-layer observability stack:
- Prompt Layer (langfuse_client.py): Prompt template management
- LLM Layer (litellm_observer.py): Model invocation metrics
- Agent Layer (this module): AI task execution behavior and orchestration

API Reference:
- Location: src/rag_service/observability/phidata_observer.py
- Class: PhidataObserver
- Method: task_start() -> Initialize agent task tracking
- Method: record_tool_call() -> Record tool invocation
- Method: record_reasoning_step() -> Record reasoning path step
- Method: record_execution() -> Record complete agent execution
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from collections import defaultdict

from rag_service.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ToolCallRecord:
    """Represents a single tool call during agent execution."""

    tool_id: str
    tool_name: str
    trace_id: str
    input_data: Dict[str, Any]
    output_data: Optional[Dict[str, Any]] = None
    latency_ms: float = 0.0
    success: bool = True
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "tool_id": self.tool_id,
            "tool_name": self.tool_name,
            "trace_id": self.trace_id,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "latency_ms": self.latency_ms,
            "success": self.success,
            "error_message": self.error_message,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ReasoningStep:
    """Represents a single step in the agent's reasoning path."""

    step_id: str
    trace_id: str
    step_type: str  # "planning", "tool_selection", "result_evaluation", "conclusion"
    description: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "step_id": self.step_id,
            "trace_id": self.trace_id,
            "step_type": self.step_type,
            "description": self.description,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class AgentExecutionRecord:
    """Represents a complete agent execution record."""

    trace_id: str
    request_id: str
    task_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str = "running"  # running, completed, failed
    success: bool = False

    # Execution metrics
    tool_calls: List[ToolCallRecord] = field(default_factory=list)
    reasoning_path: List[ReasoningStep] = field(default_factory=list)
    total_latency_ms: float = 0.0

    # LLM calls made during execution
    llm_calls: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "trace_id": self.trace_id,
            "request_id": self.request_id,
            "task_name": self.task_name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status,
            "success": self.success,
            "tool_calls": [call.to_dict() for call in self.tool_calls],
            "reasoning_path": [step.to_dict() for step in self.reasoning_path],
            "total_latency_ms": self.total_latency_ms,
            "llm_calls": self.llm_calls,
            "tool_calls_count": len(self.tool_calls),
            "reasoning_steps_count": len(self.reasoning_path),
        }


class PhidataObserver:
    """
    Observer for capturing Agent layer metrics via Phidata.

    This observer tracks:
    - Tool calls: Which tools were called, inputs/outputs, success rates
    - Reasoning paths: Decision chains and planning steps
    - Task execution: Overall task success and performance
    - LLM integration: Model calls made during agent execution

    Data is stored in-memory for analysis and can be correlated with
    LLM layer (LiteLLM) and Prompt layer (Langfuse) data via trace_id.

    Attributes:
        _executions: Store of agent execution records by trace_id
        _tool_calls: Store of individual tool calls by tool_id
        _reasoning_steps: Store of reasoning steps by step_id
        _tool_metrics: Aggregated metrics per tool
        _lock: Async lock for thread-safe operations
    """

    def __init__(self):
        """Initialize the Phidata observer."""
        self._executions: Dict[str, AgentExecutionRecord] = {}
        self._tool_calls: Dict[str, ToolCallRecord] = {}
        self._reasoning_steps: Dict[str, ReasoningStep] = {}
        self._tool_metrics: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "total_calls": 0,
                "successful_calls": 0,
                "failed_calls": 0,
                "total_latency_ms": 0.0,
            }
        )
        self._lock = asyncio.Lock()

    async def task_start(
        self,
        trace_id: str,
        request_id: str,
        task_name: str = "rag-task",
    ) -> None:
        """Initialize tracking for an agent task.

        Creates a new execution record for the agent task.

        Args:
            trace_id: Unified trace identifier
            request_id: Request identifier
            task_name: Optional task name (default: "rag-task")
        """
        execution = AgentExecutionRecord(
            trace_id=trace_id,
            request_id=request_id,
            task_name=task_name,
            start_time=datetime.utcnow(),
        )

        async with self._lock:
            self._executions[trace_id] = execution

        logger.debug(
            "Started agent task tracking",
            extra={
                "trace_id": trace_id,
                "request_id": request_id,
                "task_name": task_name,
            },
        )

    async def record_tool_call(
        self,
        trace_id: str,
        tool_name: str,
        input_data: Dict[str, Any],
        output_data: Optional[Dict[str, Any]] = None,
        latency_ms: float = 0.0,
        success: bool = True,
        error_message: Optional[str] = None,
    ) -> None:
        """Record a tool call during agent execution.

        Args:
            trace_id: Unified trace identifier
            tool_name: Name of the tool called
            input_data: Input parameters for the tool
            output_data: Optional output from the tool
            latency_ms: Tool execution time in milliseconds
            success: Whether the tool call succeeded
            error_message: Optional error message if failed
        """
        tool_id = f"{trace_id}_{tool_name}_{len(self._tool_calls)}"

        tool_call = ToolCallRecord(
            tool_id=tool_id,
            tool_name=tool_name,
            trace_id=trace_id,
            input_data=input_data,
            output_data=output_data,
            latency_ms=latency_ms,
            success=success,
            error_message=error_message,
        )

        async with self._lock:
            self._tool_calls[tool_id] = tool_call

            # Add to execution record
            if trace_id in self._executions:
                self._executions[trace_id].tool_calls.append(tool_call)

            # Update tool metrics
            self._tool_metrics[tool_name]["total_calls"] += 1
            if success:
                self._tool_metrics[tool_name]["successful_calls"] += 1
            else:
                self._tool_metrics[tool_name]["failed_calls"] += 1
            self._tool_metrics[tool_name]["total_latency_ms"] += latency_ms

        logger.debug(
            "Recorded tool call",
            extra={
                "trace_id": trace_id,
                "tool_name": tool_name,
                "success": success,
                "latency_ms": latency_ms,
            },
        )

    async def record_reasoning_step(
        self,
        trace_id: str,
        step_type: str,
        description: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a reasoning step in the agent's decision chain.

        Args:
            trace_id: Unified trace identifier
            step_type: Type of reasoning step
            description: Human-readable description of the step
            metadata: Optional additional metadata
        """
        step_id = f"{trace_id}_reasoning_{len(self._reasoning_steps)}"

        step = ReasoningStep(
            step_id=step_id,
            trace_id=trace_id,
            step_type=step_type,
            description=description,
            metadata=metadata or {},
        )

        async with self._lock:
            self._reasoning_steps[step_id] = step

            # Add to execution record
            if trace_id in self._executions:
                self._executions[trace_id].reasoning_path.append(step)

        logger.debug(
            "Recorded reasoning step",
            extra={
                "trace_id": trace_id,
                "step_type": step_type,
                "description": description,
            },
        )

    async def record_llm_call(
        self,
        trace_id: str,
        model: str,
        tokens: Dict[str, int],
    ) -> None:
        """Record an LLM call made during agent execution.

        Links agent execution with LLM layer observability.

        Args:
            trace_id: Unified trace identifier
            model: Model identifier
            tokens: Token counts {"input": int, "output": int}
        """
        async with self._lock:
            if trace_id in self._executions:
                self._executions[trace_id].llm_calls.append({
                    "model": model,
                    "tokens": tokens,
                    "timestamp": datetime.utcnow().isoformat(),
                })

        logger.debug(
            "Recorded LLM call in agent execution",
            extra={
                "trace_id": trace_id,
                "model": model,
                "input_tokens": tokens.get("input", 0),
                "output_tokens": tokens.get("output", 0),
            },
        )

    async def record_execution(
        self,
        trace_id: str,
        tool_calls: List[Dict[str, Any]],
        reasoning_path: List[str],
        success: bool,
        total_latency_ms: Optional[float] = None,
    ) -> None:
        """Record complete agent execution summary.

        This is called at the end of agent execution to provide
        a summary of the entire task.

        Args:
            trace_id: Unified trace identifier
            tool_calls: List of tool call summaries
            reasoning_path: List of reasoning step descriptions
            success: Whether the task completed successfully
            total_latency_ms: Optional total execution time
        """
        async with self._lock:
            execution = self._executions.get(trace_id)
            if execution:
                execution.end_time = datetime.utcnow()
                execution.status = "completed" if success else "failed"
                execution.success = success
                if total_latency_ms is not None:
                    execution.total_latency_ms = total_latency_ms

        logger.info(
            "Recorded agent execution",
            extra={
                "trace_id": trace_id,
                "success": success,
                "tool_calls_count": len(tool_calls),
                "reasoning_steps": len(reasoning_path),
                "total_latency_ms": total_latency_ms,
            },
        )

    async def get_execution(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Get agent execution record by trace ID.

        Args:
            trace_id: Unified trace identifier

        Returns:
            Execution record dictionary, or None if not found
        """
        async with self._lock:
            execution = self._executions.get(trace_id)

        if not execution:
            return None

        return execution.to_dict()

    async def get_tool_calls(self, trace_id: str) -> List[Dict[str, Any]]:
        """Get all tool calls for a trace.

        Args:
            trace_id: Unified trace identifier

        Returns:
            List of tool call dictionaries
        """
        async with self._lock:
            execution = self._executions.get(trace_id)

        if not execution:
            return []

        return [call.to_dict() for call in execution.tool_calls]

    async def get_reasoning_path(self, trace_id: str) -> List[Dict[str, Any]]:
        """Get reasoning path for a trace.

        Args:
            trace_id: Unified trace identifier

        Returns:
            List of reasoning step dictionaries
        """
        async with self._lock:
            execution = self._executions.get(trace_id)

        if not execution:
            return []

        return [step.to_dict() for step in execution.reasoning_path]

    async def get_tool_metrics(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get aggregated metrics for a specific tool.

        Args:
            tool_name: Tool identifier

        Returns:
            Tool metrics dictionary, or None if tool not found
        """
        async with self._lock:
            metrics = self._tool_metrics.get(tool_name)

        if not metrics or metrics["total_calls"] == 0:
            return None

        total_calls = metrics["total_calls"]
        return {
            "tool_name": tool_name,
            "total_calls": total_calls,
            "successful_calls": metrics["successful_calls"],
            "failed_calls": metrics["failed_calls"],
            "success_rate": metrics["successful_calls"] / total_calls if total_calls > 0 else 0,
            "average_latency_ms": metrics["total_latency_ms"] / total_calls if total_calls > 0 else 0,
        }

    async def get_all_tool_metrics(self) -> List[Dict[str, Any]]:
        """Get metrics for all tools.

        Returns:
            List of tool metrics dictionaries
        """
        metrics_list = []
        async with self._lock:
            for tool_name, metrics in self._tool_metrics.items():
                if metrics["total_calls"] > 0:
                    total_calls = metrics["total_calls"]
                    metrics_list.append({
                        "tool_name": tool_name,
                        "total_calls": total_calls,
                        "successful_calls": metrics["successful_calls"],
                        "failed_calls": metrics["failed_calls"],
                        "success_rate": metrics["successful_calls"] / total_calls if total_calls > 0 else 0,
                        "average_latency_ms": metrics["total_latency_ms"] / total_calls if total_calls > 0 else 0,
                    })

        return metrics_list

    async def flush_trace(self, trace_id: str) -> None:
        """Non-blocking flush for trace-specific data.

        In a production environment, this would flush data to external storage.
        For now, data is already stored in-memory.

        Args:
            trace_id: Unified trace identifier
        """
        logger.debug(
            "Flushed Phidata trace",
            extra={"trace_id": trace_id},
        )

    async def get_recent_executions(
        self,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get recent agent execution records.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of execution dictionaries, most recent first
        """
        async with self._lock:
            executions = sorted(
                [e for e in self._executions.values() if e.end_time],
                key=lambda e: e.end_time,
                reverse=True,
            )[:limit]

        return [execution.to_dict() for execution in executions]


# Global singleton instance
_phidata_observer: Optional[PhidataObserver] = None
_observer_lock = asyncio.Lock()


async def get_phidata_observer() -> PhidataObserver:
    """Get or create the global Phidata observer singleton.

    Returns:
        The global PhidataObserver instance
    """
    global _phidata_observer

    async with _observer_lock:
        if _phidata_observer is None:
            _phidata_observer = PhidataObserver()
            logger.info("Initialized global Phidata observer")

    return _phidata_observer


def reset_phidata_observer() -> None:
    """Reset the global Phidata observer instance.

    This is primarily used for testing to ensure clean state between tests.
    """
    global _phidata_observer
    _phidata_observer = None
    logger.debug("Reset global Phidata observer")
