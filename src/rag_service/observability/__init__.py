"""
Observability package - Three-layer observability stack.

This package provides the observability infrastructure:
- Prompt Layer (Langfuse): Prompt template management and trace correlation
- LLM Layer (LiteLLM): Model invocation metrics and billing
- Agent Layer (Phidata): AI task execution behavior and orchestration

Unified trace_id propagates across all layers for complete request observability.
"""

from rag_service.observability.trace_manager import (
    UnifiedTraceManager,
    TraceRecord,
    get_trace_manager,
    reset_trace_manager,
)
from rag_service.observability.langfuse_client import (
    LangfuseClient,
    PromptTrace,
    get_langfuse_client,
    reset_langfuse_client,
)
from rag_service.observability.litellm_observer import (
    LiteLLMObserver,
    InferenceRecord,
    get_litellm_observer,
    reset_litellm_observer,
)
from rag_service.observability.phidata_observer import (
    PhidataObserver,
    AgentExecutionRecord,
    get_phidata_observer,
    reset_phidata_observer,
)
from rag_service.observability.trace_propagation import (
    TraceContext,
    get_current_trace_id,
    set_current_trace_id,
    propagate_trace_id,
    extract_trace_id,
    inject_trace_id,
)
from rag_service.observability.trace_flush import (
    TraceFlushManager,
    get_flush_manager,
    schedule_trace_flush,
)

__all__ = [
    # Trace Manager
    "UnifiedTraceManager",
    "TraceRecord",
    "get_trace_manager",
    "reset_trace_manager",
    # Langfuse Client (Prompt Layer)
    "LangfuseClient",
    "PromptTrace",
    "get_langfuse_client",
    "reset_langfuse_client",
    # LiteLLM Observer (LLM Layer)
    "LiteLLMObserver",
    "InferenceRecord",
    "get_litellm_observer",
    "reset_litellm_observer",
    # Phidata Observer (Agent Layer)
    "PhidataObserver",
    "AgentExecutionRecord",
    "get_phidata_observer",
    "reset_phidata_observer",
    # Trace Propagation
    "TraceContext",
    "get_current_trace_id",
    "set_current_trace_id",
    "propagate_trace_id",
    "extract_trace_id",
    "inject_trace_id",
    # Trace Flush
    "TraceFlushManager",
    "get_flush_manager",
    "schedule_trace_flush",
]
