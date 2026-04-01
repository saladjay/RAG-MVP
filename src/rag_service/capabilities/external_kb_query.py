"""
External Knowledge Base Query Capability.

This capability provides access to the external HTTP knowledge base service.
It wraps the ExternalKBClient and provides a unified interface for querying
the external knowledge base.
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


class ExternalKBQueryInput(CapabilityInput):
    """
    Input for external knowledge base query operations.

    Attributes:
        query: The search query text.
        comp_id: Company unique code (e.g., N000131).
        file_type: File type (PublicDocReceive or PublicDocDispatch).
        doc_date: Optional document date filter.
        keyword: Optional secondary keyword.
        top_k: Number of results to return.
        score_min: Minimum score threshold.
        search_type: Search type (0=vector, 1=fulltext, 2=hybrid).
    """

    query: str = Field(..., min_length=1, description="Search query text")
    comp_id: str = Field(..., description="Company unique code, e.g., N000131")
    file_type: str = Field(
        default="PublicDocDispatch",
        description="File type: PublicDocReceive or PublicDocDispatch"
    )
    doc_date: Optional[str] = Field(default=None, description="Document date filter")
    keyword: Optional[str] = Field(default=None, description="Secondary keyword")
    top_k: int = Field(default=10, ge=1, le=100, description="Number of results")
    score_min: float = Field(default=0.0, description="Minimum score threshold")
    search_type: int = Field(
        default=1,
        ge=0,
        le=2,
        description="Search type: 0=vector, 1=fulltext, 2=hybrid"
    )

    @model_validator(mode="after")
    def validate_inputs(self) -> "ExternalKBQueryInput":
        """Validate input parameters."""
        if not self.query.strip():
            raise ValueError("Query cannot be empty or whitespace")

        if self.file_type not in ("PublicDocReceive", "PublicDocDispatch"):
            raise ValueError(f"Invalid file_type: {self.file_type}")

        if self.search_type not in (0, 1, 2):
            raise ValueError(f"Invalid search_type: {self.search_type}")

        return self


class ExternalKBChunk(BaseModel):
    """A retrieved chunk from the external knowledge base."""

    id: str = Field(..., description="Chunk identifier (segment_id)")
    chunk_id: str = Field(..., description="Chunk identifier (same as id)")
    content: str = Field(..., description="Chunk content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Chunk metadata")
    score: float = Field(..., description="Similarity score")
    source_doc: str = Field(..., description="Source document name")


class ExternalKBQueryOutput(CapabilityOutput):
    """
    Output from external knowledge base query operations.

    Attributes:
        chunks: List of retrieved chunks.
        total_found: Total number of matching chunks.
        query_time_ms: Time taken for query in milliseconds.
    """

    chunks: List[Dict[str, Any]] = Field(default_factory=list, description="Retrieved chunks")
    total_found: int = Field(default=0, ge=0, description="Total matches")
    query_time_ms: Optional[float] = Field(default=None, description="Query time in ms")


class ExternalKBQueryCapability(Capability[ExternalKBQueryInput, ExternalKBQueryOutput]):
    """
    Capability for querying the external HTTP knowledge base.

    This capability wraps the ExternalKBClient and provides a unified
    interface for external knowledge base queries. HTTP endpoints use this
    capability to access the external KB service.

    Features:
    - HTTP-based knowledge base queries
    - Support for vector, fulltext, and hybrid search
    - Company-specific knowledge isolation (comp_id)
    - File type filtering (PublicDocReceive/PublicDocDispatch)
    - Configurable score threshold and top-k results
    """

    def __init__(self) -> None:
        """Initialize ExternalKBQueryCapability."""
        super().__init__()
        self._client = None

    async def _get_client(self):
        """Get or create the external KB client."""
        if self._client is None:
            from rag_service.clients.external_kb_client import get_external_kb_client

            self._client = await get_external_kb_client()
        return self._client

    async def execute(self, input_data: ExternalKBQueryInput) -> ExternalKBQueryOutput:
        """
        Execute external knowledge base query.

        Args:
            input_data: Query parameters.

        Returns:
            Retrieved chunks with similarity scores.

        Raises:
            RetrievalError: If query execution fails.
        """
        import time

        start_time = time.time()

        try:
            client = await self._get_client()

            # Query external KB
            chunks = await client.query(
                query=input_data.query,
                comp_id=input_data.comp_id,
                file_type=input_data.file_type,
                doc_date=input_data.doc_date or "",
                keyword=input_data.keyword or "",
                topk=input_data.top_k,
                score_min=input_data.score_min,
                search_type=input_data.search_type,
            )

            elapsed_ms = (time.time() - start_time) * 1000

            return ExternalKBQueryOutput(
                chunks=chunks,
                total_found=len(chunks),
                query_time_ms=elapsed_ms,
                trace_id=input_data.trace_id,
                metadata={
                    "comp_id": input_data.comp_id,
                    "file_type": input_data.file_type,
                    "search_type": input_data.search_type,
                },
            )

        except RetrievalError:
            raise
        except Exception as e:
            raise RetrievalError(
                message=f"External KB query failed: {input_data.query}",
                detail=str(e),
            ) from e

    def validate_input(self, input_data: ExternalKBQueryInput) -> CapabilityValidationResult:
        """
        Validate external KB query input.

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

        # Validate comp_id
        if not input_data.comp_id:
            errors.append("Company ID (comp_id) is required")

        # Validate file_type
        if input_data.file_type not in ("PublicDocReceive", "PublicDocDispatch"):
            errors.append(f"Invalid file_type: {input_data.file_type}")

        # Validate top_k
        if input_data.top_k < 1:
            errors.append("top_k must be at least 1")
        elif input_data.top_k > 100:
            warnings.append("top_k > 100 may impact performance")

        # Validate search_type
        if input_data.search_type not in (0, 1, 2):
            errors.append(f"Invalid search_type: {input_data.search_type}")

        return CapabilityValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    async def get_health(self) -> Dict[str, Any]:
        """
        Get health status of external KB service.

        Returns:
            Health status information.
        """
        health = await super().get_health()

        try:
            client = await self._get_client()
            is_healthy = await client.health_check()
            health["external_kb"] = "connected" if is_healthy else "disconnected"
            if not is_healthy:
                health["status"] = "unhealthy"
        except Exception as e:
            health["external_kb"] = f"error: {e}"
            health["status"] = "unhealthy"

        return health
