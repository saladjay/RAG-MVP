"""
Unified Trace Manager for RAG Service.

This module provides unified trace_id generation and propagation across all three
observability layers:
- LLM Layer (LiteLLM): Model invocation gateway + billing + strategy control
- Agent Layer (Phidata): AI task execution behavior observation and orchestration
- Prompt Layer (Langfuse): Prompt template management and trace correlation

The trace_manager ensures that a single trace_id propagates through all layers,
enabling complete request-to-cost-to-quality optimization.

API Reference:
- Location: src/rag_service/observability/trace_manager.py
- Function: UnifiedTraceManager.create_trace() -> Creates unified trace_id
- Function: UnifiedTraceManager.link_inference() -> Links inference metrics
- Function: UnifiedTraceManager.link_retrieval() -> Links retrieval metrics
- Function: UnifiedTraceManager.get_trace() -> Retrieves trace data
"""

import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from rag_service.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TraceRecord:
    """Represents a complete trace record."""

    trace_id: str
    request_id: str
    request_prompt: str
    user_context: Dict[str, Any]
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str = "active"  # active, completed, failed

    # Layer-specific data
    phidata_data: Dict[str, Any] = field(default_factory=dict)
    litellm_data: Dict[str, Any] = field(default_factory=dict)
    langfuse_data: Dict[str, Any] = field(default_factory=dict)

    # Spans for nested operations
    spans: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "trace_id": self.trace_id,
            "request_id": self.request_id,
            "request_prompt": self.request_prompt,
            "user_context": self.user_context,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status,
            "phidata_data": self.phidata_data,
            "litellm_data": self.litellm_data,
            "langfuse_data": self.langfuse_data,
            "spans": self.spans,
        }


class UnifiedTraceManager:
    """
    Unified trace manager for three-layer observability.

    This manager coordinates trace creation and propagation across:
    - Agent Layer (Phidata): Records task execution and reasoning
    - LLM Layer (LiteLLM): Records model invocations and costs
    - Prompt Layer (Langfuse): Records prompt versions and templates

    The unified trace_id ensures correlation across all layers.

    Attributes:
        litellm_observer: LLM layer observer for cost/performance metrics
        phidata_observer: Agent layer observer for execution metrics
        langfuse_client: Prompt layer client for template tracking
        _traces: In-memory store for active traces (production would use persistent storage)
    """

    def __init__(
        self,
        litellm_observer: Optional[Any] = None,
        phidata_observer: Optional[Any] = None,
        langfuse_client: Optional[Any] = None,
    ):
        """Initialize the unified trace manager.

        Args:
            litellm_observer: Optional LLM layer observer
            phidata_observer: Optional Agent layer observer
            langfuse_client: Optional Prompt layer client
        """
        self.litellm_observer = litellm_observer
        self.phidata_observer = phidata_observer
        self.langfuse_client = langfuse_client
        self._traces: Dict[str, TraceRecord] = {}
        self._lock = asyncio.Lock()

    async def create_trace(
        self,
        request_id: str,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a new unified trace across all layers.

        Generates a unified trace_id and initializes tracking across
        all three observability layers.

        Args:
            request_id: Unique request identifier
            prompt: User's input prompt/question
            context: Optional user context

        Returns:
            Unified trace_id for correlation across layers
        """
        # Generate unified trace_id
        trace_id = f"{request_id}_{uuid.uuid4().hex[:8]}"

        # Create trace record
        trace_record = TraceRecord(
            trace_id=trace_id,
            request_id=request_id,
            request_prompt=prompt,
            user_context=context or {},
            start_time=datetime.utcnow(),
        )

        async with self._lock:
            self._traces[trace_id] = trace_record

        # Initialize across all layers (non-blocking)
        await self._initialize_layer_traces(trace_record)

        logger.info(
            "Created unified trace",
            extra={
                "trace_id": trace_id,
                "request_id": request_id,
                "prompt_length": len(prompt),
            },
        )

        return trace_id

    async def _initialize_layer_traces(self, trace_record: TraceRecord) -> None:
        """Initialize trace across all three layers.

        This method calls each layer's trace initialization in a non-blocking manner.
        Failures in any layer are logged but do not block the request.

        Args:
            trace_record: The trace record to initialize across layers
        """
        # Initialize Phidata (Agent Layer)
        if self.phidata_observer:
            try:
                await self.phidata_observer.task_start(
                    trace_id=trace_record.trace_id,
                    request_id=trace_record.request_id,
                )
            except Exception as e:
                logger.warning(
                    "Failed to initialize Phidata trace",
                    extra={
                        "trace_id": trace_record.trace_id,
                        "error": str(e),
                    },
                )

        # Initialize Langfuse (Prompt Layer)
        if self.langfuse_client:
            try:
                await self.langfuse_client.create_trace(
                    trace_id=trace_record.trace_id,
                    prompt=trace_record.request_prompt,
                    context=trace_record.user_context,
                )
            except Exception as e:
                logger.warning(
                    "Failed to initialize Langfuse trace",
                    extra={
                        "trace_id": trace_record.trace_id,
                        "error": str(e),
                    },
                )

        # LiteLLM (LLM Layer) is initialized when inference actually happens

    async def link_inference(
        self,
        trace_id: str,
        model: str,
        tokens: Dict[str, int],
        latency_ms: float,
        cost: Optional[float] = None,
    ) -> None:
        """Link LLM inference metrics to trace.

        Records model invocation data from LiteLLM and links it to the unified trace.

        Args:
            trace_id: Unified trace identifier
            model: Model identifier (e.g., "gpt-4", "claude-3-opus")
            tokens: Token counts {"input": int, "output": int}
            latency_ms: Inference latency in milliseconds
            cost: Optional estimated cost in USD
        """
        async with self._lock:
            trace_record = self._traces.get(trace_id)
            if not trace_record:
                logger.warning(
                    "Trace not found for inference link",
                    extra={"trace_id": trace_id},
                )
                return

            # Store inference data
            trace_record.litellm_data = {
                "model": model,
                "tokens": tokens,
                "latency_ms": latency_ms,
                "cost": cost,
            }

        # Link to Phidata
        if self.phidata_observer:
            try:
                await self.phidata_observer.record_llm_call(
                    trace_id=trace_id,
                    model=model,
                    tokens=tokens,
                )
            except Exception as e:
                logger.warning(
                    "Failed to link inference to Phidata",
                    extra={"trace_id": trace_id, "error": str(e)},
                )

        # Link to LiteLLM observer
        if self.litellm_observer:
            try:
                await self.litellm_observer.capture_inference(
                    trace_id=trace_id,
                    model=model,
                    tokens=tokens,
                    latency_ms=latency_ms,
                    cost=cost,
                )
            except Exception as e:
                logger.warning(
                    "Failed to capture inference in LiteLLM observer",
                    extra={"trace_id": trace_id, "error": str(e)},
                )

        logger.info(
            "Linked inference to trace",
            extra={
                "trace_id": trace_id,
                "model": model,
                "input_tokens": tokens.get("input", 0),
                "output_tokens": tokens.get("output", 0),
                "latency_ms": latency_ms,
            },
        )

    async def link_retrieval(
        self,
        trace_id: str,
        chunks_count: int,
        chunk_ids: List[str],
        latency_ms: float,
        query_vector_used: Optional[str] = None,
    ) -> None:
        """Link retrieval metrics to trace.

        Records knowledge base retrieval data and links it to the unified trace.

        Args:
            trace_id: Unified trace identifier
            chunks_count: Number of chunks retrieved
            chunk_ids: List of chunk identifiers
            latency_ms: Retrieval latency in milliseconds
            query_vector_used: Optional embedding model used
        """
        async with self._lock:
            trace_record = self._traces.get(trace_id)
            if not trace_record:
                logger.warning(
                    "Trace not found for retrieval link",
                    extra={"trace_id": trace_id},
                )
                return

            # Add retrieval span
            trace_record.spans.append({
                "span_id": f"{trace_id}_retrieval_{uuid.uuid4().hex[:4]}",
                "span_name": "retrieval",
                "span_type": "retrieval",
                "latency_ms": latency_ms,
                "metadata": {
                    "chunks_count": chunks_count,
                    "chunk_ids": chunk_ids,
                    "query_vector_used": query_vector_used,
                },
            })

        logger.info(
            "Linked retrieval to trace",
            extra={
                "trace_id": trace_id,
                "chunks_count": chunks_count,
                "latency_ms": latency_ms,
            },
        )

    async def link_agent_execution(
        self,
        trace_id: str,
        tool_calls: List[Dict[str, Any]],
        reasoning_path: List[str],
        success: bool,
    ) -> None:
        """Link agent execution metrics to trace.

        Records Phidata agent execution data and links it to the unified trace.

        Args:
            trace_id: Unified trace identifier
            tool_calls: List of tools called during execution
            reasoning_path: List of reasoning steps taken
            success: Whether the agent task completed successfully
        """
        async with self._lock:
            trace_record = self._traces.get(trace_id)
            if not trace_record:
                logger.warning(
                    "Trace not found for agent execution link",
                    extra={"trace_id": trace_id},
                )
                return

            # Store agent data
            trace_record.phidata_data.update({
                "tool_calls": tool_calls,
                "reasoning_path": reasoning_path,
                "success": success,
            })

            # Add agent execution span
            trace_record.spans.append({
                "span_id": f"{trace_id}_agent_{uuid.uuid4().hex[:4]}",
                "span_name": "agent_execution",
                "span_type": "agent",
                "metadata": {
                    "tool_calls_count": len(tool_calls),
                    "reasoning_steps": len(reasoning_path),
                    "success": success,
                },
            })

        # Link to Phidata observer
        if self.phidata_observer:
            try:
                await self.phidata_observer.record_execution(
                    trace_id=trace_id,
                    tool_calls=tool_calls,
                    reasoning_path=reasoning_path,
                    success=success,
                )
            except Exception as e:
                logger.warning(
                    "Failed to record agent execution in Phidata observer",
                    extra={"trace_id": trace_id, "error": str(e)},
                )

        logger.info(
            "Linked agent execution to trace",
            extra={
                "trace_id": trace_id,
                "tool_calls_count": len(tool_calls),
                "success": success,
            },
        )

    async def complete_trace(
        self,
        trace_id: str,
        final_answer: Optional[str] = None,
        status: str = "completed",
    ) -> None:
        """Mark trace as completed and trigger non-blocking flush.

        Args:
            trace_id: Unified trace identifier
            final_answer: Optional final answer/response
            status: Final status ("completed", "failed")
        """
        async with self._lock:
            trace_record = self._traces.get(trace_id)
            if not trace_record:
                logger.warning(
                    "Trace not found for completion",
                    extra={"trace_id": trace_id},
                )
                return

            trace_record.end_time = datetime.utcnow()
            trace_record.status = status

            if final_answer:
                trace_record.langfuse_data["final_answer"] = final_answer

        # Trigger non-blocking flush across all layers
        await self._flush_trace_layers(trace_id)

        logger.info(
            "Completed trace",
            extra={
                "trace_id": trace_id,
                "status": status,
                "duration_ms": (
                    (trace_record.end_time - trace_record.start_time).total_seconds() * 1000
                    if trace_record.end_time
                    else 0
                ),
            },
        )

    async def _flush_trace_layers(self, trace_id: str) -> None:
        """Flush trace data across all layers in a non-blocking manner.

        This method ensures that trace data is persisted to all observability layers
        without blocking the request response. Failures are logged but do not affect
        the request.

        Args:
            trace_id: Unified trace identifier
        """
        # Flush Langfuse (Prompt Layer)
        if self.langfuse_client:
            try:
                await self.langfuse_client.flush_trace(trace_id)
            except Exception as e:
                logger.warning(
                    "Failed to flush Langfuse trace",
                    extra={"trace_id": trace_id, "error": str(e)},
                )

        # Flush LiteLLM observer (LLM Layer)
        if self.litellm_observer:
            try:
                await self.litellm_observer.flush_trace(trace_id)
            except Exception as e:
                logger.warning(
                    "Failed to flush LiteLLM trace",
                    extra={"trace_id": trace_id, "error": str(e)},
                )

        # Flush Phidata observer (Agent Layer)
        if self.phidata_observer:
            try:
                await self.phidata_observer.flush_trace(trace_id)
            except Exception as e:
                logger.warning(
                    "Failed to flush Phidata trace",
                    extra={"trace_id": trace_id, "error": str(e)},
                )

    async def get_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve trace data by ID.

        Args:
            trace_id: Unified trace identifier

        Returns:
            Trace data as dictionary, or None if not found
        """
        async with self._lock:
            trace_record = self._traces.get(trace_id)

        if not trace_record:
            return None

        return trace_record.to_dict()

    async def get_cross_layer_metrics(
        self,
        trace_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get aggregated metrics across all three layers.

        Combines metrics from Phidata, LiteLLM, and Langfuse for comprehensive
        trace analysis.

        Args:
            trace_id: Unified trace identifier

        Returns:
            Aggregated metrics dictionary, or None if trace not found
        """
        trace_data = await self.get_trace(trace_id)
        if not trace_data:
            return None

        return {
            "trace_id": trace_id,
            "duration_ms": (
                (
                    datetime.fromisoformat(trace_data["end_time"])
                    - datetime.fromisoformat(trace_data["start_time"])
                ).total_seconds()
                * 1000
                if trace_data["end_time"]
                else 0
            ),
            "agent_metrics": {
                "tool_calls_count": len(trace_data["phidata_data"].get("tool_calls", [])),
                "reasoning_steps": len(trace_data["phidata_data"].get("reasoning_path", [])),
                "success": trace_data["phidata_data"].get("success", True),
            },
            "llm_metrics": {
                "model": trace_data["litellm_data"].get("model"),
                "input_tokens": trace_data["litellm_data"].get("tokens", {}).get("input", 0),
                "output_tokens": trace_data["litellm_data"].get("tokens", {}).get("output", 0),
                "total_tokens": (
                    trace_data["litellm_data"].get("tokens", {}).get("input", 0)
                    + trace_data["litellm_data"].get("tokens", {}).get("output", 0)
                ),
                "latency_ms": trace_data["litellm_data"].get("latency_ms", 0),
                "cost": trace_data["litellm_data"].get("cost", 0),
            },
            "prompt_metrics": {
                "template_version": trace_data["langfuse_data"].get("template_version"),
                "final_answer": trace_data["langfuse_data"].get("final_answer"),
            },
            "spans": trace_data["spans"],
        }


# Global singleton instance
_trace_manager: Optional[UnifiedTraceManager] = None
_manager_lock = asyncio.Lock()


async def get_trace_manager() -> UnifiedTraceManager:
    """Get or create the global trace manager singleton.

    Returns:
        The global UnifiedTraceManager instance
    """
    global _trace_manager

    async with _manager_lock:
        if _trace_manager is None:
            _trace_manager = UnifiedTraceManager()
            logger.info("Initialized global trace manager")

    return _trace_manager


def reset_trace_manager() -> None:
    """Reset the global trace manager instance.

    This is primarily used for testing to ensure clean state between tests.
    """
    global _trace_manager
    _trace_manager = None
    logger.debug("Reset global trace manager")
