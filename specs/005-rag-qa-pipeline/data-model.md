# Data Model: RAG QA Pipeline

**Feature**: 005-rag-qa-pipeline
**Created**: 2026-04-01

## Entity Overview

This document defines all data entities for the RAG QA Pipeline feature, including request/response models, internal data structures, and database entities (if any).

---

## 1. API Request/Response Models

### 1.1 QA Query Request

**Purpose**: User's query request with optional context

**Location**: `src/rag_service/api/qa_schemas.py`

```python
class QAQueryRequest(BaseModel):
    """Request for QA query."""

    query: str = Field(..., min_length=1, max_length=1000, description="User's question")
    context: Optional[QAContext] = Field(default=None, description="Optional query context")
    options: Optional[QAOptions] = Field(default=None, description="Query options")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "query": "2025年春节放假几天？",
                    "context": {"company_id": "N000131", "file_type": "PublicDocDispatch"},
                }
            ]
        }
    )
```

**Fields**:
- `query`: User's natural language question (1-1000 chars)
- `context`: Optional context for query
- `options`: Optional processing options

### 1.2 QA Context

```python
class QAContext(BaseModel):
    """Query context for retrieval."""

    company_id: str = Field(..., description="Company unique code (e.g., N000131)")
    file_type: Optional[str] = Field(
        default="PublicDocDispatch",
        description="Document type filter (PublicDocReceive or PublicDocDispatch)"
    )
    doc_date: Optional[str] = Field(default="", description="Optional document date filter")
```

### 1.3 QA Options

```python
class QAOptions(BaseModel):
    """Query processing options."""

    enable_query_rewrite: Optional[bool] = Field(
        default=True, description="Enable query rewriting"
    )
    enable_hallucination_check: Optional[bool] = Field(
        default=True, description="Enable hallucination detection"
    )
    top_k: Optional[int] = Field(default=10, ge=1, le=50, description="Number of chunks to retrieve")
    stream: Optional[bool] = Field(default=False, description="Enable streaming response")
```

### 1.4 QA Query Response

```python
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
```

### 1.5 QA Source Info

```python
class QASourceInfo(BaseModel):
    """Source document information."""

    chunk_id: str = Field(..., description="Chunk identifier")
    document_id: str = Field(..., description="Source document ID")
    document_name: str = Field(..., description="Source document name")
    dataset_id: str = Field(..., description="Dataset ID")
    dataset_name: str = Field(..., description="Dataset name")
    score: float = Field(..., description="Retrieval relevance score")
    content_preview: str = Field(..., description="First 200 chars of chunk content")
```

### 1.6 Hallucination Status

```python
class HallucinationStatus(BaseModel):
    """Hallucination detection result."""

    checked: bool = Field(..., description="Whether verification was performed")
    passed: bool = Field(..., description="Whether verification passed")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    flagged_claims: List[str] = Field(
        default_factory=list, description="Flagged claims if failed"
    )
    warning_message: Optional[str] = Field(
        default=None, description="Warning message if verification failed"
    )
```

### 1.7 QA Metadata

```python
class QAMetadata(BaseModel):
    """Response metadata."""

    trace_id: str = Field(..., description="Trace ID for observability")
    query_rewritten: bool = Field(..., description="Whether query was rewritten")
    original_query: str = Field(..., description="Original user query")
    rewritten_query: Optional[str] = Field(default=None, description="Rewritten query if applicable")
    retrieval_count: int = Field(..., description="Number of chunks retrieved")
    timing_ms: QATiming = Field(..., description="Timing breakdown")
```

### 1.8 QA Timing

```python
class QATiming(BaseModel):
    """Timing breakdown in milliseconds."""

    total_ms: float = Field(..., description="Total end-to-end time")
    rewrite_ms: Optional[float] = Field(default=None, description="Query rewriting time")
    retrieve_ms: float = Field(..., description="Retrieval time")
    generate_ms: float = Field(..., description="Answer generation time")
    verify_ms: Optional[float] = Field(default=None, description="Hallucination check time")
```

---

## 2. Internal Capability Models

### 2.1 Query Rewrite Input

**Location**: `src/rag_service/capabilities/query_rewrite.py`

```python
class QueryRewriteInput(CapabilityInput):
    """Input for query rewriting."""

    original_query: str = Field(..., description="Original user query")
    context: Optional[QAContext] = Field(default=None, description="Query context")
```

### 2.2 Query Rewrite Output

```python
class QueryRewriteOutput(CapabilityOutput):
    """Output from query rewriting."""

    rewritten_query: str = Field(..., description="Rewritten query")
    original_query: str = Field(..., description="Original query")
    was_rewritten: bool = Field(..., description="Whether query was modified")
    rewrite_reason: Optional[str] = Field(default=None, description="Reason for rewrite")
```

### 2.3 QA Pipeline Input

**Location**: `src/rag_service/capabilities/qa_pipeline.py`

```python
class QAPipelineInput(CapabilityInput):
    """Input for QA pipeline."""

    query: str = Field(..., description="User's question")
    context: Optional[QAContext] = Field(default=None, description="Query context")
    options: QAOptions = Field(
        default_factory=lambda: QAOptions(),
        description="Processing options"
    )
```

### 2.4 QA Pipeline Output

```python
class QAPipelineOutput(CapabilityOutput):
    """Output from QA pipeline."""

    answer: str = Field(..., description="Generated answer")
    sources: List[QASourceInfo] = Field(..., description="Source information")
    hallucination_status: HallucinationStatus = Field(..., description="Verification result")
    pipeline_metadata: QAPipelineMetadata = Field(..., description="Pipeline metadata")
```

### 2.5 QA Pipeline Metadata

```python
class QAPipelineMetadata(BaseModel):
    """QA pipeline execution metadata."""

    trace_id: str = Field(..., description="Trace ID")
    query_rewrite_result: Optional[QueryRewriteOutput] = Field(
        default=None, description="Query rewrite result"
    )
    retrieval_count: int = Field(..., description="Chunks retrieved")
    generation_model: str = Field(..., description="Model used for generation")
    timing: QATiming = Field(..., description="Timing breakdown")
```

---

## 3. Hallucination Detection Models

### 3.1 Hallucination Check Input

**Location**: `src/rag_service/capabilities/hallucination_detection.py`

```python
class HallucinationCheckInput(CapabilityInput):
    """Input for hallucination detection."""

    generated_answer: str = Field(..., description="Generated answer to verify")
    retrieved_chunks: List[Dict[str, Any]] = Field(
        ..., description="Retrieved document chunks"
    )
    threshold: Optional[float] = Field(
        default=0.7, description="Similarity threshold for passing"
    )
```

### 3.2 Hallucination Check Output

```python
class HallucinationCheckOutput(CapabilityOutput):
    """Output from hallucination detection."""

    passed: bool = Field(..., description="Whether verification passed")
    confidence: float = Field(..., description="Confidence score (0-1)")
    similarity_score: float = Field(..., description="Raw similarity score")
    flagged_claims: List[str] = Field(
        default_factory=list, description="Flagged claims/sections"
    )
    verification_method: str = Field(
        default="similarity", description="Method used for verification"
    )
```

---

## 4. Default Fallback Models

### 4.1 Fallback Request

**Location**: `src/rag_service/services/default_fallback.py`

```python
class FallbackRequest(BaseModel):
    """Request for fallback message."""

    error_type: FallbackErrorType = Field(..., description="Type of error")
    context: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional context for templating"
    )
```

### 4.2 Fallback Error Type

```python
class FallbackErrorType(str, Enum):
    """Types of errors that trigger fallback."""

    KB_UNAVAILABLE = "kb_unavailable"
    KB_EMPTY = "kb_empty"
    KB_ERROR = "kb_error"
    HALUCINATION_FAILED = "hallucination_failed"
    REGENERATION_FAILED = "regeneration_failed"
    TIMEOUT = "timeout"
```

### 4.3 Fallback Response

```python
class FallbackResponse(BaseModel):
    """Fallback message response."""

    message: str = Field(..., description="Fallback message")
    error_type: FallbackErrorType = Field(..., description="Error type")
    suggestions: List[str] = Field(
        default_factory=list, description="Suggestions for user"
    )
```

---

## 5. Configuration Models

### 5.1 QA Configuration

**Location**: `src/rag_service/config.py`

```python
class QAConfig(BaseSettings):
    """QA Pipeline configuration."""

    # Query rewriting
    enable_query_rewrite: bool = Field(default=True, description="Enable query rewriting")
    query_rewrite_model: Optional[str] = Field(
        default=None, description="Model for query rewriting (default: main model)"
    )
    query_rewrite_max_length: int = Field(
        default=500, description="Maximum rewritten query length"
    )

    # Hallucination detection
    enable_hallucination_check: bool = Field(
        default=True, description="Enable hallucination detection"
    )
    hallucination_threshold: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Similarity threshold"
    )
    hallucination_method: str = Field(
        default="similarity", description="Detection method: similarity or llm"
    )

    # Regeneration
    max_regen_attempts: int = Field(default=1, ge=0, le=3, description="Max regeneration attempts")
    regen_timeout: int = Field(default=3, ge=1, le=10, description="Regeneration timeout (seconds)")

    # Fallback
    fallback_config_path: str = Field(
        default="config/qa_fallback.yaml", description="Fallback messages config file"
    )

    # Prompts (if not using Langfuse)
    prompt_query_rewrite: Optional[str] = Field(
        default=None, description="Query rewrite prompt template"
    )
    prompt_answer_generate: Optional[str] = Field(
        default=None, description="Answer generation prompt template"
    )
    prompt_answer_strict: Optional[str] = Field(
        default=None, description="Strict answer generation prompt (for regeneration)"
    )

    model_config = SettingsConfigDict(
        env_prefix="QA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
```

---

## 6. Data Flow Summary

```
User Request
    │
    ├─► QAQueryRequest
    │       ├─ query: str
    │       ├─ context: QAContext
    │       └─ options: QAOptions
    │
    ▼
QAPipelineCapability.execute()
    │
    ├─► QueryRewriteCapability
    │       ├─ QueryRewriteInput
    │       └─► QueryRewriteOutput
    │
    ├─► ExternalKBQueryCapability
    │       └─► List[Dict] (chunks)
    │
    ├─► ModelInferenceCapability
    │       └─► str (answer)
    │
    └─► HallucinationDetectionCapability
            ├─ HallucinationCheckInput
            └─► HallucinationCheckOutput
    │
    ▼
QAQueryResponse
    ├─ answer: str
    ├─ sources: List[QASourceInfo]
    ├─ hallucination_status: HallucinationStatus
    └─ metadata: QAMetadata
```

---

## 7. Validation Rules

### Query Validation
- `query`: 1-1000 characters, not whitespace only
- `company_id`: Must match pattern `^N\d{6,}$` (e.g., N000131)
- `file_type`: Must be `PublicDocReceive` or `PublicDocDispatch`
- `top_k`: 1-50

### Response Validation
- `confidence`: 0.0-1.0
- `score`: 0.0-1.0
- `timing_ms`: All values >= 0

### Hallucination Thresholds
- `threshold < 0.5`: Very strict (more false positives)
- `threshold = 0.7`: Default (balanced)
- `threshold > 0.85`: Lenient (more false negatives)

---

## 8. Error Responses

### Error Schema

```python
class QAErrorResponse(BaseModel):
    """Error response for QA endpoint."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    detail: Optional[str] = Field(default=None, description="Detailed error info")
    trace_id: str = Field(..., description="Trace ID for debugging")
    is_fallback: bool = Field(default=False, description="Whether fallback response was provided")
```

### Error Types

| Error Type | HTTP Status | Description |
|------------|-------------|-------------|
| `invalid_query` | 400 | Query validation failed |
| `kb_unavailable` | 503 | External KB not accessible |
| `kb_empty` | 200 | No relevant documents found (with fallback message) |
| `generation_failed` | 500 | LLM generation failed |
| `verification_failed` | 200 | Hallucination check failed (with warning) |
| `timeout` | 504 | Query processing timeout |
