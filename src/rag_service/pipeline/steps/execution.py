"""
ExecutionStep — post-generation quality metadata finalization.

Phase 1: Migrated from quality.post_process(). Collects quality metadata
from the pipeline run and finalizes it.

Future: Tool calling, API invocation, workflow execution.

API Reference:
- Location: src/rag_service/pipeline/steps/execution.py
- Reads: answer, chunks, hallucination_status
- Writes: quality_meta (finalized)
"""

from typing import Any

from rag_service.core.logger import get_logger
from rag_service.pipeline.context import PipelineContext

logger = get_logger(__name__)


class ExecutionStep:
    """Execution step — finalize quality metadata.

    Phase 1: Collects and finalizes quality metadata from the pipeline run.
    Future: Tool calling, API invocation, workflow execution.
    """

    @property
    def name(self) -> str:
        """Step identifier."""
        return "execution"

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """Execute — finalize quality metadata.

        Args:
            context: Pipeline context with answer, chunks, hallucination_status set.

        Returns:
            Context with finalized quality_meta.
        """
        meta = context.quality_meta

        # Add hallucination info to metadata
        if context.hallucination_status:
            meta["hallucination_checked"] = context.hallucination_status.checked
            meta["hallucination_passed"] = context.hallucination_status.passed
            if context.hallucination_status.warning_message:
                meta["hallucination_warning"] = context.hallucination_status.warning_message

        # Add retrieval count
        meta["retrieval_count"] = len(context.chunks)

        context.quality_meta = meta

        logger.debug(
            "Execution step completed",
            extra={
                "trace_id": context.trace_id,
                "meta_keys": list(meta.keys()),
            },
        )

        return context

    async def get_health(self) -> dict[str, Any]:
        """Return health status."""
        return {
            "step": "execution",
            "status": "healthy",
        }
