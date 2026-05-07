"""
VerificationStep — hallucination detection.

Delegates to HallucinationDetectionCapability. Gracefully degrades
(marks unchecked) on failure (non-core error).

API Reference:
- Location: src/rag_service/pipeline/steps/verification.py
- Reads: answer, chunks
- Writes: hallucination_status
"""

from typing import Any

from rag_service.api.unified_schemas import HallucinationStatus
from rag_service.core.logger import get_logger
from rag_service.pipeline.context import PipelineContext

logger = get_logger(__name__)


class VerificationStep:
    """Verification step — hallucination detection.

    Delegates to HallucinationDetectionCapability. On failure,
    marks verification as unchecked (non-core, pipeline continues).
    """

    @property
    def name(self) -> str:
        """Step identifier."""
        return "verification"

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """Execute hallucination verification.

        Args:
            context: Pipeline context with answer and chunks set.

        Returns:
            Updated context with hallucination_status populated.
        """
        try:
            from rag_service.capabilities.hallucination_detection import (
                HallucinationDetectionCapability,
                HallucinationCheckInput,
            )

            capability = HallucinationDetectionCapability()
            detect_input = HallucinationCheckInput(
                generated_answer=context.answer,
                retrieved_chunks=context.chunks,
                trace_id=context.trace_id,
            )
            result = await capability.execute(detect_input)

            context.hallucination_status = HallucinationStatus(
                checked=True,
                passed=result.passed,
                confidence=result.confidence,
                flagged_claims=result.flagged_claims,
                warning_message=result.warning_message if not result.passed else None,
            )

            logger.info(
                "Verification completed",
                extra={
                    "trace_id": context.trace_id,
                    "passed": result.passed,
                    "confidence": result.confidence,
                },
            )

        except Exception as e:
            logger.warning(
                "Hallucination check failed, marking unchecked",
                extra={"trace_id": context.trace_id, "error": str(e)},
            )
            context.hallucination_status = HallucinationStatus(
                checked=False,
                passed=True,
                confidence=0.0,
            )

        return context

    async def get_health(self) -> dict[str, Any]:
        """Return health status of verification dependencies."""
        return {
            "step": "verification",
            "status": "healthy",
        }
