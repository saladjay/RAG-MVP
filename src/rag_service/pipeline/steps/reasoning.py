"""
ReasoningStep — chain-of-thought and evidence synthesis.

Phase 1: Pass-through (identity function). Protocol interface defined
for future chain-of-thought, multi-step reasoning, and evidence synthesis.

API Reference:
- Location: src/rag_service/pipeline/steps/reasoning.py
- Reads: chunks, processed_query
- Writes: reasoning_result
"""

from typing import Any

from rag_service.core.logger import get_logger
from rag_service.pipeline.context import PipelineContext

logger = get_logger(__name__)


class ReasoningStep:
    """Reasoning step — Phase 1 pass-through.

    Protocol interface is defined for future CoT and evidence synthesis.
    Currently a no-op that passes context through unchanged.
    """

    @property
    def name(self) -> str:
        """Step identifier."""
        return "reasoning"

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """Execute reasoning — Phase 1 pass-through.

        Args:
            context: Pipeline context with chunks and processed_query set.

        Returns:
            Context with reasoning_result=None (unchanged).
        """
        # Phase 1: pass-through — no reasoning applied
        context.reasoning_result = None
        return context

    async def get_health(self) -> dict[str, Any]:
        """Return health status."""
        return {
            "step": "reasoning",
            "status": "healthy",
            "note": "pass-through (Phase 1)",
        }
