# Data Model: RAG Service Architecture Refactoring

**Branch**: `008-rag-architecture-refactor` | **Date**: 2026-05-07

## Entity Overview

The refactoring preserves all existing data models from Features 006/007 unchanged. The changes are limited to the orchestration layer (config, capabilities, API schemas).

```
┌─────────────────────────────────────────────────────┐
│                  API Schemas (New)                    │
│                                                       │
│  UnifiedQueryRequest ──→ QueryResponse               │
│  DocumentRequest     ──→ DocumentResponse            │
│  TraceRequest        ──→ TraceResponse               │
└──────────────────────────┬──────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────┐
│             Config Models (Consolidated)              │
│                                                       │
│  MilvusConfig    LiteLLMConfig    LangfuseConfig      │
│  ServerConfig    QueryConfig                          │
└──────────────────────────┬──────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────┐
│          Strategy Interfaces (Protocol)               │
│                                                       │
│  RetrievalStrategy   QualityStrategy                  │
│  ┌────────────┐      ┌──────────────────┐            │
│  │Milvus      │      │BasicQuality      │            │
│  │ExternalKB  │      │DimensionGather   │            │
│  └────────────┘      │Conversational    │            │
│                       └──────────────────┘            │
└─────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────┐
│         Existing Data Models (Unchanged)              │
│                                                       │
│  DimensionInfo   SessionState   BeliefState           │
│  ColloquialMap   DomainRoute                          │
└─────────────────────────────────────────────────────┘
```

---

## API Schemas

### UnifiedQueryRequest

Single request model replacing `QueryRequest`, `ExternalKBQueryRequest`, and `QAQueryRequest`.

```python
class QueryContext(BaseModel):
    """Optional retrieval context."""
    company_id: Optional[str] = None      # External KB company filter
    file_type: Optional[str] = None       # Document type filter
    doc_date: Optional[str] = None        # Date filter

class UnifiedQueryRequest(BaseModel):
    """Unified query request for all retrieval and quality modes."""
    query: str                            # Required: user's question
    context: Optional[QueryContext] = None  # Optional: retrieval context
    session_id: Optional[str] = None      # Optional: multi-turn session
    top_k: int = 10                       # Optional: retrieval count (default from config)
    stream: bool = False                  # Optional: streaming mode
```

**Minimum viable request**: `{"query": "What is RAG?"}`

### QueryResponse

Unified response preserving all fields from `QAQueryResponse` and `QueryResponse`.

```python
class SourceInfo(BaseModel):
    """Retrieved chunk information."""
    chunk_id: str
    content: str
    score: float
    source_doc: str
    metadata: dict = {}

class HallucinationStatus(BaseModel):
    """Hallucination check result."""
    checked: bool = False
    passed: bool = True
    confidence: float = 0.0
    flagged_claims: list[str] = []

class QueryResponseMetadata(BaseModel):
    """Response metadata."""
    trace_id: str
    query_rewritten: bool = False
    original_query: str = ""
    rewritten_query: Optional[str] = None
    retrieval_count: int = 0
    retrieval_backend: str = ""           # "milvus" or "external_kb"
    quality_mode: str = ""                # "basic" | "dimension_gather" | "conversational"
    quality_score: float = 0.0
    session_id: Optional[str] = None
    timing_ms: dict = {}

class QueryResponse(BaseModel):
    """Unified query response."""
    answer: str
    sources: list[SourceInfo] = []
    hallucination_status: HallucinationStatus = HallucinationStatus()
    metadata: QueryResponseMetadata
    # Quality prompt fields (returned when more info needed)
    action: Optional[str] = None          # "prompt" when quality needs clarification
    prompt_text: Optional[str] = None
    dimensions: Optional[dict] = None
    feedback: Optional[str] = None
```

### DocumentRequest

Single request for all document operations, replacing separate upload/update/delete.

```python
class DocumentRequest(BaseModel):
    """Document management request."""
    operation: str = "upload"             # "upload" | "update" | "delete"
    doc_id: Optional[str] = None          # Required for update/delete
    content: Optional[str] = None         # Required for upload/update
    metadata: Optional[dict] = None       # Optional metadata
```

### TraceResponse

Unchanged from current.

### ModelsResponse

Unchanged from current.

---

## Config Models

### MilvusConfig (Consolidated)

Merges: `MilvusConfig` + `MilvusKBConfig` + `EmbeddingConfig`

```python
class MilvusConfig(BaseSettings):
    """Milvus vector database configuration."""
    # Connection
    host: str = "localhost"
    port: int = 19530
    collection_name: str = "knowledge_base"

    # Vector search
    dimension: int = 1024                 # Embedding dimension (bge-m3: 1024)
    index_type: str = "IVF_FLAT"
    metric_type: str = "L2"
    default_search_type: str = "hybrid"   # "vector" | "keyword" | "hybrid"
    default_limit: int = 10

    # Upload/chunking
    chunk_size: int = 512
    chunk_overlap: int = 50
    hybrid_ranker: str = "RRF"
    rrf_k: int = 60

    # Embedding
    embedding_model: str = "bge-m3"
    embedding_device: str = "cpu"
```

### LiteLLMConfig (Consolidated)

Merges: `LiteLLMConfig` + `CloudCompletionConfig` + `GLMConfig` + `CloudEmbeddingConfig` + `CloudRerankConfig`

```python
class ProviderConfig(BaseModel):
    """Internal provider configuration within LiteLLM."""
    url: str = ""
    model: str = ""
    api_key: str = ""
    auth_token: str = ""
    timeout: int = 60
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 0.9
    max_retries: int = 3
    # Provider-specific
    enable_thinking: bool = False          # GLM-specific

class LiteLLMConfig(BaseSettings):
    """Unified inference gateway configuration."""
    provider: str = "openai"              # "openai" | "cloud_http" | "glm"
    api_base: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-3.5-turbo"

    # Internal provider overrides (optional, merged with main config)
    cloud_http: Optional[ProviderConfig] = None
    glm: Optional[ProviderConfig] = None

    # Embedding & Rerank (internal services)
    embedding_url: str = ""
    embedding_model: str = "bge-m3"
    rerank_url: str = ""
    rerank_model: str = "embed_rerank"
```

### QueryConfig (Consolidated)

Merges: `QAConfig` + `QueryQualityConfig` + `ConversationalQueryConfig` + `ExternalKBConfig`

```python
class ExternalKBSettings(BaseModel):
    """External KB configuration (nested in QueryConfig)."""
    base_url: str = ""
    endpoint: str = "/cloudoa-ai/ai/file-knowledge/queryKnowledge"
    timeout: int = 30
    headers: dict = {}

class QueryConfig(BaseSettings):
    """Unified query pipeline configuration."""
    # Strategy selection
    retrieval_backend: str = "external_kb"  # "milvus" | "external_kb"
    quality_mode: str = "basic"             # "basic" | "dimension_gather" | "conversational"

    # Pipeline toggles
    enable_query_rewrite: bool = True
    enable_hallucination_check: bool = True
    hallucination_threshold: float = 0.7
    hallucination_method: str = "similarity"

    # External KB
    external_kb: ExternalKBSettings = ExternalKBSettings()

    # Session (shared by dimension_gather and conversational)
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""
    session_timeout: int = 900
    max_turns: int = 10

    # Colloquial mappings (conversational mode only)
    colloquial_mappings: dict = {}
    domain_keywords: dict = {}
```

### ServerConfig (Consolidated)

Merges: `ServerConfig` + `CORSConfig` + `FeatureFlags`

```python
class ServerConfig(BaseSettings):
    """Server and operational configuration."""
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    reload: bool = False
    workers: int = 1

    # CORS
    cors_origins: list[str] = ["*"]

    # Observability
    enable_tracing: bool = True
    non_blocking_tracing: bool = True
```

### LangfuseConfig (Unchanged)

```python
class LangfuseConfig(BaseSettings):
    """Langfuse observability configuration (unchanged)."""
    public_key: str = ""
    secret_key: str = ""
    host: str = "https://cloud.langfuse.com"
    release: str = "production"
    sample_rate: float = 1.0
```

---

## Strategy Interfaces

### RetrievalStrategy

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class RetrievalStrategy(Protocol):
    """Protocol for retrieval backends."""

    async def retrieve(
        self,
        query: str,
        top_k: int,
        context: Optional[dict] = None,
        trace_id: str = "",
    ) -> list[dict]:
        """Retrieve relevant chunks from knowledge base."""
        ...
```

Implementations:
- `MilvusRetrieval` — uses Milvus vector search (from existing `knowledge_query.py` + `milvus_kb_query.py`)
- `ExternalKBRetrieval` — uses HTTP external KB (from existing `external_kb_query.py`)

### QualityStrategy

```python
@runtime_checkable
class QualityStrategy(Protocol):
    """Protocol for query quality enhancement."""

    async def pre_process(
        self,
        query: str,
        session_id: Optional[str],
        config: "QueryConfig",
    ) -> tuple[str, Optional[dict]]:
        """Pre-process query. Returns (processed_query, prompt_info_or_None)."""
        ...

    async def post_process(
        self,
        answer: str,
        chunks: list[dict],
        session_id: Optional[str],
    ) -> dict:
        """Post-process answer. Returns metadata dict."""
        ...
```

Implementations:
- `BasicQuality` — pass-through (no enhancement)
- `DimensionGatherQuality` — from existing `query_quality.py`
- `ConversationalQuality` — from existing `conversational_query.py`

---

## Relationship Diagram

```
Settings (5 config sections)
  ├── MilvusConfig     ──→ MilvusRetrieval (strategy)
  ├── LiteLLMConfig    ──→ LiteLLMGateway (sole inference entry)
  ├── LangfuseConfig   ──→ (unchanged)
  ├── ServerConfig     ──→ FastAPI app setup
  └── QueryConfig      ──→ QueryCapability (strategy selection)
        ├── retrieval_backend ──→ MilvusRetrieval | ExternalKBRetrieval
        ├── quality_mode      ──→ BasicQuality | DimensionGatherQuality | ConversationalQuality
        └── external_kb       ──→ ExternalKBRetrieval config

QueryCapability
  ├── execute(UnifiedQueryRequest) → QueryResponse
  ├── _quality_strategy: QualityStrategy
  ├── _retrieval_strategy: RetrievalStrategy
  ├── _gateway: LiteLLMGateway
  └── _hallucination_detector: HallucinationDetector

ManagementCapability
  ├── execute(DocumentRequest) → DocumentResponse
  ├── list_models() → ModelsResponse
  └── (document upload, model listing logic)

TraceCapability
  ├── get_trace(trace_id) → TraceResponse
  ├── health_check() → HealthResponse
  └── get_metrics() → MetricsResponse
```
