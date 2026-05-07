"""
Pipeline Protocol definitions for RAG Service.

Defines the StepCapability and MemoryCapability interfaces using
typing.Protocol for structural subtyping. No inheritance required.

API Reference:
- StepCapability: Protocol for all pipeline steps
- MemoryCapability: Protocol for session state management
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Protocol, runtime_checkable

if TYPE_CHECKING:
    from rag_service.pipeline.context import PipelineContext


@runtime_checkable
class StepCapability(Protocol):
    """Atomic pipeline step interface.

    All pipeline steps MUST implement this interface. Uses structural
    subtyping (Protocol) — no inheritance required.

    Contract:
    - execute() reads from and writes to the shared PipelineContext
    - execute() MUST return the same context object (mutated, not replaced)
    - To abort: set context.should_abort = True and context.abort_prompt = "msg"
    - Steps MUST NOT record their own timing (handled by PipelineRunner)
    """

    @property
    def name(self) -> str:
        """Step identifier for logging, timing, and policy lookups.

        Must be unique within a pipeline.
        """
        ...

    async def execute(self, context: PipelineContext) -> PipelineContext:
        """Execute the step.

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


@runtime_checkable
class MemoryCapability(Protocol):
    """Session state management interface.

    Not a pipeline step — called by ExtractionStep internally for
    multi-turn quality enhancement modes.
    """

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
