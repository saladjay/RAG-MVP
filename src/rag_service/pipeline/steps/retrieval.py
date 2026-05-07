"""
RetrievalStep — knowledge base chunk retrieval.

Delegates to RetrievalStrategy (Milvus or ExternalKB). Raises
RetrievalError on core failure (pipeline halts).

API Reference:
- Location: src/rag_service/pipeline/steps/retrieval.py
- Reads: processed_query, top_k, request_context
- Writes: chunks
"""

from typing import Any, Optional

from rag_service.core.logger import get_logger
from rag_service.pipeline.context import PipelineContext
from rag_service.strategies.retrieval import (
    ExternalKBRetrieval,
    MilvusRetrieval,
    RetrievalStrategy,
)

logger = get_logger(__name__)


class RetrievalStep:
    """Retrieval step — fetch relevant chunks from knowledge base.

    Strategy selection based on policy.retrieval_backend:
    - "milvus" → MilvusRetrieval
    - "external_kb" → ExternalKBRetrieval
    """

    def __init__(self, backend: str = "external_kb") -> None:
        """Initialize retrieval step with the configured backend.

        Args:
            backend: Retrieval backend identifier.
        """
        self._backend = backend
        self._strategy: Optional[RetrievalStrategy] = None

    def _get_strategy(self) -> RetrievalStrategy:
        """Get or create the retrieval strategy."""
        if self._strategy is None:
            if self._backend == "milvus":
                self._strategy = MilvusRetrieval()
            else:
                self._strategy = ExternalKBRetrieval()
        return self._strategy

    @property
    def name(self) -> str:
        """Step identifier."""
        return "retrieval"

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """Execute retrieval from knowledge base.

        Args:
            context: Pipeline context with processed_query, top_k, request_context.

        Returns:
            Updated context with chunks populated.

        Raises:
            RetrievalError: If retrieval fails (core error).
        """
        strategy = self._get_strategy()

        # Convert request_context to dict for strategy
        ctx_dict = None
        if context.request_context:
            ctx_dict = context.request_context.model_dump()

        chunks = await strategy.retrieve(
            query=context.processed_query,
            top_k=context.top_k,
            context=ctx_dict,
            trace_id=context.trace_id,
        )

        context.chunks = chunks
        logger.info(
            "Retrieval completed",
            extra={
                "trace_id": context.trace_id,
                "chunk_count": len(chunks),
                "backend": self._backend,
            },
        )

        return context

    async def get_health(self) -> dict[str, Any]:
        """Return health status of retrieval dependencies."""
        return {
            "step": "retrieval",
            "status": "healthy",
            "dependencies": {
                "backend": self._backend,
            },
        }
