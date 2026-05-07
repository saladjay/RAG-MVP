"""
ExtractionStep — query extraction and quality enhancement.

Delegates to QualityStrategy for query pre-processing. Sets should_abort
when the quality strategy determines more information is needed from the user.

Phase 1 (US1): Only basic mode (pass-through).
Phase 2 (US2): Full dimension_gather and conversational support.

API Reference:
- Location: src/rag_service/pipeline/steps/extraction.py
- Reads: original_query, session_id
- Writes: processed_query, quality_meta, should_abort, abort_prompt
"""

from typing import Any

from rag_service.core.logger import get_logger
from rag_service.pipeline.context import PipelineContext
from rag_service.pipeline.policy import PipelinePolicy
from rag_service.strategies.quality import (
    BasicQuality,
    DimensionGatherQuality,
    ConversationalQuality,
)

logger = get_logger(__name__)


class ExtractionStep:
    """Extraction step — query quality pre-processing.

    Phase 1: delegates to BasicQuality (pass-through).
    Phase 2: delegates to DimensionGatherQuality or ConversationalQuality
    based on policy extraction_mode.
    """

    def __init__(self, policy: PipelinePolicy | None = None) -> None:
        """Initialize with quality strategy from policy or default basic."""
        self._policy = policy
        self._config = None
        self._quality: Any = None  # Set via set_quality or auto-created from policy

    def set_config(self, config: Any) -> None:
        """Set the QueryConfig for strategy selection (used in US2)."""
        self._config = config

    def set_quality(self, quality: Any) -> None:
        """Set the quality strategy directly."""
        self._quality = quality

    def _get_quality(self) -> Any:
        """Get quality strategy, auto-creating from policy if needed."""
        if self._quality is not None:
            return self._quality
        if self._policy is not None:
            mode = self._policy.extraction_mode
            if mode == "dimension_gather":
                self._quality = DimensionGatherQuality()
            elif mode == "conversational":
                self._quality = ConversationalQuality()
            else:
                self._quality = BasicQuality()
            return self._quality
        return BasicQuality()

    @property
    def name(self) -> str:
        """Step identifier."""
        return "extraction"

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """Execute extraction — pre-process query via quality strategy.

        Args:
            context: Pipeline context with original_query set.

        Returns:
            Updated context with processed_query and quality_meta.
        """
        quality = self._get_quality()
        query, prompt_info = await quality.pre_process(
            query=context.original_query,
            session_id=context.session_id or None,
            config=self._config,
        )

        if prompt_info is not None:
            # Quality strategy needs more info — signal abort
            context.should_abort = True
            context.abort_prompt = prompt_info.get("prompt_text", "")
            context.quality_meta = {
                "action": prompt_info.get("action", "prompt"),
                "session_id": prompt_info.get("session_id", ""),
                "quality_score": prompt_info.get("quality_score", 0.0),
                "dimensions": prompt_info.get("dimensions"),
                "feedback": prompt_info.get("feedback"),
            }
            logger.info(
                "Extraction aborting — quality needs more info",
                extra={
                    "trace_id": context.trace_id,
                    "quality_score": prompt_info.get("quality_score", 0.0),
                },
            )
            return context

        # Normal flow — update processed query
        context.processed_query = query
        mode = self._policy.extraction_mode if self._policy else "basic"
        context.quality_meta["extraction_mode"] = mode

        return context

    async def get_health(self) -> dict[str, Any]:
        """Return health status of extraction dependencies."""
        return {
            "step": "extraction",
            "status": "healthy",
        }
