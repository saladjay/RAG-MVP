# RAG Service API Contract

**Feature**: 002-e2e-test-interface
**Date**: 2026-03-30
**Status**: Final

---

## Overview

This document specifies the contract between the E2E Test Framework and the RAG Service API. The E2E Test Framework acts as a client, making HTTP requests to validate RAG Service responses.

---

## 1. Service Endpoint

### Base URL

```
http://localhost:8000
```

Configurable via `E2E_TEST_RAG_SERVICE_URL` environment variable or `--url` CLI flag.

### Target Endpoint

```
POST /api/v1/ai/agent
```

---

## 2. Request Contract

### HTTP Method
`POST`

### Headers

| Header | Value | Required |
|--------|-------|----------|
| `Content-Type` | `application/json` | ✅ |
| `Accept` | `application/json` | ❌ |
| `X-Trace-ID` | `<uuid>` | ❌ |

### Request Body Schema

```json
{
  "type": "object",
  "required": ["question"],
  "properties": {
    "question": {
      "type": "string",
      "minLength": 1,
      "maxLength": 10000,
      "description": "User question to process"
    },
    "trace_id": {
      "type": "string",
      "format": "uuid",
      "description": "Optional trace ID for observability"
    },
    "context": {
      "type": "object",
      "description": "Additional context (optional, not used by E2E tests)"
    }
  }
}
```

### Example Request

```json
{
  "question": "What is the RAG Service?",
  "trace_id": "e2e-test-001-1234567890"
}
```

---

## 3. Response Contract

### Success Response (200 OK)

#### Headers

| Header | Value |
|--------|-------|
| `Content-Type` | `application/json` |

#### Body Schema

```json
{
  "type": "object",
  "required": ["answer", "trace_id"],
  "properties": {
    "answer": {
      "type": "string",
      "description": "Generated answer from the RAG system"
    },
    "trace_id": {
      "type": "string",
      "format": "uuid",
      "description": "Trace ID for observability correlation"
    },
    "source_documents": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": { "type": "string" },
          "content": { "type": "string" },
          "score": { "type": "number" }
        }
      },
      "description": "Retrieved source documents"
    },
    "metadata": {
      "type": "object",
      "properties": {
        "model": { "type": "string" },
        "latency_ms": { "type": "number" },
        "tokens_used": { "type": "integer" }
      }
    }
  }
}
```

#### Example Success Response

```json
{
  "answer": "The RAG Service is a retrieval-augmented generation system that combines vector search with large language model generation to provide accurate, context-aware responses.",
  "trace_id": "e2e-test-001-1234567890",
  "source_documents": [
    {
      "id": "doc_rag_intro",
      "content": "RAG Service introduction...",
      "score": 0.92
    },
    {
      "id": "doc_rag_architecture",
      "content": "Architecture overview...",
      "score": 0.87
    }
  ],
  "metadata": {
    "model": "gpt-4",
    "latency_ms": 1250,
    "tokens_used": 450
  }
}
```

### Error Responses

#### 400 Bad Request

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Question is required",
    "details": {}
  }
}
```

#### 500 Internal Server Error

```json
{
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "An unexpected error occurred",
    "details": {}
  }
}
```

#### 503 Service Unavailable

```json
{
  "error": {
    "code": "SERVICE_UNAVAILABLE",
    "message": "RAG Service is currently unavailable",
    "details": {}
  }
}
```

---

## 4. E2E Test Framework Client Contract

### RAGClient Interface

```python
from typing import Dict, Any, List, Optional
from httpx import AsyncClient, TimeoutException, HTTPStatusError

class RAGClient:
    """RAG Service API client for E2E testing."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout_seconds: int = 30,
    ):
        """Initialize client.

        Args:
            base_url: RAG Service base URL
            timeout_seconds: Request timeout
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout_seconds

    async def query(
        self,
        question: str,
        trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Query the RAG Service.

        Args:
            question: User question
            trace_id: Optional trace ID for observability

        Returns:
            Parsed JSON response with answer, source_documents, etc.

        Raises:
            RAGConnectionError: Network/connection failure
            RAGTimeoutError: Request timeout
            RAGServerError: 5xx server error
            RAGClientError: 4xx client error
        """
        ...

    async def health_check(self) -> bool:
        """Check if RAG Service is healthy.

        Returns:
            True if service is healthy, False otherwise
        """
        ...
```

### Error Hierarchy

```python
class E2ETestError(Exception):
    """Base exception for E2E test framework."""
    pass

class RAGConnectionError(E2ETestError):
    """Network connection failure."""
    pass

class RAGTimeoutError(E2ETestError):
    """Request timeout."""
    pass

class RAGServerError(E2ETestError):
    """5xx server error response."""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"Server error {status_code}: {message}")

class RAGClientError(E2ETestError):
    """4xx client error response."""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"Client error {status_code}: {message}")
```

---

## 5. Timeout and Retry Behavior

### Timeout Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `connect_timeout` | 5 seconds | TCP connection timeout |
| `read_timeout` | 30 seconds | Response read timeout |
| `total_timeout` | 35 seconds | Total request timeout |

### Retry Strategy

| Condition | Retry? | Max Retries | Backoff |
|-----------|--------|-------------|---------|
| Connection refused | ✅ | 3 | Exponential (1s, 2s, 4s) |
| Timeout | ✅ | 2 | Fixed (2s) |
| 5xx Server Error | ✅ | 3 | Exponential (1s, 2s, 4s) |
| 4xx Client Error | ❌ | 0 | N/A |

### Retry Configuration

```python
# Environment variables
E2E_TEST_RETRY_COUNT=3        # Max retry attempts
E2E_TEST_RETRY_BACKOFF=1.0    # Base backoff in seconds
```

---

## 6. Source Document Matching

### Document ID Extraction

The E2E Test Framework extracts document IDs from `source_documents` array:

```python
# Response format
{
  "source_documents": [
    {"id": "doc_rag_intro", "score": 0.92, ...},
    {"id": "doc_rag_architecture", "score": 0.87, ...}
  ]
}

# Extracted IDs for validation
["doc_rag_intro", "doc_rag_architecture"]
```

### Matching Logic

| Test Config | Response | Match Result |
|-------------|----------|--------------|
| `source_docs: ["doc_a"]` | `["doc_a", "doc_b"]` | ✅ Partial match (superset) |
| `source_docs: ["doc_a"]` | `["doc_a"]` | ✅ Exact match |
| `source_docs: ["doc_a", "doc_b"]` | `["doc_a"]` | ❌ Missing expected doc |
| `source_docs: []` (not specified) | `["doc_a"]` | ⏭️ Skipped (no expectation) |

### Match Types

```python
class SourceDocsMatch(str, Enum):
    """Source document match result."""
    EXACT = "exact"          # Response matches expectation exactly
    SUPERSET = "superset"    # Response contains all expected + more
    SUBSET = "subset"        # Response missing some expected
    NONE = "none"            # No overlap at all
    NOT_APPLICABLE = "n/a"   # No source_docs specified in test
```

---

## 7. Observability Integration

### Trace ID Propagation

```python
# E2E Test Framework generates trace IDs
test_trace_id = f"e2e-{test_case.id}-{uuid4()}"

# Pass to RAG Service
response = await rag_client.query(
    question=test_case.question,
    trace_id=test_trace_id
)

# Trace ID in response for correlation
assert response["trace_id"] == test_trace_id
```

### Logging Format

```json
{
  "timestamp": "2026-03-30T10:00:00Z",
  "level": "INFO",
  "trace_id": "e2e-test-001-1234567890",
  "test_id": "test_basic_query",
  "event": "rag_query_start",
  "rag_service_url": "http://localhost:8000"
}
```

---

## 8. Health Check Contract

### Health Endpoint

```
GET /health
```

### Expected Response (200 OK)

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "dependencies": {
    "milvus": "ok",
    "llm_provider": "ok"
  }
}
```

### Pre-Test Health Check

```python
# Before running test suite
if not await rag_client.health_check():
    print("ERROR: RAG Service is not healthy")
    sys.exit(1)
```

---

## 9. Performance Expectations

| Metric | Target | Threshold |
|--------|--------|-----------|
| **Response time** | < 2s | < 5s |
| **Connection** | < 100ms | < 500ms |
| **Throughput** | 10 req/s | 5 req/s |

### Performance Failure Handling

- **Warning**: Response time > 2s but < 5s
- **Failure**: Response time >= 5s (timeout)
- **Skip**: If service is degraded (health check returns degraded)

---

## 10. Security Considerations

### No Authentication (Phase 1)

Current specification assumes RAG Service is running in a trusted environment:
- No API key required
- No OAuth token
- Direct HTTP access

### Future Authentication Support

```python
# Reserved for future use
class RAGClient:
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,  # Future
        auth_token: Optional[str] = None,  # Future
    ):
        ...
```

---

**Status**: ✅ RAG Service API contract defined
