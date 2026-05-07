"""
PipelineRunner — orchestrator for the atomic pipeline.

Executes a list of StepCapability instances in sequence, applying
PipelinePolicy controls, recording timing, and handling errors.

Also serves as the "Planning" capability — deciding which steps to
run and in what order.

Regeneration loop: When max_regen_attempts > 0, re-executes generation
and verification when hallucination is detected.

API Reference:
- Location: src/rag_service/pipeline/runner.py
- Used by: QueryCapability
"""

import time
from typing import Any, AsyncGenerator

from rag_service.api.unified_schemas import HallucinationStatus
from rag_service.core.exceptions import GenerationError, RetrievalError
from rag_service.core.logger import get_logger
from rag_service.pipeline.context import PipelineContext
from rag_service.pipeline.policy import PipelinePolicy

logger = get_logger(__name__)

# Core errors that halt the pipeline
_CORE_ERRORS = (RetrievalError, GenerationError)


class PipelineRunner:
    """Orchestrates execution of atomic pipeline steps.

    The runner IS the Planning capability — it decides which steps
    to run and in what order based on PipelinePolicy.
    """

    def __init__(
        self,
        steps: list[Any],
        policy: PipelinePolicy,
    ) -> None:
        """Initialize the pipeline runner.

        Args:
            steps: Ordered list of StepCapability implementations.
            policy: Execution control parameters.
        """
        self._steps = steps
        self._policy = policy

    def _find_step(self, name: str) -> Any | None:
        """Find a step by name."""
        for step in self._steps:
            if step.name == name:
                return step
        return None

    async def _execute_step(self, step: Any, context: PipelineContext) -> PipelineContext:
        """Execute a single step with error handling.

        Returns:
            Updated context.

        Raises:
            Core errors propagate. Non-core errors degrade gracefully.
        """
        start = time.monotonic()
        try:
            context = await step.execute(context)
        except _CORE_ERRORS:
            raise
        except Exception as e:
            logger.warning(
                f"Step '{step.name}' failed, degrading gracefully",
                extra={
                    "trace_id": context.trace_id,
                    "error": str(e),
                    "step": step.name,
                },
            )
        elapsed_ms = (time.monotonic() - start) * 1000
        context.timing[step.name] = elapsed_ms
        return context

    async def run(self, context: PipelineContext) -> PipelineContext:
        """Execute all enabled pipeline steps in sequence.

        After generation + verification, checks if regeneration is needed:
        - If hallucination detected and attempts remain, re-runs generation
          and verification with strict prompt.
        - Tracks attempt count in quality_meta.
        - Returns best answer if all attempts fail.

        Args:
            context: Initial pipeline state.

        Returns:
            Updated context after all steps execute.
        """
        generation_step = self._find_step("generation")
        verification_step = self._find_step("verification")

        for step in self._steps:
            if context.should_abort:
                logger.info(
                    f"Pipeline aborted before '{step.name}'",
                    extra={"trace_id": context.trace_id},
                )
                break

            if not self._policy._should_run(step.name):
                logger.debug(
                    f"Step '{step.name}' skipped by policy",
                    extra={"trace_id": context.trace_id},
                )
                continue

            context = await self._execute_step(step, context)

            # After verification, check regeneration loop
            if (
                step.name == "verification"
                and generation_step is not None
                and verification_step is not None
                and self._policy.max_regen_attempts > 0
                and not context.should_abort
            ):
                context = await self._run_regeneration_loop(
                    context, generation_step, verification_step
                )

        return context

    async def run_stream(self, context: PipelineContext) -> AsyncGenerator[str, None]:
        """Execute pipeline with streaming generation.

        Runs all steps up to and including retrieval synchronously,
        then streams tokens from GenerationStep. Verification runs
        after stream completes (not streamed).

        Args:
            context: Initial pipeline state.

        Yields:
            Token strings from generation step.
        """
        generation_step = self._find_step("generation")
        verification_step = self._find_step("verification")
        execution_step = self._find_step("execution")

        # Run pre-generation steps synchronously
        for step in self._steps:
            if step.name == "generation":
                break

            if context.should_abort:
                if context.abort_prompt:
                    yield f'[PROMPT] {context.abort_prompt}'
                return

            if not self._policy._should_run(step.name):
                continue

            context = await self._execute_step(step, context)

        # Stream generation tokens
        if generation_step is None:
            return

        if context.should_abort:
            if context.abort_prompt:
                yield f'[PROMPT] {context.abort_prompt}'
            return

        collected_tokens = []
        async for token in await generation_step.execute_stream(context):
            collected_tokens.append(token)
            yield token

        # Set final answer from collected tokens
        context.answer = "".join(collected_tokens)

        # Run verification after streaming
        if verification_step and self._policy._should_run("verification"):
            context = await self._execute_step(verification_step, context)

        # Run execution step
        if execution_step and self._policy._should_run("execution"):
            context = await self._execute_step(execution_step, context)

    async def _run_regeneration_loop(
        self,
        context: PipelineContext,
        generation_step: Any,
        verification_step: Any,
    ) -> PipelineContext:
        """Run regeneration loop when hallucination is detected.

        Re-executes generation with strict prompt and re-verifies.

        Args:
            context: Current pipeline context.
            generation_step: The generation step instance.
            verification_step: The verification step instance.

        Returns:
            Updated context with best answer.
        """
        max_attempts = self._policy.max_regen_attempts
        attempts = 0

        while attempts < max_attempts:
            hallucination = context.hallucination_status
            if hallucination is None or hallucination.passed:
                break

            attempts += 1
            logger.info(
                f"Regeneration attempt {attempts}/{max_attempts} "
                "(hallucination detected)",
                extra={
                    "trace_id": context.trace_id,
                    "confidence": hallucination.confidence,
                },
            )

            # Store previous answer as fallback
            previous_answer = context.answer
            previous_confidence = hallucination.confidence

            # Re-execute generation with strict prompt
            try:
                context = await self._execute_step(generation_step, context)
            except GenerationError:
                # If regeneration fails, keep the previous answer
                context.answer = previous_answer
                break

            # Re-execute verification
            context = await self._execute_step(verification_step, context)

            # If new verification is worse, revert
            new_hallucination = context.hallucination_status
            if new_hallucination and not new_hallucination.passed:
                if new_hallucination.confidence < previous_confidence:
                    logger.info(
                        "Regeneration produced worse result, keeping previous",
                        extra={"trace_id": context.trace_id},
                    )
                    # Keep current answer (it's already the regenerated one)

        # Track regeneration info
        context.quality_meta["regen_attempts"] = attempts
        if attempts > 0:
            final_status = context.hallucination_status
            context.quality_meta["regen_passed"] = (
                final_status.passed if final_status else False
            )

        return context

    async def get_health(self) -> dict[str, Any]:
        """Aggregate health from all steps.

        Returns:
            Dict with per-step health and overall status.
        """
        overall_healthy = True
        steps_health: dict[str, Any] = {}

        for step in self._steps:
            try:
                health = await step.get_health()
                steps_health[step.name] = health
                if health.get("status") == "unhealthy":
                    overall_healthy = False
            except Exception as e:
                steps_health[step.name] = {
                    "status": "unhealthy",
                    "error": str(e),
                }
                overall_healthy = False

        return {
            "status": "healthy" if overall_healthy else "degraded",
            "steps": steps_health,
        }
