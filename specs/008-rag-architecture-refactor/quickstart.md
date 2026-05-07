# Quickstart: RAG Service Architecture Refactoring

**Branch**: `008-rag-architecture-refactor` | **Date**: 2026-05-07

## What Changed

| Metric | Before | After |
|--------|--------|-------|
| API Endpoints | 15+ | 5 |
| Capabilities | 13+ | 3 |
| Config Classes | 16 | 5 |
| Config Lines | 941 | ~300 |
| Inference Gateways | 3 (exposed) | 1 (LiteLLM) |

## Migration Guide for Callers

### 1. Query Endpoint

**Before** (4 different endpoints depending on use case):

```python
# Milvus query
POST /api/v1/query          → {"query": "...", "top_k": 5}

# External KB query
POST /api/v1/external/query → {"query": "...", "comp_id": "N000131"}

# QA pipeline
POST /qa/query              → {"query": "...", "context": {"company_id": "N000131"}}

# Agent query
POST /api/v1/ai/agent       → {"question": "...", "top_k": 5}
```

**After** (one endpoint for everything):

```python
POST /api/v1/query → {"query": "What is RAG?"}
```

All context, retrieval backend, and quality mode are auto-selected from configuration. No code changes needed when switching backends.

### 2. Document Management

**Before**:

```python
POST   /api/v1/documents          → upload
PUT    /api/v1/documents/{doc_id} → update
DELETE /api/v1/documents/{doc_id} → delete
```

**After**:

```python
POST /api/v1/documents → {"operation": "upload", "content": "..."}
POST /api/v1/documents → {"operation": "delete", "doc_id": "xxx"}
```

### 3. Configuration

**Before** (16 config sections, 941 lines):

```bash
MILVUS_HOST=...
MILVUS_PORT=...
LITELLM_API_KEY=...
CLOUD_COMPLETION_URL=...
CLOUD_COMPLETION_MODEL=...
GLM_API_KEY=...
GLM_MODEL=...
DEFAULT_GATEWAY=http
QA_ENABLE_QUERY_REWRITE=true
QUERY_QUALITY_REDIS_HOST=...
CONVERSATIONAL_QUERY_REDIS_HOST=...
EXTERNAL_KB_BASE_URL=...
# ... and many more
```

**After** (5 config sections, ~300 lines):

```bash
# Milvus
MILVUS_HOST=localhost
MILVUS_PORT=19530

# LiteLLM (unified inference)
LITELLM_PROVIDER=cloud_http
LITELLM_API_BASE=...
LITELLM_MODEL=Qwen3-32B

# Query (unified pipeline)
QUERY_RETRIEVAL_BACKEND=external_kb
QUERY_QUALITY_MODE=basic

# Langfuse (unchanged)
LANGFUSE_PUBLIC_KEY=...

# Server
SERVER_PORT=8000
```

## For Developers Working on RAG Service

### Architecture: 3 Capabilities

```
src/rag_service/capabilities/
├── query_capability.py       # "Ask a question, get an answer"
│   ├── RetrievalStrategy     # milvus | external_kb (Protocol)
│   └── QualityStrategy       # basic | dimension_gather | conversational (Protocol)
├── management_capability.py  # "Manage documents and list models"
└── trace_capability.py       # "Check health and inspect traces"
```

### Adding a New Retrieval Backend

1. Create a new file: `src/rag_service/strategies/pg_retrieval.py`
2. Implement the `RetrievalStrategy` protocol:

```python
class PgRetrieval:
    async def retrieve(self, query: str, top_k: int, **kwargs) -> list[dict]:
        # Your implementation
        ...
```

3. Register in `QueryCapability.__init__()`:

```python
if config.retrieval_backend == "pg":
    self._retrieval = PgRetrieval(config)
```

4. Set `QUERY_RETRIEVAL_BACKEND=pg` in `.env`

No API changes, no new endpoints, no new capabilities.

### Adding a New Quality Mode

Same pattern as retrieval — implement `QualityStrategy` protocol and register.

### Adding a New LLM Provider

Set in `.env`:

```bash
LITELLM_PROVIDER=glm
LITELLM_GLM_API_KEY=xxx
```

LiteLLM handles routing internally. No code changes needed for standard providers.
