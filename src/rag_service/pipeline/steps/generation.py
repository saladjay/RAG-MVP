"""
GenerationStep — answer generation from query and retrieved chunks.

Uses LiteLLMGateway for inference. Raises GenerationError on failure
(core error — pipeline halts).

Prompt loaded via PromptClient with fallback to default template.

API Reference:
- Location: src/rag_service/pipeline/steps/generation.py
- Reads: processed_query, chunks, reasoning_result
- Writes: answer
"""

from typing import Any, AsyncGenerator, Optional

from rag_service.core.exceptions import GenerationError
from rag_service.core.logger import get_logger
from rag_service.pipeline.context import PipelineContext

logger = get_logger(__name__)

# Fallback prompt template (used when PromptClient is unavailable)
_FALLBACK_PROMPT_TEMPLATE = """Based on the following context, answer the question. If the context does not contain enough information, say so.

Context:
{context}

Question: {query}

Answer:"""

_FALLBACK_STRICT_PROMPT_TEMPLATE = """Based on the following context, answer the question. You MUST only use information directly stated in the context. Do not add any information not present in the context. If the context does not contain enough information, say so.

Context:
{context}

Question: {query}

Answer:"""


class GenerationStep:
    """Generation step — produce answer from query and chunks.

    Uses LiteLLMGateway for LLM inference. Loads prompt via PromptClient
    with fallback to default template when PromptClient is unavailable.
    """

    def __init__(self, prompt_template: str = "qa_answer_generation") -> None:
        """Initialize with prompt template ID.

        Args:
            prompt_template: PromptClient template ID for generation.
        """
        self._prompt_template = prompt_template
        self._prompt_client = None

    async def _get_prompt_client(self):
        """Get or create the prompt client."""
        if self._prompt_client is None:
            try:
                from rag_service.services.prompt_client import get_prompt_client
                self._prompt_client = await get_prompt_client()
            except Exception as e:
                logger.warning(f"PromptClient unavailable: {e}")
                self._prompt_client = None
        return self._prompt_client

    @property
    def name(self) -> str:
        """Step identifier."""
        return "generation"

    async def _build_prompt(
        self,
        context_text: str,
        query: str,
        trace_id: str,
        strict: bool = False,
    ) -> str:
        """Build generation prompt, using PromptClient if available.

        Args:
            context_text: Formatted chunk context.
            query: User query.
            trace_id: Trace ID.
            strict: Use strict prompt variant for regeneration attempts.

        Returns:
            Prompt string.
        """
        client = await self._get_prompt_client()
        if client is not None:
            try:
                template_id = self._prompt_template
                if strict:
                    template_id = template_id + "_strict"
                return await client.get_prompt(
                    template_id=template_id,
                    variables={"context": context_text, "query": query},
                    trace_id=trace_id,
                )
            except Exception as e:
                logger.warning(
                    f"PromptClient get_prompt failed, using fallback: {e}",
                    extra={"trace_id": trace_id},
                )

        # Fallback to hardcoded template
        template = _FALLBACK_STRICT_PROMPT_TEMPLATE if strict else _FALLBACK_PROMPT_TEMPLATE
        return template.format(context=context_text, query=query)

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """Execute answer generation.

        Args:
            context: Pipeline context with processed_query and chunks set.

        Returns:
            Updated context with answer populated.

        Raises:
            GenerationError: If LLM generation fails (core error).
        """
        context_parts = []
        for i, chunk in enumerate(context.chunks[:10]):
            content = chunk.get("content", "")
            if content:
                context_parts.append(f"[{i+1}] {content}")

        context_text = (
            "\n\n".join(context_parts)
            if context_parts
            else "No relevant context found."
        )

        prompt = await self._build_prompt(
            context_text=context_text,
            query=context.processed_query,
            trace_id=context.trace_id,
        )

        try:
            from rag_service.inference.gateway import get_gateway

            gateway = await get_gateway()
            result = await gateway.acomplete_routed(prompt=prompt)
            context.answer = result.text

            logger.info(
                "Answer generated",
                extra={
                    "trace_id": context.trace_id,
                    "answer_length": len(context.answer),
                },
            )

        except GenerationError:
            raise
        except Exception as e:
            raise GenerationError(
                message=f"Answer generation failed: {context.processed_query[:80]}",
                detail=str(e),
            ) from e

        return context

    async def execute_stream(self, context: PipelineContext) -> AsyncGenerator[str, None]:
        """Stream answer generation — yields tokens as they are generated.

        Args:
            context: Pipeline context with processed_query and chunks set.

        Yields:
            Token strings as they are generated.

        Raises:
            GenerationError: If streaming setup fails.
        """
        context_parts = []
        for i, chunk in enumerate(context.chunks[:10]):
            content = chunk.get("content", "")
            if content:
                context_parts.append(f"[{i+1}] {content}")

        context_text = (
            "\n\n".join(context_parts)
            if context_parts
            else "No relevant context found."
        )

        prompt = await self._build_prompt(
            context_text=context_text,
            query=context.processed_query,
            trace_id=context.trace_id,
        )

        try:
            from rag_service.inference.gateway import get_gateway

            gateway = await get_gateway()

            if gateway.provider == "cloud_http":
                http_gw = gateway._get_http_gateway()
                async for token in http_gw.astream_complete(prompt=prompt):
                    yield token
            elif gateway.provider == "glm":
                glm_gw = gateway._get_glm_gateway()
                async for token in glm_gw.astream_complete(prompt=prompt):
                    yield token
            else:
                # Fallback: complete and yield all at once
                result = await gateway.acomplete_routed(prompt=prompt)
                yield result.text

        except GenerationError:
            raise
        except Exception as e:
            raise GenerationError(
                message=f"Streaming generation failed: {context.processed_query[:80]}",
                detail=str(e),
            ) from e

    async def get_health(self) -> dict[str, Any]:
        """Return health status of generation dependencies."""
        try:
            from rag_service.inference.gateway import get_gateway

            gateway = await get_gateway()
            return {
                "step": "generation",
                "status": "healthy",
                "dependencies": {"gateway": gateway.provider},
            }
        except Exception as e:
            return {
                "step": "generation",
                "status": "unhealthy",
                "dependencies": {"gateway": f"unavailable: {e}"},
            }
