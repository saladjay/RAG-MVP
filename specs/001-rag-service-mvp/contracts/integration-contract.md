# Integration Contract: External Services

**Feature**: 001-rag-service-mvp
**Version**: 1.0.0
**Date**: 2026-03-20

## Overview

This document defines the integration contracts between the RAG Service and external dependencies: Milvus (vector database), LiteLLM (model gateway), and Langfuse (observability).

---

## 1. Milvus Integration

### Service Information

| Property | Value |
|----------|-------|
| Service | Milvus Vector Database |
| Version | 2.3+ |
| Protocol | gRPC / HTTP |
| Default Port | 19530 |
| Documentation | https://milvus.io/docs |

### Connection Configuration

```python
# src/rag_service/retrieval/knowledge_base.py
connections.connect(
    alias="default",
    host="localhost",  # MILVUS_HOST env var
    port="19530",      # MILVUS_PORT env var
    pool_size=10       # Connection pool size
)
```

### Collection Schema

**Collection Name**: `rag_documents`

```python
fields = [
    FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=100, is_primary=True),
    FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=1536),
    FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
    FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=100),
    FieldSchema(name="created_at", dtype=DataType.INT64)
]
```

### Index Configuration

```python
index_params = {
    "index_type": "IVF_FLAT",
    "metric_type": "COSINE",
    "params": {"nlist": 128}
}
```

### Operations

#### Search

**Input**:
- `query_vector`: List[float] (1536 dimensions)
- `top_k`: int (default: 5)

**Output**:
```python
[
    {
        "id": "chunk_123",
        "distance": 0.15,  # Lower = more similar for COSINE
        "entity": {
            "chunk_id": "chunk_123",
            "text": "Chunk content...",
            "doc_id": "doc_abc"
        }
    }
]
```

**Error Handling**:
| Error | Action |
|-------|--------|
| Connection failed | Retry 3x with backoff |
| Collection not found | Create collection automatically |
| Search timeout | Return empty results, log error |

#### Insert

**Input**:
```python
[
    {
        "chunk_id": "chunk_123",
        "vector": [0.1, 0.2, ...],  # 1536 floats
        "text": "Chunk content",
        "doc_id": "doc_abc",
        "created_at": 1710936000
    }
]
```

**Output**: Insert count (int)

---

## 2. LiteLLM Integration

### Service Information

| Property | Value |
|----------|-------|
| Service | LiteLLM Proxy |
| Version | 1.0+ |
| Protocol | HTTP |
| Default Port | 4000 |
| Documentation | https://docs.litellm.ai |

### Configuration

```yaml
# litellm_config.yaml
model_list:
  - model_name: ollama/llama3
    litellm_params:
      api_base: http://localhost:11434
      rpm_limit: 60  # Requests per minute
  - model_name: openai/gpt-4
    litellm_params:
      api_key: ${OPENAI_API_KEY}
  - model_name: claude-3-opus
    litellm_params:
      api_key: ${ANTHROPIC_API_KEY}
```

### Operations

#### Completion

**Endpoint**: `POST http://localhost:4000/v1/completions`

**Request**:
```json
{
  "model": "ollama/llama3",
  "prompt": "Answer the question based on context: [context]\n\nQuestion: [question]",
  "max_tokens": 500,
  "temperature": 0.7
}
```

**Response**:
```json
{
  "id": "cmpl-123",
  "object": "text_completion",
  "created": 1710936000,
  "model": "ollama/llama3",
  "choices": [
    {
      "text": "The answer is...",
      "index": 0,
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 150,
    "completion_tokens": 85,
    "total_tokens": 235
  }
}
```

**Error Responses**:
| Status | Error | Action |
|--------|-------|--------|
| 400 | Invalid model | Return 400 to client |
| 401 | Invalid API key | Log error, try fallback model |
| 503 | Model unavailable | Retry with backoff, try fallback |

#### Chat Completion (Alternative)

**Endpoint**: `POST http://localhost:4000/v1/chat/completions`

**Request**:
```json
{
  "model": "ollama/llama3",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Answer based on context..."}
  ],
  "max_tokens": 500
}
```

---

## 3. Langfuse Integration

### Service Information

| Property | Value |
|----------|-------|
| Service | Langfuse Observability |
| Version | 2.0+ |
| Protocol | HTTP |
| SDK | langfuse (Python) |
| Documentation | https://langfuse.com/docs |

### Configuration

```python
# src/rag_service/observability/langfuse_client.py
from langfuse import Langfuse

client = Langfuse(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
)
```

### Operations

#### Create Trace

```python
trace = client.trace(
    id="trace_abc123",  # UUID
    name="rag-query",
    input={"question": "What is RAG?", "context": {}},
    metadata={"model_hint": "ollama/llama3"}
)
```

#### Create Span (Retrieval)

```python
span = trace.span(
    name="retrieval",
    input={"query": "What is RAG?"},
    metadata={
        "chunks_count": 3,
        "retrieval_time_ms": 450
    }
)
span.end(output={"chunks": ["chunk_123", "chunk_456"]})
```

#### Create Span (Inference)

```python
span = trace.span(
    name="inference",
    input={"prompt": "...", "model": "ollama/llama3"},
    metadata={
        "model_id": "ollama/llama3",
        "latency_ms": 1890
    }
)
span.end(
    output={"answer": "The answer is..."},
    usage={"input": 150, "output": 85, "total": 235}
)
```

#### Update Trace (Completion)

```python
trace.update(
    output={"answer": "...", "chunks": [...]},
    metadata={
        "total_latency_ms": 2340,
        "estimated_cost": 0.0
    }
)
```

### Error Handling

| Condition | Action |
|-----------|--------|
| Connection timeout | Log warning, continue (non-blocking) |
| Invalid credentials | Log error, disable tracing |
| Flush failure | Background retry |

---

## 4. OpenAI Embeddings Integration

### Service Information

| Property | Value |
|----------|-------|
| Service | OpenAI API |
| Operation | Embeddings |
| Model | text-embedding-3-small |
| Documentation | https://platform.openai.com/docs |

### Operations

#### Create Embedding

**Endpoint**: `POST https://api.openai.com/v1/embeddings`

**Request**:
```json
{
  "model": "text-embedding-3-small",
  "input": "Text to embed",
  "dimensions": 1536
}
```

**Response**:
```json
{
  "object": "list",
  "data": [
    {
      "object": "embedding",
      "index": 0,
      "embedding": [0.1, 0.2, ...]  // 1536 floats
    }
  ],
  "model": "text-embedding-3-small",
  "usage": {"prompt_tokens": 5, "total_tokens": 5}
}
```

---

## 5. Connection Health Checks

Each integration should implement health check logic:

```python
# src/rag_service/core/health.py
async def check_milvus_health() -> bool:
    try:
        connections.list_connections()
        return True
    except Exception:
        return False

async def check_litellm_health() -> bool:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:4000/health/status")
            return response.status_code == 200
    except Exception:
        return False

async def check_langfuse_health() -> bool:
    # Langfuse is non-blocking; we check auth only
    try:
        client = Langfuse()
        client.auth_check()
        return True
    except Exception:
        return False
```

---

## 6. Retry Strategies

| Service | Max Retries | Backoff | Timeout |
|---------|-------------|---------|---------|
| Milvus | 3 | Exponential (2x) | 5s |
| LiteLLM | 2 | Fixed (1s) | 30s |
| Langfuse | 1 | None | 2s |
| OpenAI Embeddings | 3 | Exponential (2x) | 10s |

---

## 7. Configuration Management

All external service configuration via environment variables:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| MILVUS_HOST | No | localhost | Milvus server host |
| MILVUS_PORT | No | 19530 | Milvus server port |
| LITELLM_HOST | No | localhost | LiteLLM proxy host |
| LITELLM_PORT | No | 4000 | LiteLLM proxy port |
| OPENAI_API_KEY | Yes* | - | OpenAI API key |
| ANTHROPIC_API_KEY | No* | - | Anthropic API key |
| LANGFUSE_PUBLIC_KEY | No | - | Langfuse public key |
| LANGFUSE_SECRET_KEY | No | - | Langfuse secret key |
| LANGFUSE_HOST | No | https://cloud.langfuse.com | Langfuse server |

*Required if using those models.

---

## 8. Contract Testing

Each integration should have contract tests in `tests/contract/`:

```python
# tests/contract/test_milvus_contract.py
async def test_milvus_search_returns_expected_format():
    kb = KnowledgeBase()
    results = await kb.search(query_vector, top_k=5)
    assert isinstance(results, list)
    if results:
        assert "chunk_id" in results[0]
        assert "score" in results[0]

# tests/contract/test_litellm_contract.py
async def test_litellm_completion_returns_expected_format():
    gateway = ModelGateway()
    response = await gateway.complete("test prompt")
    assert "text" in response or "choices" in response
```
