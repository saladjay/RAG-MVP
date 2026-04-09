# RAG QA Pipeline API Reference

**Feature**: 005 - RAG QA Pipeline
**Version**: 1.0
**Last Updated**: 2026-04-02

## Overview

The RAG QA Pipeline provides REST API endpoints for question-answering with external knowledge base integration. It supports both non-streaming and streaming responses, with optional query rewriting and hallucination detection.

## Base URL

```
http://your-server:8000
```

## Authentication

Currently, the API does not require authentication. This is subject to change in future versions.

## Common Headers

### X-Trace-ID

Optional header for request tracing. If not provided, a new trace ID will be generated.

```http
X-Trace-ID: custom-trace-id
```

## Endpoints

### 1. Query Answer (Non-Streaming)

Submit a question and receive a complete answer with sources.

```http
POST /qa/query
```

#### Request Body

```json
{
  "query": "2025年春节放假几天？",
  "context": {
    "company_id": "N000131",
    "file_type": "PublicDocDispatch",
    "doc_date": "2025-01-01"
  },
  "options": {
    "enable_query_rewrite": true,
    "enable_hallucination_check": true,
    "top_k": 10,
    "stream": false
  }
}
```

#### Request Parameters

| Field | Type | Required | Description | Constraints |
|-------|------|----------|-------------|-------------|
| query | string | Yes | User's natural language question | 1-1000 characters, not empty |
| context | object | No | Additional context for retrieval | - |
| context.company_id | string | No | Company/organization identifier | Format: N + digits (e.g., N000131) |
| context.file_type | string | No | Document type filter | PublicDocReceive, PublicDocDispatch |
| context.doc_date | string | No | Document date filter | ISO 8601 date format |
| options | object | No | Processing options | - |
| options.enable_query_rewrite | boolean | No | Enable query rewriting | Default: true |
| options.enable_hallucination_check | boolean | No | Enable hallucination detection | Default: true |
| options.top_k | integer | No | Number of chunks to retrieve | Range: 1-50, Default: 10 |
| options.stream | boolean | No | Use streaming response | Default: false (for non-streaming endpoint) |

#### Response (200 OK)

```json
{
  "answer": "根据现有信息，2025年春节放假安排如下...",
  "sources": [
    {
      "chunk_id": "chunk_12345",
      "document_id": "doc_67890",
      "document_name": "关于2025年春节放假的通知",
      "dataset_id": "dataset_001",
      "dataset_name": "公司公文",
      "score": 0.95,
      "content_preview": "根据国家法定节假日安排..."
    }
  ],
  "hallucination_status": {
    "checked": true,
    "passed": true,
    "confidence": 0.85,
    "flagged_claims": [],
    "warning_message": null
  },
  "metadata": {
    "trace_id": "req_abc123",
    "query_rewritten": true,
    "original_query": "2025年春节放假几天？",
    "rewritten_query": "2025年春节放假安排查询",
    "rewrite_reason": "添加时间上下文",
    "retrieval_count": 5,
    "generation_model": "gpt-3.5-turbo",
    "timing": {
      "rewrite_ms": 1250,
      "retrieve_ms": 450,
      "generate_ms": 2100,
      "verify_ms": 320,
      "total_ms": 4120
    }
  }
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| answer | string | Generated answer text |
| sources | array | List of retrieved document chunks |
| sources[].chunk_id | string | Unique chunk identifier |
| sources[].document_id | string | Source document ID |
| sources[].document_name | string | Source document name |
| sources[].dataset_id | string | Dataset identifier |
| sources[].dataset_name | string | Dataset name |
| sources[].score | number | Relevance score (0-1) |
| sources[].content_preview | string | First 200 characters |
| hallucination_status | object | Hallucination detection result |
| hallucination_status.checked | boolean | Whether verification was performed |
| hallucination_status.passed | boolean | Whether verification passed |
| hallucination_status.confidence | number | Similarity confidence (0-1) |
| hallucination_status.flagged_claims | array | Claims that couldn't be verified |
| hallucination_status.warning_message | string | User-facing warning (if applicable) |
| metadata | object | Execution metadata |
| metadata.trace_id | string | Request trace ID |
| metadata.query_rewritten | boolean | Whether query was rewritten |
| metadata.original_query | string | Original user query |
| metadata.rewritten_query | string | Rewritten query (if applicable) |
| metadata.rewrite_reason | string | Reason for rewrite (if applicable) |
| metadata.retrieval_count | number | Number of chunks retrieved |
| metadata.generation_model | string | Model used for generation |
| metadata.timing | object | Timing breakdown (ms) |
| metadata.timing.total_ms | number | Total end-to-end time |
| metadata.timing.rewrite_ms | number | Query rewrite time (null if disabled) |
| metadata.timing.retrieve_ms | number | KB retrieval time |
| metadata.timing.generate_ms | number | Answer generation time |
| metadata.timing.verify_ms | number | Hallucination check time (null if disabled) |

#### Error Responses

**400 Bad Request** - Invalid request parameters

```json
{
  "detail": {
    "error": "invalid_query",
    "message": "Query cannot be empty",
    "trace_id": "req_abc123"
  }
}
```

**400 Bad Request** - Invalid company_id format

```json
{
  "detail": {
    "error": "invalid_query",
    "message": "Invalid company_id format (expected N followed by digits, e.g., N000131)",
    "trace_id": "req_abc123"
  }
}
```

**400 Bad Request** - Invalid file_type

```json
{
  "detail": {
    "error": "invalid_query",
    "message": "file_type must be one of: PublicDocReceive, PublicDocDispatch",
    "trace_id": "req_abc123"
  }
}
```

**503 Service Unavailable** - External services unavailable

```json
{
  "answer": "知识库暂时无法访问，请稍后再试。",
  "sources": [],
  "hallucination_status": {
    "checked": false,
    "passed": false,
    "confidence": 0.0
  },
  "metadata": {
    "trace_id": "req_abc123",
    "query_rewritten": false,
    "original_query": "...",
    "retrieval_count": 0,
    "generation_model": "none",
    "timing": {
      "total_ms": 250
    }
  }
}
```

### 2. Query Answer (Streaming)

Submit a question and receive the answer as a stream of tokens.

```http
POST /qa/query/stream
```

#### Request Body

Same as non-streaming endpoint. Set `options.stream` to `true`.

#### Response (200 OK)

Server-Sent Events (SSE) format:

```
data: 根据
data: 现有
data: 信息
data: ，
data: 2025年
...
data: [DONE]
```

#### Response Headers

```
Content-Type: text/event-stream
X-Hallucination-Checked: pending
X-Trace-ID: req_abc123
Cache-Control: no-cache
Connection: keep-alive
```

#### Streaming Behavior

- Tokens arrive incrementally as they are generated
- Each SSE event contains a token or partial token
- `[DONE]` signal indicates stream completion
- X-Hallucination-Checked header updates after completion:
  - `pending`: Hallucination check in progress
  - `passed`: Check completed successfully
  - `failed`: Check failed (answer may be unreliable)
  - `skipped`: Check was not enabled

### 3. Health Check

Check the health status of QA pipeline components.

```http
GET /qa/health
```

#### Response (200 OK)

```json
{
  "status": "healthy",
  "external_kb": "connected",
  "litellm": "connected",
  "hallucination_detector": "ready",
  "fallback_ready": "ready"
}
```

#### Health Status Values

| Component | Status Values | Description |
|-----------|---------------|-------------|
| status | healthy, degraded, unhealthy, initializing | Overall system status |
| external_kb | connected, disconnected, error | KB connection status |
| litellm | connected, not_configured, error | LLM gateway status |
| hallucination_detector | ready, not_configured, error | Verification status |
| fallback_ready | ready, not_configured | Fallback service status |

## Error Codes

| Error Code | HTTP Status | Description |
|------------|-------------|-------------|
| invalid_query | 400 | Query validation failed |
| invalid_company_id | 400 | Company ID format invalid |
| invalid_file_type | 400 | File type not in enum |
| invalid_top_k | 400 | top_k outside valid range |
| kb_unavailable | 503 | External KB service unavailable |
| kb_error | 503 | External KB returned error |
| generation_error | 500 | Answer generation failed |
| hallucination_failed | 500 | Hallucination check failed |
| not_implemented | 501 | Feature not yet implemented (streaming) |

## Usage Examples

### Basic Query

```bash
curl -X POST "http://localhost:8000/qa/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "什么是RAG（Retrieval-Augmented Generation）？"
  }'
```

### Query with Context

```bash
curl -X POST "http://localhost:8000/qa/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "2025年春节放假几天？",
    "context": {
      "company_id": "N000131",
      "file_type": "PublicDocDispatch"
    }
  }'
```

### Query with Custom Options

```bash
curl -X POST "http://localhost:8000/qa/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "春节放假",
    "options": {
      "enable_query_rewrite": true,
      "enable_hallucination_check": true,
      "top_k": 5
    }
  }'
```

### Streaming Query

```bash
curl -X POST "http://localhost:8000/qa/query/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "什么是机器学习？"
  }'
```

### Custom Trace ID

```bash
curl -X POST "http://localhost:8000/qa/query" \
  -H "Content-Type: application/json" \
  -H "X-Trace-ID: my-custom-trace-123" \
  -d '{
    "query": "Test question"
  }'
```

## Performance Guidelines

### Expected Latency

| Percentile | Latency | Notes |
|------------|---------|-------|
| p50 | < 3s | Median response time |
| p95 | < 10s | 95th percentile (success criterion) |
| p99 | < 15s | Worst case for complex queries |

### Optimization Tips

1. **Use specific queries** - More specific queries get better results
2. **Enable query rewriting** - Improves retrieval for vague queries
3. **Adjust top_k** - Lower values (5-10) are faster, higher values (20-50) are more thorough
4. **Consider streaming** - For long answers, streaming provides faster perceived response
5. **Disable hallucination check** - For non-critical queries, this saves 300-500ms

## Rate Limiting

Currently, there are no rate limits enforced. This is subject to change in future versions. Implement client-side rate limiting for production use.

## Versioning

The API follows semantic versioning. Breaking changes will result in a major version increment.

## Support

For issues or questions:
- Check the trace_id in error responses for debugging
- Review the health endpoint status
- Consult the architecture documentation for component details
