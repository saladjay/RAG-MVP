"""
Unified request and response schemas for RAG Service API.

This module provides a single set of Pydantic models for all API endpoints,
replacing the previous split between schemas.py, qa_schemas.py, and
kb_upload route inline models.

Key models:
- UnifiedQueryRequest: Single query request for all modes
- QueryResponse: Unified response with answer, sources, metadata
- DocumentRequest: Unified document operation request

API Reference:
- Location: src/rag_service/api/unified_schemas.py
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# Query Schemas
# ============================================================================


class QueryContext(BaseModel):
    """Optional retrieval context for query requests."""

    company_id: Optional[str] = Field(
        default=None,
        description="Company unique code (e.g., N000131) for external KB",
    )
    file_type: Optional[str] = Field(
        default=None,
        description="Document type filter (PublicDocReceive or PublicDocDispatch)",
    )
    doc_date: Optional[str] = Field(
        default=None,
        description="Optional document date filter (YYYY-MM-DD format)",
    )

    @field_validator("file_type")
    @classmethod
    def validate_file_type(cls, v: Optional[str]) -> Optional[str]:
        """Validate file_type is allowed value."""
        if v and v not in ("PublicDocReceive", "PublicDocDispatch"):
            raise ValueError("file_type must be PublicDocReceive or PublicDocDispatch")
        return v


class UnifiedQueryRequest(BaseModel):
    """Unified query request for all retrieval and quality modes.

    Minimum viable request: {"query": "What is RAG?"}
    All other fields have sensible defaults from configuration.
    """

    query: str = Field(..., min_length=1, max_length=1000, description="User's question")
    context: Optional[QueryContext] = Field(
        default=None,
        description="Optional retrieval context (company_id, file_type, doc_date)",
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Session ID for multi-turn conversations",
    )
    top_k: int = Field(default=10, ge=1, le=50, description="Number of chunks to retrieve")
    stream: bool = Field(default=False, description="Enable streaming response")

    @field_validator("query")
    @classmethod
    def validate_query_not_empty(cls, v: str) -> str:
        """Validate query is not just whitespace."""
        if not v or not v.strip():
            raise ValueError("Query cannot be empty or whitespace only")
        return v.strip()


class SourceInfo(BaseModel):
    """Retrieved chunk information."""

    chunk_id: str = Field(..., description="Chunk identifier")
    content: str = Field(..., description="Chunk text content")
    score: float = Field(..., ge=0.0, description="Retrieval relevance score")
    source_doc: str = Field(default="", description="Source document name")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class HallucinationStatus(BaseModel):
    """Hallucination detection result."""

    checked: bool = Field(default=False, description="Whether verification was performed")
    passed: bool = Field(default=True, description="Whether verification passed")
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Confidence score"
    )
    flagged_claims: List[str] = Field(
        default_factory=list, description="Flagged claims if verification failed"
    )
    warning_message: Optional[str] = Field(
        default=None, description="Warning message if verification failed"
    )


class QueryTiming(BaseModel):
    """Timing breakdown in milliseconds."""

    total_ms: float = Field(default=0.0, ge=0.0, description="Total end-to-end time")
    rewrite_ms: Optional[float] = Field(default=None, ge=0.0, description="Query rewriting time")
    retrieve_ms: float = Field(default=0.0, ge=0.0, description="Retrieval time")
    generate_ms: float = Field(default=0.0, ge=0.0, description="Answer generation time")
    verify_ms: Optional[float] = Field(default=None, ge=0.0, description="Hallucination check time")


class QueryResponseMetadata(BaseModel):
    """Response metadata."""

    trace_id: str = Field(default="", description="Trace ID for observability")
    query_rewritten: bool = Field(default=False, description="Whether query was rewritten")
    original_query: str = Field(default="", description="Original user query")
    rewritten_query: Optional[str] = Field(default=None, description="Rewritten query if applicable")
    retrieval_count: int = Field(default=0, ge=0, description="Number of chunks retrieved")
    retrieval_backend: str = Field(default="", description="Retrieval backend used (milvus/external_kb)")
    quality_mode: str = Field(default="", description="Quality mode (basic/dimension_gather/conversational)")
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Query quality score")
    session_id: Optional[str] = Field(default=None, description="Session ID for multi-turn")
    dimension_feedback: Optional[str] = Field(default=None, description="Quality feedback")
    timing_ms: Optional[QueryTiming] = Field(default=None, description="Timing breakdown")


class QueryResponse(BaseModel):
    """Unified query response."""

    answer: str = Field(default="", description="Generated answer")
    sources: List[SourceInfo] = Field(default_factory=list, description="Retrieved source chunks")
    hallucination_status: HallucinationStatus = Field(
        default_factory=HallucinationStatus,
        description="Hallucination detection result",
    )
    metadata: QueryResponseMetadata = Field(
        default_factory=QueryResponseMetadata,
        description="Response metadata",
    )
    # Quality prompt fields (returned when more info needed)
    action: Optional[str] = Field(default=None, description="Action required: 'prompt' when quality needs clarification")
    prompt_text: Optional[str] = Field(default=None, description="Prompt text to display to user")
    dimensions: Optional[Dict[str, Any]] = Field(default=None, description="Current dimension states")
    feedback: Optional[str] = Field(default=None, description="Quality feedback message")


# ============================================================================
# Document Schemas
# ============================================================================


class DocumentRequest(BaseModel):
    """Unified document management request.

    A single model handling upload, update, and delete operations
    via the 'operation' field, replacing separate PUT/DELETE endpoints.
    """

    operation: str = Field(
        default="upload",
        description="Operation type: 'upload', 'update', or 'delete'",
    )
    doc_id: Optional[str] = Field(default=None, description="Document ID (required for update/delete)")
    title: Optional[str] = Field(default=None, description="Document title (for upload)")
    content: Optional[str] = Field(default=None, description="Document content (required for upload/update)")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional metadata")
    chunk_size: Optional[int] = Field(default=512, ge=100, le=4096, description="Chunk size in characters")
    chunk_overlap: Optional[int] = Field(default=50, ge=0, le=512, description="Chunk overlap")

    @field_validator("operation")
    @classmethod
    def validate_operation(cls, v: str) -> str:
        """Validate operation is a valid value."""
        valid = {"upload", "update", "delete"}
        if v not in valid:
            raise ValueError(f"operation must be one of {valid}, got '{v}'")
        return v


class DocumentResponse(BaseModel):
    """Document operation response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    doc_id: str = Field(..., description="Document identifier")
    operation: str = Field(..., description="Operation performed")
    chunk_count: int = Field(default=0, ge=0, description="Number of chunks created/affected")
    trace_id: str = Field(default="", description="Trace ID for observability")


# ============================================================================
# Shared / Re-exported Schemas
# ============================================================================


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Health status: healthy, degraded, or unhealthy")
    components: Dict[str, str] = Field(default_factory=dict, description="Component health status")
    uptime_ms: float = Field(default=0.0, description="Service uptime in milliseconds")


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str = Field(..., description="Error type identifier")
    message: str = Field(..., description="User-friendly error message")
    detail: Optional[str] = Field(default=None, description="Detailed error info (debug mode only)")
    trace_id: str = Field(default="", description="Trace ID for debugging")
    is_fallback: bool = Field(default=False, description="Whether a fallback response was provided")
