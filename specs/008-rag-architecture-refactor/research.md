# Research: RAG Service Architecture Refactoring

**Branch**: `008-rag-architecture-refactor` | **Date**: 2026-05-07

## Current State Inventory

### Capabilities (16 files, 13 registered)

| # | File | Registered | Bypasses Registry? |
|---|------|-----------|-------------------|
| 1 | `health_check.py` | Yes (main.py:120) | No |
| 2 | `knowledge_query.py` | Yes (main.py:121) | No |
| 3 | `external_kb_query.py` | Yes (main.py:122) | Yes (qa_routes.py:49) |
| 4 | `model_inference.py` | Yes (main.py:123) | No |
| 5 | `trace_observation.py` | Yes (main.py:124) | No |
| 6 | `document_management.py` | Yes (main.py:125) | No |
| 7 | `model_discovery.py` | Yes (main.py:126) | No |
| 8 | `milvus_kb_upload.py` | Yes (main.py:127) | No |
| 9 | `query_quality.py` | Yes (main.py:128) | No |
| 10 | `conversational_query.py` | Yes (main.py:129) | No |
| 11 | `qa_pipeline.py` | **No** | Yes (qa_routes.py:48) |
| 12 | `query_rewrite.py` | **No** | Internal to qa_pipeline |
| 13 | `hallucination_detection.py` | **No** | Internal to qa_pipeline |
| 14 | `milvus_kb_query.py` | **No** | Standalone (not Capability subclass) |

### Gateways (4 classes in gateway.py)

| Class | Lines | Factory Function | Used By |
|-------|-------|-----------------|---------|
| `LiteLLMGateway` | ~200 | `get_gateway()` | KnowledgeQuery |
| `HTTPCompletionGateway` | ~350 | `get_http_gateway()` | QAPipeline, routes |
| `GLMCompletionGateway` | ~350 | `get_glm_gateway()` | QAPipeline, routes |
| `HTTPEmbeddingGateway` | ~100 | (none) | MilvusKBUpload |

**Problem**: `Settings.default_gateway` ("http" | "litellm" | "glm") forces callers to choose.

### Config Classes (16 classes, 941 lines)

| Class | Env Prefix | Purpose |
|-------|-----------|---------|
| `MilvusConfig` | `MILVUS_` | Milvus connection |
| `MilvusKBConfig` | `MILVUS_KB_*` | Milvus KB hybrid search |
| `LiteLLMConfig` | `LITELLM_` | LiteLLM gateway |
| `CloudCompletionConfig` | `CLOUD_COMPLETION_` | HTTP Cloud gateway |
| `GLMConfig` | `GLM_` | GLM gateway |
| `CloudEmbeddingConfig` | `CLOUD_EMBEDDING_` | Cloud embedding |
| `CloudRerankConfig` | `CLOUD_RERANK_` | Cloud rerank |
| `LangfuseConfig` | `LANGFUSE_` | Observability |
| `EmbeddingConfig` | `EMBEDDING_` | Local embedding |
| `ServerConfig` | (none) | Server settings |
| `CORSConfig` | `CORS_` | CORS |
| `ExternalKBConfig` | `EXTERNAL_KB_` | External KB |
| `FeatureFlags` | (none) | Feature toggles |
| `QAConfig` | `QA_` | QA pipeline |
| `QueryQualityConfig` | `QUERY_QUALITY_` | Quality enhancement |
| `ConversationalQueryConfig` | `CONVERSATIONAL_QUERY_` | Conversational query |

### API Routes (15 endpoints across 3 routers)

| Router | Endpoints | Prefix |
|--------|-----------|--------|
| `routes.py` | GET /health, POST /ai/agent, POST /query, POST /external/query, GET /models, POST /documents, DELETE /documents/{id}, PUT /documents/{id}, GET /traces/{id}, GET /observability/metrics | `/api/v1` |
| `qa_routes.py` | POST /query, POST /query/stream, GET /health | `/qa` |
| `kb_upload_routes.py` | POST /upload, GET /status | unknown prefix |

---

## Design Decisions

### D1: Strategy Pattern — Pure Python (No New Libraries)

**Decision**: Use `typing.Protocol` (stdlib since Python 3.8) for strategy interfaces. Each strategy is a plain class implementing the protocol.

**Rationale**:
- `typing.Protocol` is in Python's standard library — no pip install needed
- Structural subtyping (duck typing with type checking) — simpler than ABC inheritance
- Each strategy is a standalone file in a `_strategies/` subdirectory
- Caller never sees strategies — only `QueryCapability.execute()` dispatches

**Alternatives considered**:
- ABC with inheritance: More boilerplate, tighter coupling
- Callable dict: Too loose, no type safety
- Third-party library (e.g., `strategies`, `simple-di`): Violates "no new libraries" constraint

**Implementation sketch**:
```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class RetrievalStrategy(Protocol):
    async def retrieve(self, query: str, top_k: int, **kwargs) -> list[dict]: ...

class MilvusRetrieval:
    async def retrieve(self, query: str, top_k: int, **kwargs) -> list[dict]:
        # existing Milvus logic
        ...

class ExternalKBRetrieval:
    async def retrieve(self, query: str, top_k: int, **kwargs) -> list[dict]:
        # existing External KB logic
        ...
```

### D2: Gateway Consolidation — Internal Providers

**Decision**: Keep `LiteLLMGateway` as the only exposed class. `HTTPCompletionGateway` and `GLMCompletionGateway` become internal methods within LiteLLM, selected by a `provider` config field (not by caller).

**Rationale**:
- Original design intent: LiteLLM is the sole inference entry point
- HTTP Cloud and GLM are provider implementations, not separate Gateways
- Remove `Settings.default_gateway` — callers never specify a gateway
- Config change from `default_gateway: "http"` to `litellm.provider: "cloud_http"` or `litellm.provider: "glm"`

**Alternatives considered**:
- Adapter pattern wrapping each gateway: Extra indirection layer, not needed
- Factory method returning different classes: Still exposes multiple types
- Keep all 3 as separate classes: Current state, explicitly rejected by user

**Config migration**:
```
# Before (3 separate configs + selector)
CLOUD_COMPLETION_URL=...
CLOUD_COMPLETION_MODEL=...
GLM_API_KEY=...
DEFAULT_GATEWAY=http

# After (unified under LiteLLM)
LITELLM_PROVIDER=cloud_http    # or "glm" or "openai" etc.
LITELLM_API_BASE=...
LITELLM_MODEL=...
LITELLM_API_KEY=...
```

### D3: Capability Consolidation — 3 Capabilities

**Decision**: Merge 13+ capabilities into 3 aligned with caller intent.

| New Capability | Merges | Caller Intent |
|---------------|--------|---------------|
| `QueryCapability` | KnowledgeQuery, ExternalKBQuery, QAPipeline, QueryQuality, ConversationalQuery, QueryRewrite, HallucinationDetection, MilvusKBQuery | "Ask a question, get an answer" |
| `ManagementCapability` | DocumentManagement, MilvusKBUpload, ModelDiscovery | "Manage documents and list models" |
| `TraceCapability` | TraceObservation, HealthCheck | "Check system health and inspect traces" |

**Rationale**: User said "Capability 的粒度应对齐调用者意图" — callers have 3 intents: query, manage, observe.

**How strategies switch internally**:
```
QueryCapability.execute(query, ...):
  1. quality_strategy.pre_process(query)   # basic | dimension_gather | conversational
  2. retrieval_strategy.retrieve(query)    # milvus | external_kb
  3. llm.generate(context + query)         # via LiteLLM (internal provider routing)
  4. hallucination.check(answer, chunks)   # optional
  5. quality_strategy.post_process(answer) # feedback/score
```

### D4: API Consolidation — 5 Endpoints

**Decision**: Reduce from 15 endpoints to 5, under `/api/v1` prefix.

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/query` | Unified query (all retrieval, quality modes) |
| POST | `/api/v1/query/stream` | Streaming variant |
| POST | `/api/v1/documents` | Upload documents |
| GET | `/api/v1/traces/{id}` | Get trace + health info |
| GET | `/api/v1/models` | List available models |

**Old endpoint mapping**:
- `POST /api/v1/ai/agent` → `POST /api/v1/query` (deprecated redirect)
- `POST /api/v1/query` → `POST /api/v1/query` (enhanced)
- `POST /api/v1/external/query` → `POST /api/v1/query` (with context.company_id)
- `POST /qa/query` → `POST /api/v1/query` (with context)
- `POST /qa/query/stream` → `POST /api/v1/query/stream`
- `POST /api/v1/documents` → `POST /api/v1/documents` (unchanged)
- `DELETE/PUT /api/v1/documents/{id}` → folded into `POST /api/v1/documents` with operation field
- `GET /api/v1/health` → folded into `GET /api/v1/traces/health`
- `GET /api/v1/traces/{id}` → `GET /api/v1/traces/{id}` (unchanged)
- `GET /api/v1/models` → `GET /api/v1/models` (unchanged)
- `GET /api/v1/observability/metrics` → folded into `GET /api/v1/traces/{id}` with detail param

**Simplified document management**: Instead of separate POST/PUT/DELETE endpoints, use a single `POST /documents` with an `operation` field (`upload`, `update`, `delete`). This keeps the API surface minimal while supporting all operations.

### D5: Config Consolidation — 5 Sections

**Decision**: Merge 16 config classes into 5.

| New Config | Merges | Env Prefix |
|-----------|--------|-----------|
| `MilvusConfig` | MilvusConfig + MilvusKBConfig + EmbeddingConfig | `MILVUS_` |
| `LiteLLMConfig` | LiteLLMConfig + CloudCompletionConfig + GLMConfig + CloudEmbeddingConfig + CloudRerankConfig | `LITELLM_` |
| `LangfuseConfig` | (unchanged) | `LANGFUSE_` |
| `ServerConfig` | ServerConfig + CORSConfig + FeatureFlags | `SERVER_` |
| `QueryConfig` | QAConfig + QueryQualityConfig + ConversationalQueryConfig + ExternalKBConfig | `QUERY_` |

**Estimated lines**: ~300 (down from 941)

**Key config field changes**:
- `DEFAULT_GATEWAY` → removed (auto-detected from LITELLM_PROVIDER)
- `LITELLM_PROVIDER` → new field ("openai", "cloud_http", "glm")
- `CLOUD_COMPLETION_*` → `LITELLM_CLOUD_*` (deprecated, mapped internally)
- `GLM_*` → `LITELLM_GLM_*` (deprecated, mapped internally)
- `QUERY_RETRIEVAL_BACKEND` → new field ("milvus" | "external_kb")
- `QUERY_QUALITY_MODE` → new field ("basic" | "dimension_gather" | "conversational")

### D6: Unified Request Schema

**Decision**: Single `UnifiedQueryRequest` merging all existing request types.

```python
class UnifiedQueryRequest(BaseModel):
    """Single query request for all modes."""
    query: str                           # Required: the question
    context: Optional[QueryContext] = None  # Optional: company_id, file_type, doc_date
    session_id: Optional[str] = None     # Optional: for multi-turn
    top_k: int = 10                      # Optional: retrieval count
    stream: bool = False                 # Optional: streaming mode
```

**Caller simplicity**: Minimum viable request is `{"query": "What is RAG?"}` — all other fields have sensible defaults from config.

---

## Call Flow Diagrams

### Before (Current)

```
Client → POST /qa/query
  → qa_routes.py (creates QAPipelineCapability directly, bypasses registry)
    → QAPipelineCapability.execute()
      → QueryRewriteCapability (standalone)
      → ExternalKBQueryCapability (standalone) or MilvusKBQuery (not a Capability)
      → ModelInferenceCapability (uses get_gateway() or get_http_gateway() or get_glm_gateway())
      → HallucinationDetectionCapability (standalone)
```

### After (Target)

```
Client → POST /api/v1/query {"query": "..."}
  → routes.py → registry.get("QueryCapability")
    → QueryCapability.execute(UnifiedQueryRequest)
      → quality_strategy.pre_process()  # basic | dimension_gather | conversational
      → retrieval_strategy.retrieve()   # milvus | external_kb
      → LiteLLMGateway.generate()       # auto-selects internal provider
      → hallucination_check()           # optional, config-driven
      → quality_strategy.post_process()
```

---

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Breaking existing callers | Keep old endpoints with deprecation headers for 1 version |
| Config migration breaks deployments | Accept old env vars with deprecation warnings, map to new fields |
| Strategy pattern adds complexity | Keep strategies as simple classes — no framework, no DI container |
| QA pipeline logic scattered across strategies | QA pipeline becomes the orchestrator inside QueryCapability.execute() |
| MilvusKBQuery doesn't extend Capability | Absorb its logic into MilvusRetrieval strategy |
| qa_routes.py bypasses registry | All routes go through registry in new design |

---

## Files to Create/Modify/Delete

### Create
- `src/rag_service/capabilities/query_capability.py` — unified QueryCapability
- `src/rag_service/capabilities/management_capability.py` — unified ManagementCapability
- `src/rag_service/capabilities/trace_capability.py` — unified TraceCapability
- `src/rag_service/api/unified_routes.py` — new unified router (5 endpoints)
- `src/rag_service/api/unified_schemas.py` — unified request/response models

### Modify
- `src/rag_service/config.py` — consolidate to 5 config classes
- `src/rag_service/main.py` — register 3 capabilities, include new router
- `src/rag_service/inference/gateway.py` — merge HTTP/GLM into LiteLLM internal providers

### Deprecate (keep with deprecation headers)
- `src/rag_service/api/qa_routes.py` — old QA routes
- `src/rag_service/api/kb_upload_routes.py` — old KB upload routes
- Old endpoints in `src/rag_service/api/routes.py`

### Delete (after transition period)
- `src/rag_service/capabilities/knowledge_query.py`
- `src/rag_service/capabilities/external_kb_query.py`
- `src/rag_service/capabilities/qa_pipeline.py`
- `src/rag_service/capabilities/query_quality.py`
- `src/rag_service/capabilities/conversational_query.py`
- `src/rag_service/capabilities/document_management.py`
- `src/rag_service/capabilities/milvus_kb_upload.py`
- `src/rag_service/capabilities/model_discovery.py`
- `src/rag_service/capabilities/trace_observation.py`
- `src/rag_service/capabilities/health_check.py`
- `src/rag_service/capabilities/model_inference.py`
- `src/rag_service/capabilities/query_rewrite.py`
- `src/rag_service/capabilities/hallucination_detection.py`
- `src/rag_service/capabilities/milvus_kb_query.py`
