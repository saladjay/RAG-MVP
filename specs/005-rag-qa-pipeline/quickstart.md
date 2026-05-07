# Quick Start Guide: RAG QA Pipeline

**Feature**: 005-rag-qa-pipeline
**Last Updated**: 2026-04-01

## Overview

The RAG QA Pipeline provides a question-answering service that processes natural language queries through query rewriting, knowledge base retrieval, answer generation, and hallucination detection.

---

## Prerequisites

- Python 3.11+
- uv package manager
- Access to external knowledge base (configured from Spec 001)
- LiteLLM gateway configured (from Spec 001)
- Existing RAG Service (Spec 001) running

---

## Installation

### 1. Install Dependencies

```bash
cd D:/project/OA/svn/代码组件
uv sync
```

### 2. Configure Environment

Create or update `.env` file:

```bash
# QA Pipeline Configuration
QA_ENABLE_QUERY_REWRITE=true
QA_ENABLE_HALLUCINATION_CHECK=true
QA_HALLUCINATION_THRESHOLD=0.7
QA_MAX_REGEN_ATTEMPTS=1
QA_REGEN_TIMEOUT=3

# Fallback messages (optional, defaults in code)
QA_FALLBACK_CONFIG_PATH=config/qa_fallback.yaml
```

### 3. Create Fallback Messages (Optional)

Create `config/qa_fallback.yaml`:

```yaml
fallback_messages:
  kb_unavailable:
    zh: "抱歉，知识库暂时无法访问。请稍后再试。"
  kb_empty:
    zh: "抱歉，没有找到与您的问题相关的信息。请尝试重新表述您的问题。"
  kb_error:
    zh: "抱歉，查询知识库时发生错误。请联系管理员。"
  hallucination_failed:
    zh: "抱歉，无法验证答案的准确性。请谨慎参考以下内容。"
```

---

## Running the Service

### Development Server

```bash
uv run uvicorn rag_service.main:app --reload --port 8000
```

### Production Server

```bash
uv run uvicorn rag_service.main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## API Usage

### Basic Query

```bash
curl -X POST http://localhost:8000/qa/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "2025年春节放假几天？"
  }'
```

### Query with Context

```bash
curl -X POST http://localhost:8000/qa/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "假期安排",
    "context": {
      "company_id": "N000131",
      "file_type": "PublicDocDispatch"
    }
  }'
```

### Query with Options

```bash
curl -X POST http://localhost:8000/qa/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "怎么请假？",
    "options": {
      "enable_query_rewrite": true,
      "enable_hallucination_check": true,
      "top_k": 5
    }
  }'
```

---

## Response Examples

### Successful Response

```json
{
  "answer": "2025年春节放假共计8天，从1月28日（农历除夕）至2月4日（农历正月初七）。",
  "sources": [
    {
      "chunk_id": "seg_12345",
      "document_id": "doc_67890",
      "document_name": "关于2025年度部分节假日安排的通知",
      "dataset_id": "ds_001",
      "dataset_name": "公司制度",
      "score": 0.95,
      "content_preview": "2025年春节放假共计8天，从1月28日..."
    }
  ],
  "hallucination_status": {
    "checked": true,
    "passed": true,
    "confidence": 0.92,
    "flagged_claims": []
  },
  "metadata": {
    "trace_id": "trace_abc123",
    "query_rewritten": true,
    "original_query": "春节放假几天？",
    "rewritten_query": "2025年春节放假安排",
    "retrieval_count": 5,
    "timing_ms": {
      "total_ms": 4500,
      "rewrite_ms": 1200,
      "retrieve_ms": 500,
      "generate_ms": 2500,
      "verify_ms": 300
    }
  }
}
```

### Fallback Response (Empty KB)

```json
{
  "answer": "抱歉，没有找到与您的问题相关的信息。请尝试重新表述您的问题，或者联系管理员获取帮助。",
  "sources": [],
  "hallucination_status": {
    "checked": false,
    "passed": false,
    "confidence": 0.0,
    "warning_message": "知识库中没有找到相关文档"
  },
  "metadata": {
    "trace_id": "trace_ghi789",
    "query_rewritten": true,
    "original_query": "公司股票代码是多少？",
    "retrieval_count": 0,
    "timing_ms": {
      "total_ms": 1500,
      "rewrite_ms": 800,
      "retrieve_ms": 700
    }
  }
}
```

---

## Python Client Usage

### Basic Usage

```python
import httpx

async def query_qa(question: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/qa/query",
            json={"query": question}
        )
        return response.json()

# Use it
result = await query_qa("2025年春节放假几天？")
print(result["answer"])
```

### With Context

```python
async def query_qa_with_context(question: str, company_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/qa/query",
            json={
                "query": question,
                "context": {
                    "company_id": company_id,
                    "file_type": "PublicDocDispatch"
                }
            }
        )
        return response.json()
```

---

## Streaming Response

### Server-Sent Events (SSE)

```python
import httpx
import asyncio

async def stream_query(question: str):
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            "http://localhost:8000/qa/query/stream",
            json={"query": question}
        ) as response:
            # Check hallucination status header
            status = response.headers.get("X-Hallucination-Checked", "pending")
            print(f"Verification status: {status}")

            # Stream tokens
            async for chunk in response.aiter_text():
                print(chunk, end="", flush=True)
```

---

## Configuration Options

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `QA_ENABLE_QUERY_REWRITE` | `true` | Enable query rewriting |
| `QA_ENABLE_HALLUCINATION_CHECK` | `true` | Enable hallucination detection |
| `QA_HALLUCINATION_THRESHOLD` | `0.7` | Similarity threshold (0.0-1.0) |
| `QA_MAX_REGEN_ATTEMPTS` | `1` | Max regeneration attempts |
| `QA_REGEN_TIMEOUT` | `3` | Regeneration timeout (seconds) |

### Hallucination Threshold Guide

| Threshold | Behavior | Use Case |
|-----------|----------|----------|
| `0.5 - 0.6` | Very strict | High-risk domains (medical, legal) |
| `0.7` | Balanced | General purpose (default) |
| `0.8 - 0.9` | Lenient | Allow creative answers |

---

## Testing

### Run Unit Tests

```bash
uv run pytest tests/unit/test_qa_pipeline.py -v
```

### Run Integration Tests

```bash
uv run pytest tests/integration/test_qa_pipeline_e2e.py -v
```

### Run with Coverage

```bash
uv run pytest --cov=rag_service.capabilities.qa_pipeline --cov-report=html
```

---

## Troubleshooting

### External KB Unavailable

**Error**: `kb_unavailable`

**Solution**:
1. Check external KB is running
2. Verify `EXTERNAL_KB_BASE_URL` in `.env`
3. Check network connectivity

### Low Answer Quality

**Possible Causes**:
- Query rewriting disabled
- Low `top_k` value
- Hallucination threshold too strict

**Solutions**:
```bash
# Enable query rewriting
QA_ENABLE_QUERY_REWRITE=true

# Increase retrieval count
top_k: 20

# Relax hallucination threshold
QA_HALLUCINATION_THRESHOLD=0.6
```

### Slow Response Time

**Target**: < 10 seconds (95th percentile)

**If slow**:
1. Check timing breakdown in response metadata
2. Consider disabling query rewriting for faster responses
3. Check LLM gateway performance

---

## Monitoring

### Health Check

```bash
curl http://localhost:8000/health
```

### Response

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "qa_pipeline": {
    "status": "healthy",
    "external_kb": "connected",
    "litellm": "connected",
    "hallucination_detector": "ready"
  }
}
```

---

## Next Steps

- **Prompts**: Customize query rewrite and generation prompts
- **Fallbacks**: Add domain-specific fallback messages
- **Monitoring**: Set up Langfuse observability
- **Scaling**: Configure worker count for production

---

## Support

- **Documentation**: `docs/qa-pipeline-architecture.md`
- **API Reference**: `docs/qa-pipeline-api.md`
- **Issues**: Create issue in project repository
