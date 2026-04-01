"""
Trace Observation Capability for RAG Service.

This capability provides unified access to observability operations
across the three-layer stack (LLM, Agent, Prompt). HTTP endpoints use
this capability - they NEVER access Langfuse/Phidata directly.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime

from pydantic import BaseModel, Field

from rag_service.capabilities.base import (
    Capability,
    CapabilityInput,
    CapabilityOutput,
    CapabilityValidationResult,
)


class TraceObservationInput(CapabilityInput):
    """
    Input for trace observation operations.

    Attributes:
        trace_id: The trace identifier.
        operation: Operation being performed (get_trace, get_metrics).
        metadata: Additional metadata for the trace.
    """

    trace_id: str = Field(..., min_length=1, description="Trace identifier")
    operation: str = Field(default="get_trace", description="Operation name")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Trace metadata")


class TraceObservationOutput(CapabilityOutput):
    """
    Output from trace observation operations.

    Attributes:
        trace_id: The trace identifier.
        recorded: Whether the operation was successful.
        trace_data: Full trace data if operation was get_trace.
        spans: List of spans in the trace.
        metrics: Aggregated metrics if operation was get_metrics.
    """

    trace_id: str = Field(..., description="Trace identifier")
    recorded: bool = Field(default=False, description="Whether operation was successful")
    trace_data: Optional[Dict[str, Any]] = Field(None, description="Full trace data")
    spans: List[Dict[str, Any]] = Field(default_factory=list, description="Trace spans")
    metrics: Optional[Dict[str, Any]] = Field(None, description="Aggregated metrics")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class TraceObservationCapability(Capability[TraceObservationInput, TraceObservationOutput]):
    """
    Capability for trace observation and management.

    This capability wraps observability operations across the three-layer
    stack (LLM via LiteLLM, Agent via Phidata, Prompt via Langfuse). HTTP
    endpoints use this capability - they NEVER access observability components
    directly.

    Features:
    - Unified trace_id generation and propagation
    - Trace creation and finalization
    - Trace retrieval by ID
    - Cross-layer metrics aggregation
    - Span management
    - Non-blocking trace flush
    """

    def __init__(self, trace_manager: Optional[Any] = None) -> None:
        """
        Initialize TraceObservationCapability.

        Args:
            trace_manager: UnifiedTraceManager instance (injected dependency).
        """
        super().__init__()
        self._trace_manager = trace_manager

    async def execute(self, input_data: TraceObservationInput) -> TraceObservationOutput:
        """
        Execute trace observation operation.

        Args:
            input_data: Trace observation parameters.

        Returns:
            Trace observation result.
        """
        try:
            # Get trace manager if not provided
            if self._trace_manager is None:
                from rag_service.observability.trace_manager import get_trace_manager
                self._trace_manager = await get_trace_manager()

            operation = input_data.operation
            trace_id = input_data.trace_id

            if operation == "get_trace":
                # Retrieve full trace data
                trace_data = await self._trace_manager.get_trace(trace_id)

                if trace_data:
                    return TraceObservationOutput(
                        recorded=True,
                        trace_id=trace_id,
                        trace_data=trace_data,
                        spans=trace_data.get("spans", []),
                        metadata={
                            "operation": operation,
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                    )
                else:
                    return TraceObservationOutput(
                        recorded=False,
                        trace_id=trace_id,
                        metadata={"error": "Trace not found"},
                    )

            elif operation == "get_metrics":
                # Get cross-layer aggregated metrics
                metrics = await self._trace_manager.get_cross_layer_metrics(trace_id)

                if metrics:
                    return TraceObservationOutput(
                        recorded=True,
                        trace_id=trace_id,
                        metrics=metrics,
                        metadata={
                            "operation": operation,
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                    )
                else:
                    return TraceObservationOutput(
                        recorded=False,
                        trace_id=trace_id,
                        metadata={"error": "Trace not found"},
                    )

            else:
                return TraceObservationOutput(
                    recorded=False,
                    trace_id=trace_id,
                    metadata={"error": f"Unknown operation: {operation}"},
                )

        except Exception as e:
            # Observability failures should NOT block requests
            # Return success=False but don't raise
            from rag_service.core.logger import get_logger
            logger = get_logger(__name__)
            logger.warning(
                "Trace observation operation failed",
                extra={"trace_id": input_data.trace_id, "error": str(e)},
            )

            return TraceObservationOutput(
                recorded=False,
                trace_id=input_data.trace_id,
                metadata={"error": str(e)},
            )

    def validate_input(self, input_data: TraceObservationInput) -> CapabilityValidationResult:
        """
        Validate trace observation input.

        Args:
            input_data: Input to validate.

        Returns:
            Validation result.
        """
        errors = []

        # Validate trace_id
        if not input_data.trace_id or not input_data.trace_id.strip():
            errors.append("trace_id cannot be empty")

        # Validate operation
        valid_operations = ["get_trace", "get_metrics"]
        if input_data.operation not in valid_operations:
            errors.append(f"operation must be one of: {', '.join(valid_operations)}")

        return CapabilityValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
        )

    def get_health(self) -> Dict[str, Any]:
        """
        Get health status of trace observation.

        Returns:
            Health status information.
        """
        health = super().get_health()

        # Check trace manager status
        if self._trace_manager:
            health["trace_manager"] = "available"
        else:
            health["trace_manager"] = "not_initialized"
            health["observability_status"] = "degraded"

        return health
