# API Contract: Query Quality Enhancement

**Feature**: 006-query-quality-enhancement
**Version**: 1.0.0
**Date**: 2026-04-09

## Overview

The Query Quality Enhancement is integrated into the existing QA Pipeline API (`/qa/query`). It operates as a pre-processing capability that analyzes query dimensions and prompts for missing information before retrieval.

## API Endpoints

### Existing Endpoint (Extended)

The query quality enhancement extends the existing QA Pipeline endpoint behavior.

```
POST /qa/query
```

#### Request

**Content-Type**: `application/json`

```json
{
  "query": "string (1-1000 characters, required)",
  "context": {
    "company_id": "string (required, format: NXXXXXX)",
    "file_type": "string (optional, PublicDocDispatch|PublicDocReceive)",
    "doc_date": "string (optional, YYYY-MM-DD)"
  },
  "options": {
    "enable_query_rewrite": "boolean (default: true)",
    "enable_hallucination_check": "boolean (default: true)",
    "enable_query_quality": "boolean (default: true, NEW)",
    "top_k": "integer (1-50, default: 10)",
    "stream": "boolean (default: false)"
  }
}
```

#### Response

**Success Response** (200 OK)

When query quality analysis is enabled and dimensions are missing:

```json
{
  "action": "prompt",
  "message": "请问您需要查找哪一年的安全管理通知？",
  "missing_dimensions": ["year"],
  "quality_score": 0.5,
  "session_id": "trace-uuid-v4",
  "feedback": "您的查询缺少以下维度：[年份]，建议添加年份以获得更精确的结果"
}
```

When dimensions are complete and search proceeds:

```json
{
  "action": "complete",
  "answer": "生成的回答内容...",
  "sources": [
    {
      "chunk_id": "chunk_123",
      "document_id": "doc_456",
      "document_name": "关于印发《安全生产管理办法》的通知",
      "dataset_id": "N000002_PublicDocDispatch",
      "dataset_name": "发文知识库",
      "score": 0.95,
      "content_preview": "根据《安全生产管理办法》..."
    }
  ],
  "enhanced_query": "2024年安全生产相关通知",
  "quality_feedback": "您的查询非常完整，包含了所有关键维度",
  "hallucination_status": {
    "checked": true,
    "passed": true,
    "confidence": 0.85
  },
  "metadata": {
    "trace_id": "trace-uuid-v4",
    "query_rewritten": true,
    "dimensions_provided": ["year", "doc_type", "subject"],
    "quality_score": 1.0,
    "timing": {
      "total_ms": 1234.5,
      "quality_analysis_ms": 234.5,
      "retrieve_ms": 456.7,
      "generate_ms": 543.3
    }
  }
}
```

**Error Response** (400 Bad Request)

```json
{
  "error": "validation_error",
  "message": "查询不能为空",
  "detail": "query field is required and must be 1-1000 characters",
  "trace_id": "trace-uuid-v4"
}
```

**Error Response** (429 Too Many Requests - Turn Limit)

```json
{
  "error": "turn_limit_exceeded",
  "message": "对话轮次已达上限（10轮），请开始新的对话",
  "detail": "Maximum 10 conversation turns per session exceeded",
  "trace_id": "trace-uuid-v4"
}
```

**Error Response** (408 Request Timeout - Session Expired)

```json
{
  "error": "session_expired",
  "message": "会话已超时（15分钟），请重新开始",
  "detail": "Session expired due to inactivity",
  "trace_id": "trace-uuid-v4"
}
```

## Query Flow

### Flow 1: Missing Dimensions (Multi-Turn)

```
Client: POST /qa/query
        {"query": "安全通知", "context": {"company_id": "N000002"}}

Server: 200 OK
        {
          "action": "prompt",
          "message": "请问您需要查找哪一年的安全通知？",
          "missing_dimensions": ["year"]
        }

Client: POST /qa/query
        {"query": "2024年的", "context": {"company_id": "N000002"}}
        (with same session_id from previous response)

Server: 200 OK
        {
          "action": "complete",
          "answer": "根据搜索结果...",
          "sources": [...]
        }
```

### Flow 2: Complete Query (Single Turn)

```
Client: POST /qa/query
        {"query": "2024年安全生产管理办法通知", "context": {"company_id": "N000002"}}

Server: 200 OK
        {
          "action": "complete",
          "answer": "根据搜索结果...",
          "sources": [...],
          "quality_feedback": "您的查询非常完整"
        }
```

### Flow 3: Dual Knowledge Base Search

```
Client: POST /qa/query
        {"query": "关于工会建设的文件", "context": {"company_id": "N000002"}}
        // Note: file_type NOT specified

Server: 200 OK
        {
          "action": "complete",
          "answer": "搜索了发文和收文两个知识库...",
          "sources": [
            {"dataset_id": "N000002_PublicDocDispatch", ...},
            {"dataset_id": "N000002_PublicDocReceive", ...}
          ],
          "metadata": {
            "search_mode": "dual",
            "collections_searched": ["N000002_PublicDocDispatch", "N000002_PublicDocReceive"]
          }
        }
```

## Data Contracts

### Dimension Type Enum

```typescript
enum DimensionType {
  COMPANY_ID = "company_id",
  FILE_TYPE = "file_type",
  DOC_TYPE = "doc_type",
  ORGANIZATION = "organization",
  YEAR = "year",
  DOC_NUMBER = "doc_number",
  SUBJECT = "subject"
}
```

### Session State Schema (Redis)

```typescript
interface SessionState {
  trace_id: string;
  company_id: string;
  file_type?: string;
  turn_count: number;
  created_at: string;  // ISO 8601
  last_activity: string;  // ISO 8601
  established_dimensions: Record<DimensionType, string>;
  pending_dimensions: DimensionType[];
  query_history: string[];
  response_history: string[];
  status: "active" | "complete" | "expired";
}
```

## Performance Contracts

| Metric | Target | Measurement |
|--------|--------|-------------|
| Dimension analysis latency | < 500ms p95 | Time from QueryQualityCapability.execute() to LLM response |
| Session state read/write | < 10ms p95 | Redis GET/SET operations |
| End-to-end query processing | < 3000ms p95 | From API request to final response (including prompts) |
| Session TTL | 900 seconds | Redis key expiration |

## Compatibility

### Backward Compatibility

- Existing clients can ignore `action` field and treat non-prompt responses as normal QA results
- `enable_query_quality` option defaults to `true` but can be set to `false` to skip dimension analysis
- Response format extended (not modified) - existing fields preserved

### Versioning

- API version: 1.0
- Breaking changes will be reflected in minor version increments (1.1, 1.2, etc.)
- Major version increments (2.0) reserved for incompatible changes

## Error Codes

| Code | Description | HTTP Status |
|------|-------------|-------------|
| `validation_error` | Invalid request parameters | 400 |
| `session_expired` | Session inactive for 15+ minutes | 408 |
| `turn_limit_exceeded` | More than 10 conversation turns | 429 |
| `kb_unavailable` | Knowledge base not accessible | 503 |
| `llm_error` | LLM processing failed | 500 |

## Testing

### Contract Tests

See: `tests/contract/test_query_quality_api.py`

### Example Test Cases

1. **Missing Year Dimension**: Query "关于安全的通知" should prompt for year
2. **Complete Query**: Query "2024年安全生产管理办法通知" should proceed to retrieval
3. **Session Expiry**: Session inactive > 15 minutes should return error
4. **Turn Limit**: 10+ turns should return turn_limit_exceeded error
5. **Dual KB Search**: Query without file_type should search both collections
