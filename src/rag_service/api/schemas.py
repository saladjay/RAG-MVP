"""
API request/response schemas for RAG Service.

This module defines Pydantic models for all API endpoints using
the Capability interface layer. All schemas are designed to map
to Capability Input/Output models.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ============================================================================
# Base Schemas
# ============================================================================

class ErrorResponse(BaseModel):
    """Error response schema."""

    message: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Error detail")
    code: Optional[str] = Field(None, description="Error code")


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str = Field(..., description="Overall health status")
    components: Dict[str, str] = Field(default_factory=dict, description="Component statuses")
    uptime_ms: Optional[float] = Field(None, description="Uptime in milliseconds")


# ============================================================================
# Query Schemas
# ============================================================================

class QueryRequest(BaseModel):
    """
    Request schema for knowledge base query.

    This schema maps to KnowledgeQueryCapability input.
    For /ai/agent endpoint, use 'question' field.
    For /query endpoint, use 'query' field.
    """

    query: Optional[str] = Field(None, min_length=1, max_length=2000, description="Query text (legacy)")
    question: Optional[str] = Field(None, min_length=1, max_length=2000, description="Question text (preferred)")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context")
    top_k: int = Field(default=5, ge=1, le=100, description="Number of results")
    trace_id: Optional[str] = Field(None, description="Trace ID for observability")
    model_hint: Optional[str] = Field(None, description="Optional model hint for inference")


class RetrievedChunk(BaseModel):
    """Retrieved chunk schema."""

    id: str = Field(..., description="Chunk identifier")
    content: str = Field(..., description="Chunk content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Chunk metadata")
    score: float = Field(..., description="Similarity score")


class QueryResponse(BaseModel):
    """
    Response schema for knowledge base query.

    This schema maps to KnowledgeQueryCapability output.
    """

    answer: str = Field(..., description="Generated answer")
    chunks: List[RetrievedChunk] = Field(default_factory=list, description="Retrieved chunks")
    trace_id: str = Field(..., description="Trace ID for observability")
    query_time_ms: Optional[float] = Field(None, description="Query time in ms")


# ============================================================================
# External KB Query Schemas
# ============================================================================

class ExternalKBQueryRequest(BaseModel):
    """
    Request schema for external knowledge base query.

    This schema maps to ExternalKBQueryCapability input.
    """

    query: str = Field(..., min_length=1, max_length=2000, description="Search query")
    comp_id: str = Field(..., description="Company ID (e.g., N000131)")
    file_type: str = Field(default="PublicDocDispatch", description="File type: PublicDocReceive or PublicDocDispatch")
    doc_date: Optional[str] = Field(None, description="Document date filter")
    keyword: Optional[str] = Field(None, description="Secondary keyword")
    top_k: int = Field(default=10, ge=1, le=100, description="Number of results")
    score_min: float = Field(default=0.0, description="Minimum score threshold")
    search_type: int = Field(default=1, ge=0, le=2, description="Search type: 0=vector, 1=fulltext, 2=hybrid")
    trace_id: Optional[str] = Field(None, description="Trace ID for observability")


class ExternalKBChunkInfo(BaseModel):
    """External KB chunk schema."""

    id: str = Field(..., description="Chunk identifier")
    chunk_id: str = Field(..., description="Chunk identifier (same as id)")
    content: str = Field(..., description="Chunk content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Chunk metadata")
    score: float = Field(..., description="Similarity score")
    source_doc: str = Field(..., description="Source document name")


class ExternalKBQueryResponse(BaseModel):
    """
    Response schema for external knowledge base query.

    This schema maps to ExternalKBQueryCapability output.
    """

    chunks: List[ExternalKBChunkInfo] = Field(default_factory=list, description="Retrieved chunks")
    total_found: int = Field(default=0, description="Total matches")
    trace_id: str = Field(..., description="Trace ID")
    query_time_ms: Optional[float] = Field(None, description="Query time in ms")


# ============================================================================
# Model Schemas
# ============================================================================

class ModelInfo(BaseModel):
    """Model information schema."""

    id: str = Field(..., description="Model identifier")
    name: str = Field(..., description="Model display name")
    provider: str = Field(..., description="Model provider")
    context_length: int = Field(..., description="Max context length")


class ModelsResponse(BaseModel):
    """Response schema for available models."""

    models: List[ModelInfo] = Field(default_factory=list, description="Available models")
    providers: List[str] = Field(default_factory=list, description="Available providers")


# ============================================================================
# Document Schemas
# ============================================================================

class DocumentUploadRequest(BaseModel):
    """Request schema for document upload."""

    content: str = Field(..., min_length=1, description="Document content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata")


class DocumentUploadResponse(BaseModel):
    """Response schema for document upload."""

    doc_id: str = Field(..., description="Document ID")
    chunk_count: int = Field(..., description="Number of chunks created")
    trace_id: str = Field(..., description="Trace ID")


class DocumentDeleteResponse(BaseModel):
    """Response schema for document deletion."""

    doc_id: str = Field(..., description="Deleted document ID")
    trace_id: str = Field(..., description="Trace ID")


# ============================================================================
# Trace Schemas
# ============================================================================

class TraceInfo(BaseModel):
    """Trace information schema."""

    trace_id: str = Field(..., description="Trace identifier")
    operation: str = Field(..., description="Operation name")
    timestamp: str = Field(..., description="Trace timestamp")


class TraceResponse(BaseModel):
    """Response schema for trace retrieval."""

    trace_id: str = Field(..., description="Trace identifier")
    request_id: str = Field(..., description="Request identifier")
    request_prompt: str = Field(..., description="Original user prompt")
    user_context: Dict[str, Any] = Field(default_factory=dict, description="User context")
    start_time: str = Field(..., description="Trace start time (ISO format)")
    end_time: Optional[str] = Field(None, description="Trace end time (ISO format)")
    status: str = Field(..., description="Trace status (active/completed/failed)")
    spans: List[Dict[str, Any]] = Field(default_factory=list, description="Trace spans")
    phidata_data: Dict[str, Any] = Field(default_factory=dict, description="Agent layer data")
    litellm_data: Dict[str, Any] = Field(default_factory=dict, description="LLM layer data")
    langfuse_data: Dict[str, Any] = Field(default_factory=dict, description="Prompt layer data")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional trace metadata")


class ObservabilityMetricsResponse(BaseModel):
    """Response schema for observability metrics."""

    metrics: Dict[str, Any] = Field(default_factory=dict, description="Aggregated metrics")
    agent_metrics: Dict[str, Any] = Field(default_factory=dict, description="Agent layer metrics")
    llm_metrics: Dict[str, Any] = Field(default_factory=dict, description="LLM layer metrics")
    prompt_metrics: Dict[str, Any] = Field(default_factory=dict, description="Prompt layer metrics")
    summary: Dict[str, Any] = Field(default_factory=dict, description="Summary statistics")
