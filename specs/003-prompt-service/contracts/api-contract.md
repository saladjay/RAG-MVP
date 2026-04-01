# API Contract: Prompt Management Service

**Feature**: 003-prompt-service | **Date**: 2026-03-23
**Version**: v1 | **Base Path**: `/api/v1`

## Overview

This document defines the REST API contract for the Prompt Management Service. All endpoints use JSON request/response format.

---

## Common Headers

| Header | Required | Description |
|--------|----------|-------------|
| `Content-Type` | Yes | Must be `application/json` |
| `X-Trace-ID` | No | Client-provided trace ID for debugging |
| `X-API-Key` | No | API key for authentication (future) |
| `Authorization` | No | Bearer token for authentication (future) |

---

## Common Response Fields

All responses include:
```json
{
  "trace_id": "string (UUID)",  // For tracing requests
  "timestamp": "ISO-8601"
}
```

Error responses follow this format:
```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable error message",
  "details": {},
  "trace_id": "UUID",
  "timestamp": "ISO-8601"
}
```

---

## Endpoints

### Health Check

#### GET /health

Check service health status.

**Response**:
```json
{
  "status": "healthy | degraded | unhealthy",
  "version": "string",
  "components": {
    "langfuse": "connected | disconnected",
    "cache": "enabled | disabled"
  },
  "uptime_ms": 12345.67
}
```

---

### Prompt Retrieval

#### POST /prompts/{template_id}/retrieve

Retrieve and render a prompt template with variables.

**Path Parameters**:
- `template_id` (string): The prompt template identifier

**Request Body**:
```json
{
  "variables": {
    "input": "User input text",
    "context": "Additional context"
  },
  "context": {
    "user_id": "string",
    "session_id": "string"
  },
  "retrieved_docs": [
    {
      "id": "string",
      "content": "Document content",
      "metadata": {}
    }
  ],
  "options": {
    "version_id": 123,           // Optional: specific version
    "include_metadata": false    // Optional: include version metadata
  }
}
```

**Response** (200 OK):
```json
{
  "content": "Fully assembled and rendered prompt text",
  "template_id": "financial_analysis",
  "version_id": 3,
  "variant_id": "variant_a",    // Present if A/B test
  "sections": [                 // Present if include_metadata
    {"name": "角色", "content": "..."},
    {"name": "任务", "content": "..."}
  ],
  "metadata": {
    "created_at": "2026-03-23T10:00:00Z",
    "created_by": "user@example.com"
  },
  "trace_id": "abc-123-def",
  "timestamp": "2026-03-23T12:00:00Z"
}
```

**Error Responses**:
- `404`: Prompt template not found
- `400`: Invalid variable values (validation error)
- `503`: Service unavailable (Langfuse disconnected, may include fallback)

---

### Prompt Management

#### GET /prompts

List all prompt templates with pagination.

**Query Parameters**:
- `page` (integer, default: 1)
- `page_size` (integer, default: 20, max: 100)
- `tag` (string, optional): Filter by tag
- `search` (string, optional): Search in name/description

**Response** (200 OK):
```json
{
  "prompts": [
    {
      "template_id": "financial_analysis",
      "name": "Financial Analysis",
      "description": "Analyze financial data",
      "version": 3,
      "is_active": true,
      "tags": ["finance", "analysis"],
      "created_at": "2026-03-23T10:00:00Z",
      "updated_at": "2026-03-23T11:30:00Z",
      "created_by": "user@example.com"
    }
  ],
  "total": 42,
  "page": 1,
  "page_size": 20
}
```

---

#### GET /prompts/{template_id}

Get details of a specific prompt template.

**Path Parameters**:
- `template_id` (string): The prompt template identifier

**Query Parameters**:
- `version` (integer, optional): Specific version, default is active

**Response** (200 OK):
```json
{
  "template_id": "financial_analysis",
  "name": "Financial Analysis",
  "description": "Analyze financial data",
  "version": 3,
  "sections": [
    {
      "name": "角色",
      "content": "你是一个金融分析专家",
      "is_required": true,
      "order": 0
    },
    {
      "name": "任务",
      "content": "分析用户输入",
      "is_required": true,
      "order": 1
    },
    {
      "name": "约束",
      "content": "- 必须基于数据\n- 不允许编造",
      "is_required": true,
      "order": 2
    },
    {
      "name": "输出格式",
      "content": "JSON",
      "is_required": true,
      "order": 4
    }
  ],
  "variables": {
    "input": {
      "name": "input",
      "description": "User input to analyze",
      "type": "string",
      "is_required": true
    }
  },
  "tags": ["finance", "analysis"],
  "is_active": true,
  "is_published": true,
  "created_at": "2026-03-23T10:00:00Z",
  "updated_at": "2026-03-23T11:30:00Z",
  "created_by": "user@example.com"
}
```

---

#### POST /prompts

Create a new prompt template.

**Request Body**:
```json
{
  "template_id": "financial_analysis",
  "name": "Financial Analysis",
  "description": "Analyze financial data",
  "sections": [
    {
      "name": "角色",
      "content": "你是一个金融分析专家",
      "is_required": true,
      "order": 0
    }
  ],
  "variables": {
    "input": {
      "name": "input",
      "description": "User input to analyze",
      "type": "string",
      "is_required": true
    }
  },
  "tags": ["finance", "analysis"],
  "is_published": false
}
```

**Response** (201 Created):
```json
{
  "template_id": "financial_analysis",
  "version": 1,
  "is_active": false,
  "created_at": "2026-03-23T12:00:00Z",
  "trace_id": "abc-123-def"
}
```

**Error Responses**:
- `400`: Invalid request (validation error)
- `409`: Template ID already exists

---

#### PUT /prompts/{template_id}

Update an existing prompt template (creates new version).

**Path Parameters**:
- `template_id` (string): The prompt template identifier

**Request Body**:
```json
{
  "name": "Financial Analysis (Updated)",
  "description": "Updated description",
  "sections": [...],
  "variables": {...},
  "tags": ["finance", "analysis", "updated"],
  "change_description": "Added retrieved docs section support"
}
```

**Response** (200 OK):
```json
{
  "template_id": "financial_analysis",
  "version": 4,
  "previous_version": 3,
  "is_active": true,
  "updated_at": "2026-03-23T12:30:00Z",
  "trace_id": "abc-123-def"
}
```

**Error Responses**:
- `400`: Invalid request (validation error)
- `404`: Template not found

---

#### DELETE /prompts/{template_id}

Delete a prompt template (soft delete, archived).

**Path Parameters**:
- `template_id` (string): The prompt template identifier

**Response** (200 OK):
```json
{
  "template_id": "financial_analysis",
  "deleted": true,
  "trace_id": "abc-123-def"
}
```

---

### Version Management

#### GET /prompts/{template_id}/versions

Get version history for a prompt.

**Path Parameters**:
- `template_id` (string): The prompt template identifier

**Query Parameters**:
- `page` (integer, default: 1)
- `page_size` (integer, default: 20)

**Response** (200 OK):
```json
{
  "versions": [
    {
      "version": 4,
      "change_description": "Added retrieved docs section support",
      "created_at": "2026-03-23T12:30:00Z",
      "created_by": "user@example.com",
      "is_active": true
    },
    {
      "version": 3,
      "change_description": "Initial version",
      "created_at": "2026-03-23T10:00:00Z",
      "created_by": "user@example.com",
      "is_active": false
    }
  ],
  "total": 4,
  "page": 1,
  "page_size": 20
}
```

---

#### POST /prompts/{template_id}/rollback

Rollback to a specific previous version.

**Path Parameters**:
- `template_id` (string): The prompt template identifier

**Request Body**:
```json
{
  "target_version": 3,
  "reason": "Bug in version 4, rolling back"
}
```

**Response** (200 OK):
```json
{
  "template_id": "financial_analysis",
  "previous_version": 4,
  "new_version": 5,
  "rolled_back_to": 3,
  "note": "Version 5 is a copy of version 3",
  "trace_id": "abc-123-def"
}
```

---

### A/B Testing

#### POST /ab-tests

Create a new A/B test.

**Request Body**:
```json
{
  "template_id": "financial_analysis",
  "name": "Test prompt variations",
  "description": "Compare structured vs unstructured prompts",
  "variants": [
    {
      "variant_id": "variant_a",
      "template_version": 3,
      "traffic_percentage": 50,
      "is_control": true
    },
    {
      "variant_id": "variant_b",
      "template_version": 4,
      "traffic_percentage": 50,
      "is_control": false
    }
  ],
  "success_metric": "success_rate",
  "min_sample_size": 1000,
  "target_improvement": 0.05
}
```

**Response** (201 Created):
```json
{
  "test_id": "ab_test_123",
  "status": "running",
  "created_at": "2026-03-23T12:00:00Z",
  "trace_id": "abc-123-def"
}
```

---

#### GET /ab-tests

List all A/B tests.

**Query Parameters**:
- `status` (string, optional): Filter by status
- `template_id` (string, optional): Filter by template

**Response** (200 OK):
```json
{
  "tests": [
    {
      "test_id": "ab_test_123",
      "template_id": "financial_analysis",
      "name": "Test prompt variations",
      "status": "running",
      "variants": [
        {
          "variant_id": "variant_a",
          "traffic_percentage": 50,
          "impressions": 500
        },
        {
          "variant_id": "variant_b",
          "traffic_percentage": 50,
          "impressions": 500
        }
      ],
      "created_at": "2026-03-23T12:00:00Z"
    }
  ]
}
```

---

#### GET /ab-tests/{test_id}

Get detailed results for an A/B test.

**Path Parameters**:
- `test_id` (string): The A/B test identifier

**Response** (200 OK):
```json
{
  "test_id": "ab_test_123",
  "template_id": "financial_analysis",
  "name": "Test prompt variations",
  "status": "running",
  "variants": [
    {
      "variant_id": "variant_a",
      "template_version": 3,
      "is_control": true,
      "traffic_percentage": 50,
      "impressions": 1000,
      "successes": 850,
      "success_rate": 0.85,
      "avg_latency_ms": 75.5,
      "metrics": {
        "p_value": 0.02,
        "confidence_interval": [0.82, 0.88],
        "is_significant": true
      }
    },
    {
      "variant_id": "variant_b",
      "template_version": 4,
      "is_control": false,
      "traffic_percentage": 50,
      "impressions": 1000,
      "successes": 890,
      "success_rate": 0.89,
      "avg_latency_ms": 78.2,
      "metrics": {
        "p_value": 0.02,
        "confidence_interval": [0.86, 0.92],
        "is_significant": true,
        "improvement_over_control": 0.047
      }
    }
  ],
  "recommendation": {
    "winner": "variant_b",
    "confidence": "high",
    "reason": "Significant improvement in success rate (4.7%)"
  },
  "created_at": "2026-03-23T12:00:00Z",
  "started_at": "2026-03-23T12:01:00Z"
}
```

---

#### POST /ab-tests/{test_id}/winner

Select a winner and end the A/B test.

**Path Parameters**:
- `test_id` (string): The A/B test identifier

**Request Body**:
```json
{
  "variant_id": "variant_b",
  "reason": "Clear winner with 4.7% improvement"
}
```

**Response** (200 OK):
```json
{
  "test_id": "ab_test_123",
  "winner_variant_id": "variant_b",
  "status": "completed",
  "new_prompt_version": 5,
  "trace_id": "abc-123-def"
}
```

---

#### POST /ab-tests/{test_id}/pause

Pause an A/B test.

**Path Parameters**:
- `test_id` (string): The A/B test identifier

**Response** (200 OK):
```json
{
  "test_id": "ab_test_123",
  "status": "paused",
  "trace_id": "abc-123-def"
}
```

---

#### POST /ab-tests/{test_id}/resume

Resume a paused A/B test.

**Path Parameters**:
- `test_id` (string): The A/B test identifier

**Response** (200 OK):
```json
{
  "test_id": "ab_test_123",
  "status": "running",
  "trace_id": "abc-123-def"
}
```

---

### Analytics

#### GET /analytics/prompts/{template_id}

Get analytics for a specific prompt.

**Path Parameters**:
- `template_id` (string): The prompt template identifier

**Query Parameters**:
- `start_date` (ISO-8601, optional): Start of date range
- `end_date` (ISO-8601, optional): End of date range
- `include_ab_test_results` (boolean, default: true)

**Response** (200 OK):
```json
{
  "template_id": "financial_analysis",
  "period": {
    "start": "2026-03-20T00:00:00Z",
    "end": "2026-03-23T23:59:59Z"
  },
  "summary": {
    "total_retrievals": 15000,
    "unique_users": 3200,
    "error_rate": 0.02,
    "avg_latency_ms": 82.3,
    "latency_p50": 78.0,
    "latency_p95": 95.0,
    "latency_p99": 120.0
  },
  "versions": [
    {
      "version": 3,
      "retrievals": 10000,
      "error_rate": 0.015,
      "avg_latency_ms": 80.0
    },
    {
      "version": 4,
      "retrievals": 5000,
      "error_rate": 0.03,
      "avg_latency_ms": 85.0
    }
  ],
  "ab_tests": [
    {
      "test_id": "ab_test_123",
      "variants": [
        {
          "variant_id": "variant_a",
          "success_rate": 0.85,
          "impressions": 1000
        },
        {
          "variant_id": "variant_b",
          "success_rate": 0.89,
          "impressions": 1000
        }
      ]
    }
  ],
  "top_errors": [
    {
      "error": "VARIABLE_VALIDATION_FAILED",
      "count": 150,
      "percentage": 0.5
    }
  ],
  "trace_id": "abc-123-def"
}
```

---

#### GET /analytics/traces

Search and filter trace records.

**Query Parameters**:
- `template_id` (string, optional): Filter by template
- `variant_id` (string, optional): Filter by A/B test variant
- `start_date` (ISO-8601, required)
- `end_date` (ISO-8601, required)
- `success` (boolean, optional): Filter by success status
- `page` (integer, default: 1)
- `page_size` (integer, default: 50)

**Response** (200 OK):
```json
{
  "traces": [
    {
      "trace_id": "trace_123",
      "template_id": "financial_analysis",
      "template_version": 3,
      "variant_id": "variant_a",
      "input_variables": {"input": "Analyze AAPL"},
      "success": true,
      "latency_ms": 78,
      "timestamp": "2026-03-23T12:00:00Z"
    }
  ],
  "total": 500,
  "page": 1,
  "page_size": 50
}
```

---

## Error Codes

| Code | HTTP | Description |
|------|------|-------------|
| `PROMPT_NOT_FOUND` | 404 | Prompt template does not exist |
| `PROMPT_VERSION_NOT_FOUND` | 404 | Specific version not found |
| `INVALID_TEMPLATE_ID` | 400 | Template ID format invalid |
| `INVALID_VARIABLES` | 400 | Variable values fail validation |
| `MISSING_REQUIRED_VARIABLE` | 400 | Required variable not provided |
| `AB_TEST_NOT_FOUND` | 404 | A/B test does not exist |
| `AB_TEST_ALREADY_RUNNING` | 409 | Cannot modify running test |
| `INSUFFICIENT_SAMPLE_SIZE` | 400 | Not enough data for conclusion |
| `SERVICE_UNAVAILABLE` | 503 | Langfuse disconnected |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |

---

## Rate Limits

| Endpoint | Limit | Window |
|----------|-------|--------|
| POST /prompts/{id}/retrieve | 1000/minute | Per API key |
| GET/POST/PUT /prompts | 100/minute | Per API key |
| GET /analytics/* | 60/minute | Per API key |

---

**Document Version**: 1.0 | **Last Updated**: 2026-03-23
