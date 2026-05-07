"""
Quality strategy protocols and implementations.

Defines the QualityStrategy Protocol and concrete implementations for
query quality enhancement modes. Strategy selection is config-driven
via QueryConfig.quality_mode.

Implementations:
- BasicQuality: Pass-through (no enhancement)
- DimensionGatherQuality: Multi-turn dimension gathering (delegates to QueryQualityCapability)
- ConversationalQuality: Slot extraction and conversational query (delegates to ConversationalQueryCapability)

API Reference:
- Location: src/rag_service/strategies/quality.py
"""

from typing import Any, Optional, Protocol, runtime_checkable

from rag_service.core.logger import get_logger

logger = get_logger(__name__)


@runtime_checkable
class QualityStrategy(Protocol):
    """Protocol for query quality enhancement.

    Implementations may pre-process queries (e.g., dimension analysis,
    slot extraction) and post-process results (e.g., quality feedback,
    confidence scoring).
    """

    async def pre_process(
        self,
        query: str,
        session_id: Optional[str],
        config: Any,
    ) -> tuple[str, Optional[dict[str, Any]]]:
        """Pre-process query before retrieval.

        Args:
            query: The original user query.
            session_id: Optional session ID for multi-turn conversations.
            config: QueryConfig instance.

        Returns:
            Tuple of (processed_query, prompt_info_or_None).
            If prompt_info is not None, the pipeline should return a
            clarification prompt to the caller instead of proceeding.
        """
        ...

    async def post_process(
        self,
        answer: str,
        chunks: list[dict[str, Any]],
        session_id: Optional[str],
    ) -> dict[str, Any]:
        """Post-process answer after generation.

        Args:
            answer: The generated answer text.
            chunks: The retrieved chunks used for generation.
            session_id: Optional session ID for multi-turn conversations.

        Returns:
            Dictionary with quality metadata (quality_score, feedback, etc.).
        """
        ...


class BasicQuality:
    """Pass-through quality strategy — no enhancement.

    Returns the query unchanged and provides no quality feedback.
    Used when quality_mode is "basic" or when quality enhancement is disabled.
    """

    async def pre_process(
        self,
        query: str,
        session_id: Optional[str],
        config: Any,
    ) -> tuple[str, Optional[dict[str, Any]]]:
        """Pass through query unchanged.

        Returns:
            (original_query, None) — no prompt needed.
        """
        return query, None

    async def post_process(
        self,
        answer: str,
        chunks: list[dict[str, Any]],
        session_id: Optional[str],
    ) -> dict[str, Any]:
        """Return empty quality metadata.

        Returns:
            Empty dict — no quality feedback.
        """
        return {}


class DimensionGatherQuality:
    """Multi-turn dimension gathering quality strategy.

    Delegates to the existing QueryQualityCapability during transition.
    Analyzes user queries against required document dimensions and prompts
    users for missing information before search.
    """

    def __init__(self) -> None:
        """Initialize DimensionGatherQuality."""
        self._capability = None

    async def _get_capability(self):
        """Get or create the underlying QueryQualityCapability."""
        if self._capability is None:
            from rag_service.capabilities.query_quality import QueryQualityCapability
            from rag_service.config import get_settings
            settings = get_settings()
            self._capability = QueryQualityCapability(config=settings.query_quality)
        return self._capability

    async def pre_process(
        self,
        query: str,
        session_id: Optional[str],
        config: Any,
    ) -> tuple[str, Optional[dict[str, Any]]]:
        """Analyze query dimensions and prompt for missing info.

        Args:
            query: The user's query.
            session_id: Session ID for multi-turn state.
            config: QueryConfig instance.

        Returns:
            (query, None) if dimensions are complete,
            (query, prompt_info) if user needs to provide more info.
        """
        try:
            capability = await self._get_capability()
            from rag_service.models.query_quality import QueryQualityRequest

            request = QueryQualityRequest(
                query=query,
                session_id=session_id or "",
            )
            result = await capability.execute(request)

            # If quality score is below threshold, return prompt info
            if result.quality_score < 0.7 and result.prompt_text:
                return query, {
                    "action": "prompt",
                    "prompt_text": result.prompt_text,
                    "session_id": result.session_id,
                    "quality_score": result.quality_score,
                    "dimensions": {
                        d.name: {"status": d.status, "value": d.value}
                        for d in result.dimensions
                    } if result.dimensions else {},
                    "feedback": result.feedback,
                }

            # If session is active, use enriched query
            enriched_query = query
            if hasattr(result, "enriched_query") and result.enriched_query:
                enriched_query = result.enriched_query

            return enriched_query, None

        except Exception as e:
            logger.warning(
                "DimensionGatherQuality pre_process failed, falling back to basic",
                extra={"error": str(e)},
            )
            return query, None

    async def post_process(
        self,
        answer: str,
        chunks: list[dict[str, Any]],
        session_id: Optional[str],
    ) -> dict[str, Any]:
        """Return quality metadata from dimension analysis.

        Returns:
            Dictionary with quality_score and feedback.
        """
        return {
            "quality_enhanced": True,
            "quality_mode": "dimension_gather",
            "session_id": session_id,
        }


class ConversationalQuality:
    """Conversational query quality strategy with slot extraction.

    Delegates to the existing ConversationalQueryCapability during transition.
    Implements structured slot extraction, business domain classification,
    and colloquial term mapping.
    """

    def __init__(self) -> None:
        """Initialize ConversationalQuality."""
        self._capability = None

    async def _get_capability(self):
        """Get or create the underlying ConversationalQueryCapability."""
        if self._capability is None:
            from rag_service.capabilities.conversational_query import ConversationalQueryCapability
            from rag_service.config import get_settings
            settings = get_settings()
            self._capability = ConversationalQueryCapability(config=settings.conversational_query)
        return self._capability

    async def pre_process(
        self,
        query: str,
        session_id: Optional[str],
        config: Any,
    ) -> tuple[str, Optional[dict[str, Any]]]:
        """Extract slots and generate structured query.

        Args:
            query: The user's query.
            session_id: Session ID for conversation state.
            config: QueryConfig instance.

        Returns:
            (processed_query, prompt_info) with slot extraction results.
        """
        try:
            capability = await self._get_capability()

            # Build input for the capability
            from rag_service.capabilities.conversational_query import ConversationalQueryInput

            cap_input = ConversationalQueryInput(
                query=query,
                session_id=session_id or "",
            )

            result = await capability.execute(cap_input)

            # If confidence is low, prompt for more info
            confidence = getattr(result, "confidence", 1.0)
            if confidence < 0.6 and hasattr(result, "prompt_text") and result.prompt_text:
                return query, {
                    "action": "prompt",
                    "prompt_text": result.prompt_text,
                    "session_id": getattr(result, "session_id", session_id),
                    "quality_score": confidence,
                }

            # Use the generated query if available
            processed_query = query
            if hasattr(result, "generated_query") and result.generated_query:
                processed_query = result.generated_query

            return processed_query, None

        except Exception as e:
            logger.warning(
                "ConversationalQuality pre_process failed, falling back to basic",
                extra={"error": str(e)},
            )
            return query, None

    async def post_process(
        self,
        answer: str,
        chunks: list[dict[str, Any]],
        session_id: Optional[str],
    ) -> dict[str, Any]:
        """Return quality metadata from conversational analysis.

        Returns:
            Dictionary with quality_score and session info.
        """
        return {
            "quality_enhanced": True,
            "quality_mode": "conversational",
            "session_id": session_id,
        }
