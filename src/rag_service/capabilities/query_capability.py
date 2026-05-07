"""
Unified Query Capability for RAG Service.

Orchestrates the atomic pipeline: ExtractionStep → RewriteStep →
RetrievalStep → ReasoningStep → GenerationStep → VerificationStep →
ExecutionStep. Strategy selection is config-driven via QueryConfig.

API Reference:
- Location: src/rag_service/capabilities/query_capability.py
"""

import time
import uuid
from typing import Any, AsyncGenerator, Dict, Optional

from rag_service.api.unified_schemas import (
    HallucinationStatus,
    QueryResponse,
    QueryResponseMetadata,
    QueryTiming,
    SourceInfo,
    UnifiedQueryRequest,
)
from rag_service.capabilities.base import (
    Capability,
    CapabilityValidationResult,
)
from rag_service.config import get_settings
from rag_service.core.exceptions import GenerationError
from rag_service.core.logger import get_logger
from rag_service.pipeline.context import PipelineContext
from rag_service.pipeline.policy import PipelinePolicy
from rag_service.pipeline.runner import PipelineRunner
from rag_service.pipeline.steps import (
    ExecutionStep,
    ExtractionStep,
    GenerationStep,
    ReasoningStep,
    RetrievalStep,
    RewriteStep,
    VerificationStep,
)
from rag_service.strategies.quality import (
    BasicQuality,
    DimensionGatherQuality,
    ConversationalQuality,
)

logger = get_logger(__name__)


class QueryCapability(Capability[UnifiedQueryRequest, QueryResponse]):
    """Unified query capability with atomic pipeline orchestration.

    Config-driven strategy switching for:
    - retrieval_backend: "milvus" | "external_kb"
    - quality_mode: "basic" | "dimension_gather" | "conversational"
    """

    def __init__(self) -> None:
        """Initialize QueryCapability with pipeline from config."""
        super().__init__()
        settings = get_settings()
        config = settings.query

        # Build policy from config
        self._policy = PipelinePolicy.from_config(config)

        # Build extraction step with quality strategy
        extraction = ExtractionStep()
        quality = self._create_quality_strategy(config)
        extraction.set_quality(quality)
        extraction.set_config(config)

        # Build pipeline runner
        self._runner = PipelineRunner(
            steps=[
                extraction,
                RewriteStep(),
                RetrievalStep(backend=config.retrieval_backend),
                ReasoningStep(),
                GenerationStep(),
                VerificationStep(),
                ExecutionStep(),
            ],
            policy=self._policy,
        )

        logger.info(
            "Initialized QueryCapability with atomic pipeline",
            extra={
                "retrieval_backend": config.retrieval_backend,
                "quality_mode": config.quality_mode,
            },
        )

    def _create_quality_strategy(self, config: Any) -> Any:
        """Create quality strategy from config."""
        if config.quality_mode == "dimension_gather":
            return DimensionGatherQuality()
        elif config.quality_mode == "conversational":
            return ConversationalQuality()
        return BasicQuality()

    async def execute(self, input_data: UnifiedQueryRequest) -> QueryResponse:
        """Execute unified query pipeline.

        Args:
            input_data: Unified query request.

        Returns:
            QueryResponse with answer, sources, metadata.

        Raises:
            RetrievalError: If retrieval fails.
            GenerationError: If answer generation fails.
        """
        start_time = time.time()
        context = PipelineContext.from_request(input_data)

        context = await self._runner.run(context)
        total_ms = (time.time() - start_time) * 1000

        if context.should_abort:
            return self._build_prompt_response(context, total_ms)
        return self._build_query_response(context, total_ms)

    def _build_prompt_response(
        self, context: PipelineContext, total_ms: float
    ) -> QueryResponse:
        """Build response for abort (quality needs more info)."""
        meta = context.quality_meta
        return QueryResponse(
            answer="",
            sources=[],
            hallucination_status=HallucinationStatus(),
            metadata=QueryResponseMetadata(
                trace_id=context.trace_id,
                original_query=context.original_query,
                quality_mode=self._policy.extraction_mode,
                session_id=context.session_id or None,
                timing_ms=QueryTiming(total_ms=total_ms),
            ),
            action=meta.get("action", "prompt"),
            prompt_text=context.abort_prompt,
            dimensions=meta.get("dimensions"),
            feedback=meta.get("feedback"),
        )

    def _build_query_response(
        self, context: PipelineContext, total_ms: float
    ) -> QueryResponse:
        """Build normal query response from pipeline context."""
        sources = [
            SourceInfo(
                chunk_id=c.get("id", c.get("chunk_id", "")),
                content=c.get("content", ""),
                score=c.get("score", 0.0),
                source_doc=c.get("source_doc", ""),
                metadata=c.get("metadata", {}),
            )
            for c in context.chunks
        ]

        meta = context.quality_meta
        rewritten = meta.get("query_rewritten", False)
        timing = context.timing

        return QueryResponse(
            answer=context.answer,
            sources=sources,
            hallucination_status=context.hallucination_status or HallucinationStatus(),
            metadata=QueryResponseMetadata(
                trace_id=context.trace_id,
                query_rewritten=rewritten,
                original_query=context.original_query,
                rewritten_query=meta.get("rewritten_query") if rewritten else None,
                retrieval_count=len(context.chunks),
                retrieval_backend=self._policy.retrieval_backend,
                quality_mode=self._policy.extraction_mode,
                quality_score=meta.get("quality_score", meta.get("quality_enforced", False)),
                session_id=context.session_id or None,
                dimension_feedback=meta.get("feedback"),
                timing_ms=QueryTiming(
                    total_ms=total_ms,
                    rewrite_ms=timing.get("rewrite") if rewritten else None,
                    retrieve_ms=timing.get("retrieval", 0.0),
                    generate_ms=timing.get("generation", 0.0),
                    verify_ms=timing.get("verification") if self._policy.enable_verification else None,
                ),
            ),
        )

    async def stream_execute(self, input_data: UnifiedQueryRequest) -> AsyncGenerator[str, None]:
        """Execute query with streaming response.

        Uses PipelineRunner.run_stream() — same steps as synchronous flow.
        """
        context = PipelineContext.from_request(input_data)
        async for token in self._runner.run_stream(context):
            yield token

    def validate_input(self, input_data: UnifiedQueryRequest) -> CapabilityValidationResult:
        """Validate query request."""
        errors = []
        if not input_data.query or not input_data.query.strip():
            errors.append("Query cannot be empty")
        if input_data.top_k < 1 or input_data.top_k > 50:
            errors.append("top_k must be between 1 and 50")
        return CapabilityValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=[],
        )

    async def get_health(self) -> Dict[str, Any]:
        """Get health status of query pipeline components."""
        health = await super().get_health()
        try:
            runner_health = await self._runner.get_health()
            health.update(runner_health)
        except Exception as e:
            health["status"] = "degraded"
            health["error"] = str(e)
        return health
