"""
Request and response schemas for RAG QA Pipeline API.

This module defines Pydantic models for QA query requests and responses,
including validation, serialization, and documentation.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class FallbackErrorType(str, Enum):
    """Types of errors that trigger fallback responses."""

    KB_UNAVAILABLE = "kb_unavailable"
    KB_EMPTY = "kb_empty"
    KB_ERROR = "kb_error"
    HALLUCINATION_FAILED = "hallucination_failed"
    REGENERATION_FAILED = "regeneration_failed"
    TIMEOUT = "timeout"


class QAContext(BaseModel):
    """Query context for retrieval."""

    company_id: str = Field(..., description="Company unique code (e.g., N000131)")
    file_type: Optional[str] = Field(
        default="PublicDocDispatch",
        description="Document type filter (PublicDocReceive or PublicDocDispatch)"
    )
    doc_date: Optional[str] = Field(default="", description="Optional document date filter (YYYY-MM-DD format)")

    @field_validator("company_id")
    @classmethod
    def validate_company_id(cls, v: str) -> str:
        """Validate company_id format."""
        if not v or len(v) < 2:
            raise ValueError("company_id must be at least 2 characters")
        return v

    @field_validator("file_type")
    @classmethod
    def validate_file_type(cls, v: Optional[str]) -> Optional[str]:
        """Validate file_type is allowed value."""
        if v and v not in ("PublicDocReceive", "PublicDocDispatch"):
            raise ValueError("file_type must be PublicDocReceive or PublicDocDispatch")
        return v


class QAOptions(BaseModel):
    """Query processing options."""

    enable_query_rewrite: Optional[bool] = Field(
        default=True, description="Enable query rewriting"
    )
    enable_query_quality: Optional[bool] = Field(
        default=True, description="Enable query quality enhancement (multi-turn dimension gathering)"
    )
    enable_conversational_query: Optional[bool] = Field(
        default=True, description="Enable conversational query enhancement (slot extraction, domain classification)"
    )
    enable_hallucination_check: Optional[bool] = Field(
        default=True, description="Enable hallucination detection"
    )
    top_k: Optional[int] = Field(default=10, ge=1, le=50, description="Number of chunks to retrieve")
    stream: Optional[bool] = Field(default=False, description="Enable streaming response")


class QAQueryRequest(BaseModel):
    """Request for QA query."""

    query: str = Field(..., min_length=1, max_length=1000, description="User's question")
    context: Optional[QAContext] = Field(default=None, description="Optional query context")
    options: Optional[QAOptions] = Field(default=None, description="Query options")

    @field_validator("query")
    @classmethod
    def validate_query_not_empty(cls, v: str) -> str:
        """Validate query is not just whitespace."""
        if not v or not v.strip():
            raise ValueError("Query cannot be empty or whitespace only")
        return v.strip()


class QASourceInfo(BaseModel):
    """Source document information."""

    chunk_id: str = Field(..., description="Chunk identifier")
    document_id: str = Field(..., description="Source document ID")
    document_name: str = Field(..., description="Source document name")
    dataset_id: str = Field(..., description="Dataset ID")
    dataset_name: str = Field(..., description="Dataset name")
    score: float = Field(..., ge=0.0, description="Retrieval relevance score (may vary by retrieval system)")
    content_preview: str = Field(..., max_length=200, description="First 200 characters of chunk content")


class HallucinationStatus(BaseModel):
    """Hallucination detection result."""

    checked: bool = Field(..., description="Whether verification was performed")
    passed: bool = Field(..., description="Whether verification passed")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    flagged_claims: List[str] = Field(
        default_factory=list, description="Flagged claims if verification failed"
    )
    warning_message: Optional[str] = Field(
        default=None, description="Warning message if verification failed"
    )


class QATiming(BaseModel):
    """Timing breakdown in milliseconds."""

    total_ms: float = Field(..., ge=0.0, description="Total end-to-end time")
    rewrite_ms: Optional[float] = Field(default=None, ge=0.0, description="Query rewriting time")
    retrieve_ms: float = Field(..., ge=0.0, description="Retrieval time")
    generate_ms: float = Field(..., ge=0.0, description="Answer generation time")
    verify_ms: Optional[float] = Field(default=None, ge=0.0, description="Hallucination check time")


class QAMetadata(BaseModel):
    """Response metadata."""

    trace_id: str = Field(..., description="Trace ID for observability")
    query_rewritten: bool = Field(..., description="Whether query was rewritten")
    original_query: str = Field(..., description="Original user query")
    rewritten_query: Optional[str] = Field(default=None, description="Rewritten query if applicable")
    retrieval_count: int = Field(..., ge=0, description="Number of chunks retrieved")
    timing_ms: QATiming = Field(..., description="Timing breakdown")
    # Query quality enhancement fields
    quality_enhanced: bool = Field(default=False, description="Whether query was quality enhanced")
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Query quality score (0.0-1.0)")
    session_id: Optional[str] = Field(default=None, description="Session ID for multi-turn conversations")
    dimension_feedback: Optional[str] = Field(default=None, description="Quality feedback from dimension analysis")


class QAQueryResponse(BaseModel):
    """Response from QA query."""

    answer: str = Field(..., description="Generated answer")
    sources: List[QASourceInfo] = Field(
        default_factory=list, description="Source document information"
    )
    hallucination_status: HallucinationStatus = Field(
        ..., description="Hallucination detection result"
    )
    metadata: QAMetadata = Field(..., description="Response metadata")


class QAErrorResponse(BaseModel):
    """Error response for QA endpoint."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="User-friendly error message")
    detail: Optional[str] = Field(default=None, description="Detailed error information")
    trace_id: str = Field(..., description="Trace ID for debugging")
    is_fallback: bool = Field(default=False, description="Whether fallback response was provided")


class QAPromptResponse(BaseModel):
    """Response when query quality enhancement needs more information."""

    action: str = Field(default="prompt", description="Action required: prompt")
    prompt_text: str = Field(..., description="Prompt text to display to user")
    session_id: str = Field(..., description="Session ID for multi-turn conversation")
    quality_score: float = Field(..., ge=0.0, le=1.0, description="Current query quality score")
    trace_id: str = Field(..., description="Trace ID for debugging")
    dimensions: Optional[Dict[str, Any]] = Field(default=None, description="Current dimension states")
    feedback: Optional[str] = Field(default=None, description="Quality feedback message")
