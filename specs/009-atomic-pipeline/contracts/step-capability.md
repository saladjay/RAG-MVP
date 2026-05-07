# Contract: StepCapability Interface

**Feature**: 009-atomic-pipeline
**Date**: 2026-05-07

## StepCapability Protocol

All pipeline steps MUST implement this interface. It uses structural subtyping (`typing.Protocol`) — no inheritance required.

### Interface Definition

```python
from typing import Any, Protocol, runtime_checkable

@runtime_checkable
class StepCapability(Protocol):
    """Atomic pipeline step interface."""

    @property
    def name(self) -> str:
        """Step identifier for logging, timing, and policy lookups.
        Must be unique within a pipeline."""
        ...

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """Execute the step.

        Reads from and writes to the shared PipelineContext.
        MUST return the same context object (mutated, not replaced).

        To abort the pipeline: set context.should_abort = True
                                 and context.abort_prompt = "message"

        Args:
            context: Shared pipeline state.

        Returns:
            The updated context object.
        """
        ...

    async def get_health(self) -> dict[str, Any]:
        """Return health status of this step's dependencies.

        Returns:
            Dict with at least {"status": "healthy"|"degraded"|"unhealthy"}.
        """
        ...
```

### Context Contract

Each step follows this read/write convention:

| Step | Reads | Writes |
|------|-------|--------|
| ExtractionStep | `original_query`, `session_id` | `processed_query`, `quality_meta`, `should_abort`, `abort_prompt` |
| RewriteStep | `processed_query` | `processed_query` (updated) |
| RetrievalStep | `processed_query`, `top_k`, `request_context` | `chunks` |
| ReasoningStep | `chunks`, `processed_query` | `reasoning_result` |
| GenerationStep | `processed_query`, `chunks`, `reasoning_result` | `answer` |
| VerificationStep | `answer`, `chunks` | `hallucination_status` |
| ExecutionStep | `answer`, `chunks`, `hallucination_status` | `quality_meta` (finalized) |

### Error Contract

| Error type | Behavior | Step examples |
|------------|----------|---------------|
| Core errors (`RetrievalError`, `GenerationError`) | Pipeline halts, error propagates to API layer | RetrievalStep, GenerationStep |
| Non-core errors | Step degrades gracefully, pipeline continues | RewriteStep (returns original), VerificationStep (marks unchecked), ExtractionStep (falls back to basic) |
| Abort signal (`should_abort=True`) | Pipeline stops normally, returns prompt to user | ExtractionStep (quality mode needs more info) |

### Policy Skip Contract

PipelineRunner calls `_should_run(step, policy)` before each step:

| Step | Policy field | Default |
|------|-------------|---------|
| ExtractionStep | `enable_extraction` | `True` |
| RewriteStep | `enable_rewrite` | `True` |
| RetrievalStep | Always runs | — |
| ReasoningStep | `enable_reasoning` | `False` |
| GenerationStep | Always runs | — |
| VerificationStep | `enable_verification` | `True` |
| ExecutionStep | `enable_execution` | `True` |

### Timing Contract

PipelineRunner automatically records timing for each step:

```python
context.timing[step.name] = elapsed_ms
```

Steps MUST NOT record their own timing. This is handled by the runner.

### Health Check Contract

Each step's `get_health()` returns:

```python
{
    "step": "retrieval",
    "status": "healthy",          # healthy | degraded | unhealthy
    "dependencies": {
        "milvus": "connected",     # or "unavailable"
        "external_kb": "reachable"
    }
}
```

## MemoryCapability Contract

Separate Protocol for session state management. Not a pipeline step — called by ExtractionStep internally.

```python
@runtime_checkable
class MemoryCapability(Protocol):
    async def get_session(self, session_id: str) -> Optional[dict]:
        """Retrieve session state. Returns None if not found."""
        ...

    async def save_session(self, session_id: str, data: dict, ttl: int = 900) -> None:
        """Persist session state with TTL."""
        ...

    async def get_belief_state(self, session_id: str) -> Optional[dict]:
        """Retrieve belief state. Returns None if not found."""
        ...

    async def save_belief_state(self, session_id: str, data: dict, ttl: int = 900) -> None:
        """Persist belief state with TTL."""
        ...
```
