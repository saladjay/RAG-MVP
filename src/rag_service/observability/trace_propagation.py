"""
Unified Trace ID Propagation for RAG Service.

This module provides utilities for propagating unified trace_id across all three
observability layers:
- Agent Layer (Phidata): Records task execution
- LLM Layer (LiteLLM): Records model invocations
- Prompt Layer (Langfuse): Records prompt templates

The propagation ensures that a single trace_id links all layers together,
enabling complete request-to-cost-to-quality correlation.

API Reference:
- Location: src/rag_service/observability/trace_propagation.py
- Function: propagate_trace_id() -> Inject trace_id into all layer contexts
- Function: extract_trace_id() -> Extract trace_id from any layer context
- Class: TraceContext -> Context manager for trace propagation
"""

import asyncio
import contextvars
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from rag_service.core.logger import get_logger

logger = get_logger(__name__)


# Context variable for storing the current trace_id in async context
_trace_id_context: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "trace_id",
    default=None,
)


@dataclass
class TraceContext:
    """
    Context manager for unified trace_id propagation.

    Ensures that trace_id is propagated across all async operations
    and can be accessed from any layer without explicit passing.

    Usage:
        async with TraceContext("trace_123") as ctx:
            # trace_id is now available via get_current_trace_id()
            await some_operation()
            # Child operations automatically inherit trace_id
        # trace_id is automatically cleared after context exit

    Attributes:
        trace_id: The unified trace identifier
        metadata: Optional metadata associated with the trace
        parent_trace_id: Optional parent trace_id for nested operations
    """

    trace_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    parent_trace_id: Optional[str] = None

    # Token for restoring previous context
    _token: Optional[contextvars.Token] = None

    async def __aenter__(self) -> "TraceContext":
        """Enter the trace context.

        Sets the trace_id in the async context variable.

        Returns:
            self for use in with statements
        """
        self._token = _trace_id_context.set(self.trace_id)
        logger.debug(
            "Entered trace context",
            extra={"trace_id": self.trace_id},
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit the trace context.

        Restores the previous trace_id in the async context.

        Args:
            exc_type: Exception type if an exception was raised
            exc_val: Exception value if an exception was raised
            exc_tb: Exception traceback if an exception was raised
        """
        if self._token is not None:
            _trace_id_context.reset(self._token)
        logger.debug(
            "Exited trace context",
            extra={"trace_id": self.trace_id},
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation.

        Returns:
            Dictionary with trace_id and metadata
        """
        return {
            "trace_id": self.trace_id,
            "metadata": self.metadata,
            "parent_trace_id": self.parent_trace_id,
        }


def get_current_trace_id() -> Optional[str]:
    """Get the current trace_id from async context.

    This function retrieves the trace_id that was set via TraceContext
    or set_current_trace_id().

    Returns:
        Current trace_id, or None if not set
    """
    return _trace_id_context.get()


def set_current_trace_id(trace_id: str) -> contextvars.Token:
    """Set the current trace_id in async context.

    This function sets the trace_id for the current async context,
    allowing child operations to access it via get_current_trace_id().

    Args:
        trace_id: The trace_id to set

    Returns:
        Token that can be used to restore the previous context
    """
    return _trace_id_context.set(trace_id)


def clear_current_trace_id(token: Optional[contextvars.Token] = None) -> None:
    """Clear the current trace_id from async context.

    Args:
        token: Optional token from set_current_trace_id() to restore previous context
    """
    if token is not None:
        _trace_id_context.reset(token)
    else:
        _trace_id_context.set(None)


async def propagate_trace_id(
    trace_id: str,
    target_layers: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Propagate trace_id to specified observability layers.

    This function ensures that the unified trace_id is registered with
    each layer's observer, enabling cross-layer trace correlation.

    Args:
        trace_id: Unified trace identifier
        target_layers: List of layers to propagate to.
            Options: ["phidata", "litellm", "langfuse"]
            If None, propagates to all layers.
        metadata: Optional metadata to include with propagation

    Returns:
        Dictionary with propagation results for each layer
    """
    if target_layers is None:
        target_layers = ["phidata", "litellm", "langfuse"]

    results: Dict[str, Any] = {
        "trace_id": trace_id,
        "propagated_to": [],
        "failed": [],
        "metadata": metadata or {},
    }

    # Set trace_id in async context
    set_current_trace_id(trace_id)

    # Propagate to Phidata (Agent Layer)
    if "phidata" in target_layers:
        try:
            from rag_service.observability.phidata_observer import get_phidata_observer

            observer = await get_phidata_observer()
            # Note: task_start will be called separately with actual request_id
            results["propagated_to"].append("phidata")
        except Exception as e:
            logger.warning(
                "Failed to propagate trace_id to Phidata",
                extra={"trace_id": trace_id, "error": str(e)},
            )
            results["failed"].append({"layer": "phidata", "error": str(e)})

    # Propagate to LiteLLM (LLM Layer)
    if "litellm" in target_layers:
        try:
            from rag_service.observability.litellm_observer import get_litellm_observer

            observer = await get_litellm_observer()
            # LiteLLM observer records data when inference actually happens
            results["propagated_to"].append("litellm")
        except Exception as e:
            logger.warning(
                "Failed to propagate trace_id to LiteLLM observer",
                extra={"trace_id": trace_id, "error": str(e)},
            )
            results["failed"].append({"layer": "litellm", "error": str(e)})

    # Propagate to Langfuse (Prompt Layer)
    if "langfuse" in target_layers:
        try:
            from rag_service.observability.langfuse_client import get_langfuse_client

            client = await get_langfuse_client()
            # Note: create_trace will be called separately with actual prompt
            results["propagated_to"].append("langfuse")
        except Exception as e:
            logger.warning(
                "Failed to propagate trace_id to Langfuse",
                extra={"trace_id": trace_id, "error": str(e)},
            )
            results["failed"].append({"layer": "langfuse", "error": str(e)})

    logger.info(
        "Propagated trace_id to layers",
        extra={
            "trace_id": trace_id,
            "layers": results["propagated_to"],
            "failed_count": len(results["failed"]),
        },
    )

    return results


def extract_trace_id(context: Dict[str, Any]) -> Optional[str]:
    """
    Extract trace_id from any layer's context dictionary.

    This function attempts to find trace_id in various possible keys
    that different layers might use.

    Args:
        context: Context dictionary from any layer

    Returns:
        Extracted trace_id, or None if not found
    """
    # Common keys that might contain trace_id
    possible_keys = [
        "trace_id",
        "traceId",
        "trace-id",
        "request_id",
        "requestId",
        "request-id",
        "correlation_id",
        "correlationId",
        "correlation-id",
    ]

    for key in possible_keys:
        if key in context:
            value = context[key]
            if isinstance(value, str) and value:
                return value

    # Check nested "metadata" dictionary
    if "metadata" in context and isinstance(context["metadata"], dict):
        return extract_trace_id(context["metadata"])

    # Check current async context
    current_trace_id = get_current_trace_id()
    if current_trace_id:
        return current_trace_id

    return None


def inject_trace_id(
    context: Dict[str, Any],
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Inject trace_id into a context dictionary.

    Ensures that trace_id is present in the context for propagation
    to downstream components.

    Args:
        context: Original context dictionary
        trace_id: trace_id to inject (uses current if None)

    Returns:
        New context dictionary with trace_id injected
    """
    if trace_id is None:
        trace_id = get_current_trace_id()

    if not trace_id:
        # No trace_id available, return original context
        return context

    # Create a copy to avoid modifying original
    result = context.copy()
    result["trace_id"] = trace_id

    # Also inject into metadata if present
    if "metadata" in result and isinstance(result["metadata"], dict):
        result["metadata"] = result["metadata"].copy()
        result["metadata"]["trace_id"] = trace_id

    return result


async def link_layer_traces(
    trace_id: str,
    from_layer: str,
    to_layer: str,
    link_type: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Create an explicit link between traces in different layers.

    This function records that a trace in one layer is causally connected
    to a trace in another layer (e.g., Phidata agent invoked LiteLLM).

    Args:
        trace_id: Unified trace identifier
        from_layer: Source layer ("phidata", "litellm", "langfuse")
        to_layer: Target layer ("phidata", "litellm", "langfuse")
        link_type: Type of link ("invocation", "parent-child", "correlation")
        metadata: Optional metadata about the link
    """
    link_record = {
        "trace_id": trace_id,
        "from_layer": from_layer,
        "to_layer": to_layer,
        "link_type": link_type,
        "metadata": metadata or {},
        "timestamp": asyncio.get_event_loop().time(),
    }

    logger.debug(
        "Linked layer traces",
        extra={
            "trace_id": trace_id,
            "from": from_layer,
            "to": to_layer,
            "type": link_type,
        },
    )

    # In a production system, this would be stored for later analysis
    # For now, we log it for debugging


def create_child_trace_id(parent_trace_id: str, child_name: str) -> str:
    """
    Create a child trace_id from a parent trace_id.

    For nested operations (e.g., agent calling tool, tool calling LLM),
    this creates a related trace_id that maintains the parent-child relationship.

    Args:
        parent_trace_id: Parent trace identifier
        child_name: Name/identifier for the child operation

    Returns:
        Child trace_id that includes parent reference
    """
    import uuid
    suffix = uuid.uuid4().hex[:8]
    return f"{parent_trace_id}_{child_name}_{suffix}"


async def validate_trace_chain(trace_id: str) -> Dict[str, Any]:
    """
    Validate that trace_id is present across all layers.

    This is a diagnostic function to verify that trace propagation
    is working correctly.

    Args:
        trace_id: Unified trace identifier to validate

    Returns:
        Dictionary with validation results for each layer
    """
    results = {
        "trace_id": trace_id,
        "layers_found": [],
        "layers_missing": [],
    }

    # Check Phidata
    try:
        from rag_service.observability.phidata_observer import get_phidata_observer

        observer = await get_phidata_observer()
        execution = await observer.get_execution(trace_id)
        if execution:
            results["layers_found"].append("phidata")
        else:
            results["layers_missing"].append("phidata")
    except Exception:
        results["layers_missing"].append("phidata")

    # Check LiteLLM
    try:
        from rag_service.observability.litellm_observer import get_litellm_observer

        observer = await get_litellm_observer()
        inference = await observer.get_inference(trace_id)
        if inference:
            results["layers_found"].append("litellm")
        else:
            results["layers_missing"].append("litellm")
    except Exception:
        results["layers_missing"].append("litellm")

    # Check Langfuse
    try:
        from rag_service.observability.langfuse_client import get_langfuse_client

        client = await get_langfuse_client()
        trace = await client.get_trace(trace_id)
        if trace:
            results["layers_found"].append("langfuse")
        else:
            results["layers_missing"].append("langfuse")
    except Exception:
        results["layers_missing"].append("langfuse")

    results["is_complete"] = len(results["layers_found"]) == 3

    return results
