"""
Langfuse Client Wrapper for Prompt Layer Observability.

This module provides async trace capture for the Prompt Layer using Langfuse SDK.
It handles:
- Prompt template version tracking
- Variable interpolation tracking
- Retrieved document injection tracking
- Non-blocking trace flush

The Langfuse client is part of the three-layer observability stack:
- Prompt Layer (this module): Prompt template management and trace correlation
- LLM Layer (litellm_observer.py): Model invocation metrics
- Agent Layer (phidata_observer.py): AI task execution behavior

API Reference:
- Location: src/rag_service/observability/langfuse_client.py
- Class: LangfuseClient
- Method: create_trace() -> Initialize a new trace
- Method: create_span() -> Create nested span for operations
- Method: update_span() -> Update span with results
- Method: flush_trace() -> Non-blocking flush for specific trace
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from rag_service.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PromptTrace:
    """Represents a prompt layer trace."""

    trace_id: str
    name: str = "rag-query"
    input: Dict[str, Any] = field(default_factory=dict)
    output: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    status: str = "active"

    # Prompt-specific data
    template_version: Optional[str] = None
    template_name: Optional[str] = None
    variables: Dict[str, Any] = field(default_factory=dict)
    retrieved_docs: List[Dict[str, Any]] = field(default_factory=list)

    # Nested spans for detailed tracking
    spans: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "trace_id": self.trace_id,
            "name": self.name,
            "input": self.input,
            "output": self.output,
            "metadata": self.metadata,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status,
            "template_version": self.template_version,
            "template_name": self.template_name,
            "variables": self.variables,
            "retrieved_docs": self.retrieved_docs,
            "spans": self.spans,
        }


@dataclass
class PromptSpan:
    """Represents a span within a prompt trace."""

    span_id: str
    trace_id: str
    name: str
    span_type: str  # "retrieval", "inference", "completion"
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "name": self.name,
            "span_type": self.span_type,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "metadata": self.metadata,
        }


class LangfuseClient:
    """
    Async wrapper for Langfuse SDK for Prompt Layer observability.

    This client provides non-blocking trace capture for prompt-related operations.
    It is designed to work without Langfuse dependency for development/testing,
    gracefully handling missing Langfuse installation.

    In production with Langfuse available, this client would use the official
    Langfuse Python SDK with async support.

    Attributes:
        _client: Optional Langfuse async client (None if not available)
        _enabled: Whether Langfuse integration is enabled
        _traces: In-memory store for prompt traces
        _spans: In-memory store for prompt spans
        _lock: Async lock for thread-safe operations
    """

    def __init__(self, enabled: bool = True, public_key: Optional[str] = None, secret_key: Optional[str] = None):
        """Initialize the Langfuse client.

        Args:
            enabled: Whether Langfuse integration is enabled
            public_key: Optional Langfuse public key
            secret_key: Optional Langfuse secret key
        """
        self._enabled = enabled
        self._public_key = public_key
        self._secret_key = secret_key
        self._client = None
        self._traces: Dict[str, PromptTrace] = {}
        self._spans: Dict[str, PromptSpan] = {}
        self._lock = asyncio.Lock()

        # Try to initialize Langfuse client if available
        if self._enabled:
            self._init_langfuse_client()

    def _init_langfuse_client(self) -> None:
        """Initialize Langfuse client if SDK is available.

        This method attempts to import and initialize the Langfuse SDK.
        If the SDK is not available, the client operates in mock mode
        with in-memory storage only.
        """
        try:
            from langfuse import Langfuse
            from langfuse.async_client import AsyncLangfuse

            # Initialize async client if credentials provided
            if self._public_key and self._secret_key:
                self._client = AsyncLangfuse(
                    public_key=self._public_key,
                    secret_key=self._secret_key,
                )
                logger.info("Langfuse async client initialized")
            else:
                # Check for environment variables
                self._client = AsyncLangfuse()
                logger.info("Langfuse async client initialized from environment")
        except ImportError:
            logger.warning(
                "Langfuse SDK not available, operating in mock mode. "
                "Traces will be stored in-memory only."
            )
            self._client = None
        except Exception as e:
            logger.warning(
                f"Failed to initialize Langfuse client: {e}. "
                "Operating in mock mode."
            )
            self._client = None

    async def create_trace(
        self,
        trace_id: str,
        prompt: str,
        context: Dict[str, Any],
        name: str = "rag-query",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Create a new prompt trace.

        Initializes a trace in the Prompt Layer for tracking prompt-related
        operations including variable interpolation and document injection.

        Args:
            trace_id: Unified trace identifier
            prompt: User's input prompt/question
            context: User context dictionary
            name: Optional trace name (default: "rag-query")
            metadata: Optional additional metadata
        """
        trace = PromptTrace(
            trace_id=trace_id,
            name=name,
            input={"prompt": prompt, "context": context},
            metadata=metadata or {},
        )

        async with self._lock:
            self._traces[trace_id] = trace

        # Try to create trace in Langfuse if available
        if self._client:
            try:
                await self._client.trace(
                    id=trace_id,
                    name=name,
                    input={"prompt": prompt, "context": context},
                    metadata=metadata or {},
                )
            except Exception as e:
                logger.warning(
                    "Failed to create trace in Langfuse",
                    extra={"trace_id": trace_id, "error": str(e)},
                )

        logger.debug(
            "Created prompt trace",
            extra={"trace_id": trace_id, "name": name},
        )

    async def create_span(
        self,
        trace_id: str,
        span_id: str,
        name: str,
        span_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Create a nested span within a trace.

        Spans represent individual operations within a trace, such as
        retrieval, inference, or completion.

        Args:
            trace_id: Unified trace identifier
            span_id: Unique span identifier
            name: Human-readable span name
            span_type: Type of operation ("retrieval", "inference", "completion")
            metadata: Optional span-specific metadata
        """
        span = PromptSpan(
            span_id=span_id,
            trace_id=trace_id,
            name=name,
            span_type=span_type,
            metadata=metadata or {},
        )

        async with self._lock:
            self._spans[span_id] = span
            if trace_id in self._traces:
                self._traces[trace_id].spans.append(span.to_dict())

        # Try to create span in Langfuse if available
        if self._client:
            try:
                trace = await self._client.trace(id=trace_id)
                await trace.span(
                    id=span_id,
                    name=name,
                    metadata=metadata or {},
                )
            except Exception as e:
                logger.warning(
                    "Failed to create span in Langfuse",
                    extra={"trace_id": trace_id, "span_id": span_id, "error": str(e)},
                )

        logger.debug(
            "Created prompt span",
            extra={"trace_id": trace_id, "span_id": span_id, "span_type": span_type},
        )

    async def update_span(
        self,
        span_id: str,
        output: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        end_time: Optional[datetime] = None,
    ) -> None:
        """Update an existing span with results.

        Args:
            span_id: Span identifier
            output: Optional span output data
            metadata: Optional additional metadata to merge
            end_time: Optional explicit end time (default: now)
        """
        async with self._lock:
            span = self._spans.get(span_id)
            if span:
                span.end_time = end_time or datetime.utcnow()
                if output:
                    span.metadata["output"] = output
                if metadata:
                    span.metadata.update(metadata)

        # Try to update span in Langfuse if available
        if self._client:
            try:
                # Note: Actual Langfuse SDK span update would go here
                # For now, we rely on in-memory storage
                pass
            except Exception as e:
                logger.warning(
                    "Failed to update span in Langfuse",
                    extra={"span_id": span_id, "error": str(e)},
                )

        logger.debug(
            "Updated prompt span",
            extra={"span_id": span_id},
        )

    async def track_prompt_version(
        self,
        trace_id: str,
        template_name: str,
        template_version: str,
        variables: Dict[str, Any],
    ) -> None:
        """Track prompt template version and variable interpolation.

        Records which prompt template was used and how variables were
        interpolated into the template.

        Args:
            trace_id: Unified trace identifier
            template_name: Name of the prompt template
            template_version: Version of the template
            variables: Variables interpolated into the template
        """
        async with self._lock:
            trace = self._traces.get(trace_id)
            if trace:
                trace.template_name = template_name
                trace.template_version = template_version
                trace.variables.update(variables)

        logger.debug(
            "Tracked prompt version",
            extra={
                "trace_id": trace_id,
                "template_name": template_name,
                "template_version": template_version,
                "variable_count": len(variables),
            },
        )

    async def track_retrieved_docs(
        self,
        trace_id: str,
        docs: List[Dict[str, Any]],
    ) -> None:
        """Track retrieved documents injected into prompt.

        Records which documents were retrieved and injected into the
        prompt for context.

        Args:
            trace_id: Unified trace identifier
            docs: List of retrieved documents with metadata
        """
        async with self._lock:
            trace = self._traces.get(trace_id)
            if trace:
                trace.retrieved_docs.extend(docs)

        logger.debug(
            "Tracked retrieved documents",
            extra={
                "trace_id": trace_id,
                "doc_count": len(docs),
            },
        )

    async def complete_trace(
        self,
        trace_id: str,
        output: Optional[Dict[str, Any]] = None,
        status: str = "completed",
    ) -> None:
        """Mark a trace as completed.

        Args:
            trace_id: Unified trace identifier
            output: Optional trace output data
            status: Final status ("completed", "failed")
        """
        async with self._lock:
            trace = self._traces.get(trace_id)
            if trace:
                trace.end_time = datetime.utcnow()
                trace.status = status
                if output:
                    trace.output = output

        logger.debug(
            "Completed prompt trace",
            extra={"trace_id": trace_id, "status": status},
        )

    async def flush_trace(self, trace_id: str) -> None:
        """Non-blocking flush for a specific trace.

        Flushes trace data to Langfuse (or in-memory storage) without
        blocking the request response.

        Args:
            trace_id: Unified trace identifier
        """
        # In a real implementation with Langfuse SDK, this would call
        # await self._client.flush_async()
        # For now, data is already stored in-memory

        logger.debug(
            "Flushed prompt trace",
            extra={"trace_id": trace_id},
        )

    async def get_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve trace data by ID.

        Args:
            trace_id: Unified trace identifier

        Returns:
            Trace data dictionary, or None if not found
        """
        async with self._lock:
            trace = self._traces.get(trace_id)

        if not trace:
            return None

        return trace.to_dict()

    async def get_all_traces(self) -> List[Dict[str, Any]]:
        """Get all prompt traces.

        Returns:
            List of all trace dictionaries
        """
        async with self._lock:
            return [trace.to_dict() for trace in self._traces.values()]

    def is_enabled(self) -> bool:
        """Check if Langfuse client is enabled.

        Returns:
            True if Langfuse integration is enabled
        """
        return self._enabled and self._client is not None


# Global singleton instance
_langfuse_client: Optional[LangfuseClient] = None
_client_lock = asyncio.Lock()


async def get_langfuse_client() -> LangfuseClient:
    """Get or create the global Langfuse client singleton.

    Returns:
        The global LangfuseClient instance
    """
    global _langfuse_client

    async with _client_lock:
        if _langfuse_client is None:
            # Read configuration from environment
            import os
            enabled = os.getenv("LANGFUSE_ENABLED", "true").lower() == "true"
            public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
            secret_key = os.getenv("LANGFUSE_SECRET_KEY")

            _langfuse_client = LangfuseClient(
                enabled=enabled,
                public_key=public_key,
                secret_key=secret_key,
            )
            logger.info("Initialized global Langfuse client")

    return _langfuse_client


def reset_langfuse_client() -> None:
    """Reset the global Langfuse client instance.

    This is primarily used for testing to ensure clean state between tests.
    """
    global _langfuse_client
    _langfuse_client = None
    logger.debug("Reset global Langfuse client")
