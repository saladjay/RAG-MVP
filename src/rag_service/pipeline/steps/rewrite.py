"""
RewriteStep — query rewriting for improved retrieval.

Delegates to QueryRewriteCapability. Gracefully degrades to original
query on failure (non-core error).

API Reference:
- Location: src/rag_service/pipeline/steps/rewrite.py
- Reads: processed_query
- Writes: processed_query (updated)
"""

from typing import Any

from rag_service.core.logger import get_logger
from rag_service.pipeline.context import PipelineContext

logger = get_logger(__name__)


class RewriteStep:
    """Rewrite step — query optimization for better retrieval.

    Delegates to QueryRewriteCapability. Falls back to original query
    on any failure (non-core, pipeline continues).
    """

    @property
    def name(self) -> str:
        """Step identifier."""
        return "rewrite"

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """Execute query rewrite.

        Args:
            context: Pipeline context with processed_query set.

        Returns:
            Updated context with potentially rewritten processed_query.
        """
        original = context.processed_query
        try:
            from rag_service.capabilities.query_rewrite import (
                QueryRewriteCapability,
                QueryRewriteInput,
            )
            from rag_service.inference.gateway import get_gateway

            gateway = await get_gateway()
            capability = QueryRewriteCapability(litellm_client=gateway)
            rewrite_input = QueryRewriteInput(
                original_query=original,
                trace_id=context.trace_id,
            )
            result = await capability.execute(rewrite_input)
            rewritten = result.rewritten_query or original

            if result.was_rewritten:
                logger.info(
                    "Query rewritten",
                    extra={
                        "trace_id": context.trace_id,
                        "original": original[:80],
                        "rewritten": rewritten[:80],
                    },
                )
                context.processed_query = rewritten
                context.quality_meta["query_rewritten"] = True
                context.quality_meta["original_query"] = context.original_query
                context.quality_meta["rewritten_query"] = rewritten
            else:
                context.quality_meta["query_rewritten"] = False

        except Exception as e:
            logger.warning(
                "Query rewrite failed, using original",
                extra={"trace_id": context.trace_id, "error": str(e)},
            )
            context.quality_meta["query_rewritten"] = False

        return context

    async def get_health(self) -> dict[str, Any]:
        """Return health status of rewrite dependencies."""
        try:
            from rag_service.inference.gateway import get_gateway
            gateway = await get_gateway()
            return {
                "step": "rewrite",
                "status": "healthy",
                "dependencies": {"gateway": gateway.provider},
            }
        except Exception as e:
            return {
                "step": "rewrite",
                "status": "degraded",
                "dependencies": {"gateway": f"unavailable: {e}"},
            }
