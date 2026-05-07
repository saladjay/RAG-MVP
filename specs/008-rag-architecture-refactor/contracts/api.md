# API Contract: Unified Query Endpoint

**Branch**: `008-rag-architecture-refactor` | **Date**: 2026-05-07

## Endpoints

### POST /api/v1/query

Unified query endpoint replacing `/ai/agent`, `/query`, `/external/query`, and `/qa/query`.

**Request**:

```json
{
  "query": "What are the travel expense policies?",
  "context": {
    "company_id": "N000131",
    "file_type": "PublicDocDispatch",
    "doc_date": ""
  },
  "session_id": null,
  "top_k": 10,
  "stream": false
}
```

**Minimum request** (all other fields have sensible defaults):

```json
{
  "query": "What is RAG?"
}
```

**Response (success)**:

```json
{
  "answer": "Based on the company policy document...",
  "sources": [
    {
      "chunk_id": "chunk_abc123",
      "content": "Travel expenses must be pre-approved...",
      "score": 0.92,
      "source_doc": "travel_policy_2026.pdf",
      "metadata": {}
    }
  ],
  "hallucination_status": {
    "checked": true,
    "passed": true,
    "confidence": 0.85,
    "flagged_claims": []
  },
  "metadata": {
    "trace_id": "trace_abc123",
    "query_rewritten": true,
    "original_query": "What are the travel expense policies?",
    "rewritten_query": "差旅费报销政策有哪些规定",
    "retrieval_count": 10,
    "retrieval_backend": "external_kb",
    "quality_mode": "dimension_gather",
    "quality_score": 0.75,
    "session_id": null,
    "timing_ms": {
      "total_ms": 1500,
      "rewrite_ms": 200,
      "retrieve_ms": 300,
      "generate_ms": 900,
      "verify_ms": 100
    }
  }
}
```

**Response (quality prompt — needs more info)**:

```json
{
  "answer": "",
  "sources": [],
  "hallucination_status": {"checked": false, "passed": true, "confidence": 0.0},
  "metadata": {
    "trace_id": "trace_def456",
    "query_rewritten": false,
    "original_query": "查差旅",
    "retrieval_count": 0,
    "retrieval_backend": "external_kb",
    "quality_mode": "dimension_gather",
    "quality_score": 0.3,
    "session_id": "session_789",
    "timing_ms": {"total_ms": 100}
  },
  "action": "prompt",
  "prompt_text": "请问您想查询哪一类的差旅政策？（报销标准/审批流程/住宿标准）",
  "dimensions": {
    "query_type": "travel",
    "document_type": null,
    "time_range": null
  },
  "feedback": "查询缺少关键维度：文档类型、时间范围"
}
```

**Error responses**:

```json
// 400 Bad Request
{
  "error": "invalid_query",
  "message": "Query cannot be empty",
  "trace_id": "trace_abc123"
}

// 503 Service Unavailable (KB down)
{
  "error": "kb_unavailable",
  "message": "知识库暂时无法访问，请稍后再试",
  "trace_id": "trace_abc123",
  "is_fallback": true
}

// 500 Internal Server Error
{
  "error": "generation_failed",
  "message": "生成答案时发生错误，请稍后重试",
  "trace_id": "trace_abc123"
}
```

---

### POST /api/v1/query/stream

Streaming variant of the query endpoint. Same request body, returns `text/event-stream`.

**Request**: Same as `POST /api/v1/query` with `stream: true`.

**Response**: Server-Sent Events

```
data: {"token": "根据"}
data: {"token": "公司"}
data: {"token": "差旅"}
data: {"token": "政策..."}
data: [DONE]
```

**Response headers**:
- `Content-Type: text/event-stream`
- `X-Trace-ID: trace_abc123`
- `X-Hallucination-Checked: pending`
- `Cache-Control: no-cache`

---

### POST /api/v1/documents

Unified document management endpoint.

**Request (upload)**:

```json
{
  "operation": "upload",
  "content": "Document text content here...",
  "metadata": {"source": "policy_2026.pdf", "category": "finance"}
}
```

**Request (delete)**:

```json
{
  "operation": "delete",
  "doc_id": "doc_abc123"
}
```

**Response**:

```json
{
  "doc_id": "doc_abc123",
  "operation": "upload",
  "chunk_count": 5,
  "trace_id": "trace_abc123"
}
```

---

### GET /api/v1/traces/{trace_id}

Unchanged from current implementation. Returns trace details with three-layer observability data.

**Response**: Same as current `TraceResponse`.

---

### GET /api/v1/models

Unchanged from current implementation. Lists available models through LiteLLM.

**Response**: Same as current `ModelsResponse`.

---

## Deprecated Endpoints (Transition Period)

The following endpoints remain functional but return `Deprecation` header:

| Old Endpoint | New Endpoint | Deprecation Header |
|-------------|-------------|-------------------|
| `POST /api/v1/ai/agent` | `POST /api/v1/query` | `Deprecation: true; version=0.2.0` |
| `POST /api/v1/query` (old) | `POST /api/v1/query` (enhanced) | No change |
| `POST /api/v1/external/query` | `POST /api/v1/query` | `Deprecation: true; version=0.2.0` |
| `POST /qa/query` | `POST /api/v1/query` | `Deprecation: true; version=0.2.0` |
| `POST /qa/query/stream` | `POST /api/v1/query/stream` | `Deprecation: true; version=0.2.0` |
| `GET /qa/health` | `GET /api/v1/traces/health` | `Deprecation: true; version=0.2.0` |
| `GET /api/v1/health` | `GET /api/v1/traces/health` | `Deprecation: true; version=0.2.0` |
| `DELETE /api/v1/documents/{id}` | `POST /api/v1/documents` (op=delete) | `Deprecation: true; version=0.2.0` |
| `PUT /api/v1/documents/{id}` | `POST /api/v1/documents` (op=update) | `Deprecation: true; version=0.2.0` |

---

## Configuration Contract

### Environment Variables (New)

```bash
# Milvus (unified)
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_COLLECTION=knowledge_base
MILVUS_DIMENSION=1024

# LiteLLM (unified inference)
LITELLM_PROVIDER=openai              # "openai" | "cloud_http" | "glm"
LITELLM_API_BASE=https://api.openai.com/v1
LITELLM_API_KEY=sk-xxx
LITELLM_MODEL=gpt-3.5-turbo

# Query pipeline (unified)
QUERY_RETRIEVAL_BACKEND=external_kb   # "milvus" | "external_kb"
QUERY_QUALITY_MODE=basic              # "basic" | "dimension_gather" | "conversational"
QUERY_ENABLE_REWRITE=true
QUERY_ENABLE_HALLUCINATION_CHECK=true

# External KB
QUERY_EXTERNAL_KB_BASE_URL=http://kb.example.com
QUERY_EXTERNAL_KB_AUTH_TOKEN=xxx

# Redis (shared by quality modes)
QUERY_REDIS_HOST=localhost
QUERY_REDIS_PORT=6379

# Langfuse (unchanged)
LANGFUSE_PUBLIC_KEY=xxx
LANGFUSE_SECRET_KEY=xxx

# Server
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
SERVER_LOG_LEVEL=INFO
```

### Deprecated Environment Variables (Accepted with Warning)

```bash
# These are mapped to new variables internally
CLOUD_COMPLETION_URL    → LITELLM_CLOUD_HTTP_URL
CLOUD_COMPLETION_MODEL  → LITELLM_CLOUD_HTTP_MODEL
GLM_API_KEY             → LITELLM_GLM_API_KEY
GLM_MODEL               → LITELLM_GLM_MODEL
DEFAULT_GATEWAY         → (removed, auto-detected from LITELLM_PROVIDER)
```
