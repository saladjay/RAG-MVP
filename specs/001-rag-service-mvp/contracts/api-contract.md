# API Contract: RAG Service MVP

**Feature**: 001-rag-service-mvp
**Version**: 1.0.0
**Date**: 2026-03-20

## Overview

This document defines the HTTP API contract for the RAG Service. All endpoints use JSON for request/response bodies and follow REST conventions.

## Base URL

```
Development: http://localhost:8000
Production: {configured via environment}
```

## Common Headers

| Header | Type | Required | Description |
|--------|------|----------|-------------|
| Content-Type | string | Yes | Must be `application/json` |
| Accept | string | No | Defaults to `application/json` |
| X-Request-ID | string | No | Unique request identifier for tracing |

## Common Response Codes

| Code | Meaning | Usage |
|------|---------|-------|
| 200 | Success | Request completed successfully |
| 400 | Bad Request | Invalid request parameters |
| 404 | Not Found | Resource not found |
| 500 | Internal Error | Server error (check response body) |

## Endpoints

### 1. Health Check

Check service health status.

**Endpoint**: `GET /health`

**Request**: No body

**Response** (200 OK):
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-03-20T10:00:00Z",
  "dependencies": {
    "milvus": "connected",
    "litellm": "connected",
    "langfuse": "connected"
  }
}
```

**Response** (503 Service Unavailable):
```json
{
  "status": "unhealthy",
  "error": "Milvus connection failed",
  "timestamp": "2026-03-20T10:00:00Z"
}
```

---

### 2. Query Agent

Submit a question to the RAG agent and receive an AI-generated answer with retrieved context.

**Endpoint**: `POST /ai/agent`

**Request Headers**:
- `Content-Type: application/json`

**Request Body**:
```json
{
  "question": "What is Retrieval-Augmented Generation?",
  "model_hint": "ollama/llama3",
  "context": {
    "language": "en"
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| question | string | Yes | User's question (1-2000 chars) |
| model_hint | string | No | Suggested model ID (must match configured provider) |
| context | object | No | Additional context for the query |

**Response** (200 OK):
```json
{
  "answer": "Retrieval-Augmented Generation (RAG) is an AI framework...",
  "chunks": [
    {
      "chunk_id": "chunk_123",
      "content": "RAG combines retrieval systems with generative models...",
      "score": 0.95,
      "source_doc": "doc_rag_intro",
      "timestamp": "2026-03-20T09:00:00Z"
    }
  ],
  "trace_id": "trace_abc123",
  "metadata": {
    "model_used": "ollama/llama3",
    "total_latency_ms": 2340,
    "retrieval_time_ms": 450,
    "inference_time_ms": 1890,
    "input_tokens": 150,
    "output_tokens": 85,
    "estimated_cost": 0.0
  }
}
```

**Response** (400 Bad Request):
```json
{
  "error": "validation_error",
  "message": "Question cannot be empty",
  "details": {
    "field": "question",
    "constraint": "min_length=1"
  }
}
```

**Response** (500 Internal Server Error):
```json
{
  "error": "inference_error",
  "message": "Failed to connect to model provider",
  "trace_id": "trace_xyz789"
}
```

---

### 3. List Available Models

Get a list of available AI models configured for inference.

**Endpoint**: `GET /models`

**Request**: No body

**Response** (200 OK):
```json
{
  "models": [
    {
      "model_id": "ollama/llama3",
      "provider": "ollama",
      "type": "local",
      "available": true
    },
    {
      "model_id": "openai/gpt-4",
      "provider": "openai",
      "type": "cloud",
      "available": true
    },
    {
      "model_id": "claude-3-opus",
      "provider": "anthropic",
      "type": "cloud",
      "available": false
    }
  ]
}
```

---

### 4. Get Trace by ID

Retrieve detailed trace information for a specific request.

**Endpoint**: `GET /traces/{trace_id}`

**Path Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| trace_id | string | Yes | Unique trace identifier |

**Response** (200 OK):
```json
{
  "trace_id": "trace_abc123",
  "request_prompt": "What is RAG?",
  "user_context": {},
  "start_time": "2026-03-20T10:00:00Z",
  "end_time": "2026-03-20T10:00:02.340Z",
  "spans": [
    {
      "span_id": "span_001",
      "span_name": "retrieval",
      "span_type": "retrieval",
      "latency_ms": 450,
      "metadata": {
        "chunks_count": 3,
        "chunk_ids": ["chunk_123", "chunk_456", "chunk_789"]
      }
    },
    {
      "span_id": "span_002",
      "span_name": "inference",
      "span_type": "inference",
      "latency_ms": 1890,
      "metadata": {
        "model_id": "ollama/llama3",
        "input_tokens": 150,
        "output_tokens": 85
      }
    }
  ]
}
```

**Response** (404 Not Found):
```json
{
  "error": "not_found",
  "message": "Trace not found",
  "trace_id": "trace_unknown"
}
```

---

## Error Response Format

All error responses follow this structure:

```json
{
  "error": "error_code",
  "message": "Human-readable error message",
  "details": {},
  "trace_id": "trace_id_if_available"
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `validation_error` | 400 | Request validation failed |
| `model_not_available` | 400 | Requested model is not available |
| `retrieval_error` | 500 | Knowledge base query failed |
| `inference_error` | 500 | Model inference failed |
| `tracing_error` | 500 | Observability capture failed (non-blocking) |
| `not_found` | 404 | Resource not found |
| `internal_error` | 500 | Unexpected server error |

## Rate Limiting

Not implemented in MVP. Future versions may include rate limiting based on:
- Requests per minute per IP
- Requests per minute per API key
- Concurrent request limits

## Authentication

Not implemented in MVP. Future versions may include:
- API key authentication
- OAuth2 bearer tokens
- JWT-based authentication

## Versioning

API versioning via URL path:
- Current: `v1` (implicit)
- Future: `GET /v1/ai/agent`

Breaking changes will result in a new major version (v2).

## SDK Examples

### Python (requests)

```python
import requests

# Query the agent
response = requests.post(
    "http://localhost:8000/ai/agent",
    json={"question": "What is RAG?"}
)

if response.status_code == 200:
    data = response.json()
    print(f"Answer: {data['answer']}")
    print(f"Trace ID: {data['trace_id']}")
```

### cURL

```bash
# Health check
curl http://localhost:8000/health

# Query agent
curl -X POST http://localhost:8000/ai/agent \
  -H "Content-Type: application/json" \
  -d '{"question": "What is RAG?"}'

# List models
curl http://localhost:8000/models
```

### JavaScript (fetch)

```javascript
// Query the agent
const response = await fetch('http://localhost:8000/ai/agent', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({question: 'What is RAG?'})
});

const data = await response.json();
console.log('Answer:', data.answer);
console.log('Trace ID:', data.trace_id);
```
