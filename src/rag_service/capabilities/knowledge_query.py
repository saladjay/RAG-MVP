"""
Knowledge Query Capability for RAG Service.

This capability provides unified access to knowledge base operations
including search, retrieval, and similarity matching. It wraps the Milvus
component and is only accessed via the Capability interface.

HTTP endpoints use this capability - they NEVER access Milvus directly.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator

from rag_service.capabilities.base import (
    Capability,
    CapabilityInput,
    CapabilityOutput,
    CapabilityValidationResult,
)
from rag_service.core.exceptions import RetrievalError


class KnowledgeQueryInput(CapabilityInput):
    """
    Input for knowledge query operations.

    Attributes:
        query: The search query text.
        top_k: Number of results to return.
        filters: Optional filters to apply to search.
        collection_name: Name of the collection to search.
    """

    query: str = Field(..., min_length=1, description="Search query text")
    top_k: int = Field(default=5, ge=1, le=100, description="Number of results")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Search filters")
    collection_name: str = Field(default="knowledge_base", description="Collection name")

    @model_validator(mode="after")
    def validate_query_not_empty(self) -> "KnowledgeQueryInput":
        """Validate query is not just whitespace."""
        if not self.query.strip():
            raise ValueError("Query cannot be empty or whitespace")
        return self


class RetrievedChunk(BaseModel):
    """
    A retrieved chunk from the knowledge base.

    Attributes:
        id: Chunk identifier.
        content: Chunk text content.
        metadata: Associated metadata.
        score: Similarity score (lower is more similar).
    """

    id: str = Field(..., description="Chunk identifier")
    content: str = Field(..., description="Chunk content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Chunk metadata")
    score: float = Field(..., ge=0, description="Similarity score")


class KnowledgeQueryOutput(CapabilityOutput):
    """
    Output from knowledge query operations.

    Attributes:
        chunks: List of retrieved chunks.
        total_found: Total number of matching chunks.
        query_time_ms: Time taken for query in milliseconds.
    """

    chunks: List[RetrievedChunk] = Field(default_factory=list, description="Retrieved chunks")
    total_found: int = Field(default=0, ge=0, description="Total matches")
    query_time_ms: Optional[float] = Field(default=None, description="Query time in ms")


class KnowledgeQueryCapability(Capability[KnowledgeQueryInput, KnowledgeQueryOutput]):
    """
    Capability for querying the knowledge base.

    This capability wraps Milvus vector database operations and provides
    a unified interface for knowledge base queries. HTTP endpoints use this
    capability to access Milvus - they NEVER access Milvus directly.

    Features:
    - Vector similarity search
    - Metadata filtering
    - Configurable top-k results
    - Query performance tracking
    """

    def __init__(self, milvus_client: Optional[Any] = None) -> None:
        """
        Initialize KnowledgeQueryCapability.

        Args:
            milvus_client: Milvus client instance (injected dependency).
        """
        super().__init__()
        self._milvus_client = milvus_client

    async def execute(self, input_data: KnowledgeQueryInput) -> KnowledgeQueryOutput:
        """
        Execute knowledge base query.

        Args:
            input_data: Query parameters.

        Returns:
            Retrieved chunks with similarity scores.

        Raises:
            RetrievalError: If query execution fails.
        """
        import time

        start_time = time.time()

        # TODO: Implement actual Milvus query
        # For now, return mock output
        try:
            # Mock implementation
            chunks = [
                RetrievedChunk(
                    id="mock_chunk_1",
                    content=f"Mock result for query: {input_data.query[:50]}...",
                    metadata={"source": "mock"},
                    score=0.1,
                ),
            ]

            elapsed_ms = (time.time() - start_time) * 1000

            return KnowledgeQueryOutput(
                chunks=chunks[:input_data.top_k],
                total_found=len(chunks),
                query_time_ms=elapsed_ms,
                trace_id=input_data.trace_id,
                metadata={"collection": input_data.collection_name},
            )

        except Exception as e:
            raise RetrievalError(
                message=f"Query failed: {input_data.query}",
                detail=str(e),
            ) from e

    def validate_input(self, input_data: KnowledgeQueryInput) -> CapabilityValidationResult:
        """
        Validate knowledge query input.

        Args:
            input_data: Input to validate.

        Returns:
            Validation result.
        """
        errors = []
        warnings = []

        # Validate query
        if not input_data.query or not input_data.query.strip():
            errors.append("Query cannot be empty")

        # Validate top_k
        if input_data.top_k < 1:
            errors.append("top_k must be at least 1")
        elif input_data.top_k > 100:
            warnings.append("top_k > 100 may impact performance")

        # Validate collection name
        if not input_data.collection_name:
            errors.append("Collection name is required")

        return CapabilityValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def get_health(self) -> Dict[str, Any]:
        """
        Get health status of knowledge base.

        Returns:
            Health status information.
        """
        health = super().get_health()

        # Check Milvus connectivity
        if self._milvus_client:
            try:
                # TODO: Implement actual health check
                health["milvus"] = "connected"
            except Exception as e:
                health["milvus"] = f"disconnected: {e}"
                health["status"] = "unhealthy"
        else:
            health["milvus"] = "not_configured"
            health["status"] = "degraded"

        return health
