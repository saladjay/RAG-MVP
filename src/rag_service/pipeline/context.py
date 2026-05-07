"""
PipelineContext — shared state object for the atomic pipeline.

Flows through all pipeline steps. Each step reads from and writes to
this single context object (mutated, not replaced).

API Reference:
- Location: src/rag_service/pipeline/context.py
- Used by: PipelineRunner, all StepCapability implementations
"""

from typing import Any, Optional

from pydantic import BaseModel, Field

from rag_service.api.unified_schemas import (
    HallucinationStatus,
    QueryContext,
    UnifiedQueryRequest,
)


class PipelineContext(BaseModel):
    """Shared state flowing through all pipeline steps.

    Produced/consumed by each step according to the read/write contract
    defined in contracts/step-capability.md.
    """

    # === Input fields (set at construction) ===
    original_query: str = Field(default="", description="Original user query")
    session_id: str = Field(default="", description="Session ID for multi-turn")
    trace_id: str = Field(default="", description="Trace ID for observability")
    request_context: Optional[QueryContext] = Field(
        default=None, description="Optional retrieval context from request"
    )
    top_k: int = Field(default=10, description="Number of chunks to retrieve")
    stream: bool = Field(default=False, description="Whether streaming is requested")

    # === Produced by steps ===
    processed_query: str = Field(
        default="", description="Query after extraction/rewrite processing"
    )
    chunks: list[dict[str, Any]] = Field(
        default_factory=list, description="Retrieved chunks"
    )
    reasoning_result: Optional[dict[str, Any]] = Field(
        default=None, description="Reasoning step output"
    )
    answer: str = Field(default="", description="Generated answer")
    hallucination_status: Optional[HallucinationStatus] = Field(
        default=None, description="Verification result"
    )
    quality_meta: dict[str, Any] = Field(
        default_factory=dict, description="Quality metadata from extraction/execution"
    )

    # === Control signals ===
    should_abort: bool = Field(
        default=False, description="Signal to stop pipeline and return prompt"
    )
    abort_prompt: Optional[str] = Field(
        default=None, description="Prompt text to return on abort"
    )

    # === Auto-recorded by PipelineRunner ===
    timing: dict[str, float] = Field(
        default_factory=dict,
        description="Per-step timing in milliseconds (recorded by runner)",
    )

    model_config = {"arbitrary_types_allowed": True}

    @classmethod
    def from_request(cls, request: UnifiedQueryRequest) -> "PipelineContext":
        """Create PipelineContext from a UnifiedQueryRequest.

        Args:
            request: The incoming API request.

        Returns:
            Initialized PipelineContext with input fields set.
        """
        import uuid

        trace_id = request.session_id or str(uuid.uuid4())[:8]

        return cls(
            original_query=request.query,
            session_id=request.session_id or "",
            trace_id=trace_id,
            request_context=request.context,
            top_k=request.top_k,
            stream=request.stream,
            processed_query=request.query,  # Initialize with original; steps update it
        )
