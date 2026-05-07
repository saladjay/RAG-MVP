# API Contract: Conversational Query Enhancement

**Feature**: 007-conversational-query
**Version**: 1.0.0
**Date**: 2026-04-10

## Overview

This document defines the API contract for the Conversational Query Enhancement module. The capability integrates with the existing QA Pipeline endpoint, extending the request/response schemas to support multi-turn conversations.

## Endpoint

The conversational query capability is exposed through the existing QA query endpoint:

```
POST /qa/query
```

## Request Schema

### HTTP Headers

```typescript
interface RequestHeaders {
  "Content-Type": "application/json";
  "X-Trace-ID": string;  // UUID for trace correlation
  "X-Session-ID"?: string;  // Optional: Session ID for multi-turn conversations
}
```

### Request Body

```typescript
interface ConversationalQueryRequest {
  query: string;  // User's natural language query (1-500 chars)
  context: {
    company_id: string;  // Company identifier (e.g., "N000002")
    file_type?: "PublicDocDispatch" | "PublicDocReceive";  // Optional file category
  };
  options?: {
    enable_conversational_query?: boolean;  // Enable conversational query (default: true)
    enable_colloquial_mapping?: boolean;  // Map colloquial terms (default: true)
    enable_query_expansion?: boolean;  // Expand queries (default: true)
    max_turns?: number;  // Max conversation turns (default: 10, min: 1, max: 20)
  };
}
```

## Response Schema

### Response Actions

The response includes an `action` field that determines how the client should proceed:

1. **"proceed"**: All required information gathered, proceed with retrieval
2. **"prompt"**: Missing information, prompt user for input
3. **"complete"**: Search completed, return results

### Response Body (action: "prompt")

```typescript
interface PromptResponse {
  action: "prompt";
  message: string;  // User-friendly prompt for missing information
  missing_slots: string[];  // Slots that need user input
  belief_state: {
    trace_id: string;
    turn_count: number;
    accumulated_slots: Record<string, any>;
  };
  extracted_elements: {
    query_type: "meta_info" | "business_query" | "unknown";
    domain?: string;
    confidence: "high" | "medium" | "low";
  };
}
```

### Response Body (action: "proceed" | "complete")

```typescript
interface ProceedResponse {
  action: "proceed" | "complete";

  // Query generation results
  query_generation: {
    q1: string;  // First question variation
    q2: string;  // Second question variation
    q3: string;  // Third question variation
    must_include: string[];  // 3-6 core terms
    keywords: string[];  // 5-10 expanded keywords
    domain_context: string;  // Query type and domain
  };

  // Retrieved documents (for action: "complete")
  answer?: string;
  sources?: Array<{
    chunk_id: string;
    document_id: string;
    document_name: string;
    dataset_id: string;
    dataset_name: string;
    score: number;
    content_preview: string;
  }>;

  // Session info
  belief_state: {
    trace_id: string;
    turn_count: number;
    accumulated_slots: Record<string, any>;
  };

  // Extracted elements
  extracted_elements: {
    query_type: "meta_info" | "business_query" | "unknown";
    domain?: string;
    confidence: "high" | "medium" | "low";
    slots: {
      // Temporal
      year?: number;
      date?: string;
      time_range?: string;

      // Spatial
      organization?: string;
      city?: string;

      // Document
      doc_type?: string;
      meeting_type?: string;

      // Content
      topic_keywords: string[];
    };
  };

  // Applied mappings
  applied_mappings: Record<string, string>;  // colloquial → formal

  // Quality feedback
  quality_feedback?: string;
}
```

## Example Interactions

### Example 1: Initial Query with Missing Information

**Request**:
```json
{
  "query": "我想找关于安全的规定",
  "context": {
    "company_id": "N000002"
  }
}
```

**Response**:
```json
{
  "action": "prompt",
  "message": "请问您需要查找哪一年的安全规定？",
  "missing_slots": ["year"],
  "belief_state": {
    "trace_id": "trace-uuid-v4",
    "turn_count": 1,
    "accumulated_slots": {
      "domain": "safety",
      "topic": "安全规定"
    }
  },
  "extracted_elements": {
    "query_type": "business_query",
    "domain": "safety",
    "confidence": "medium"
  }
}
```

### Example 2: Follow-up with Year Information

**Request** (with session continuation):
```json
{
  "query": "2024年的",
  "context": {
    "company_id": "N000002"
  }
}
```

**Headers**: `X-Session-ID: trace-uuid-v4`

**Response**:
```json
{
  "action": "proceed",
  "query_generation": {
    "q1": "2024年安全生产相关规定有哪些？",
    "q2": "2024年安全生产制度包括哪些内容？",
    "q3": "2024年关于安全生产的规定文件",
    "must_include": ["2024", "安全生产", "规定"],
    "keywords": ["2024", "安全生产", "规定", "制度", "办法", "细则", "管理"],
    "domain_context": "business_query:safety"
  },
  "belief_state": {
    "trace_id": "trace-uuid-v4",
    "turn_count": 2,
    "accumulated_slots": {
      "year": 2024,
      "domain": "safety",
      "topic": "安全生产"
    }
  },
  "extracted_elements": {
    "query_type": "business_query",
    "domain": "safety",
    "confidence": "high",
    "slots": {
      "year": 2024,
      "topic_keywords": ["安全生产", "规定"]
    }
  },
  "applied_mappings": {}
}
```

### Example 3: Colloquial Expression Mapping

**Request**:
```json
{
  "query": "有没有关于防火的规定",
  "context": {
    "company_id": "N000002"
  }
}
```

**Response**:
```json
{
  "action": "proceed",
  "query_generation": {
    "q1": "消防管理相关规定有哪些？",
    "q2": "消防安全制度包括什么内容？",
    "q3": "关于消防的规定和标准",
    "must_include": ["消防", "规定"],
    "keywords": ["消防", "防火", "消防安全", "规定", "制度", "标准", "管理"],
    "domain_context": "business_query:safety"
  },
  "extracted_elements": {
    "query_type": "business_query",
    "domain": "safety",
    "confidence": "high",
    "slots": {
      "topic_keywords": ["防火", "规定"]
    }
  },
  "applied_mappings": {
    "防火": "消防"
  }
}
```

### Example 4: Meeting Query with 2025 Updates

**Request**:
```json
{
  "query": "职工代表大会会议纪要",
  "context": {
    "company_id": "N000002"
  }
}
```

**Response**:
```json
{
  "action": "proceed",
  "query_generation": {
    "q1": "职工代表大会会议纪要有哪些内容？",
    "q2": "职工代表大会会议纪要包含哪些决议？",
    "q3": "关于职工代表大会的会议纪要文件",
    "must_include": ["职工代表大会", "会议纪要"],
    "keywords": ["职工代表大会", "职代会", "会议纪要", "会议记录", "决议", "工会"],
    "domain_context": "business_query:union"
  },
  "extracted_elements": {
    "query_type": "business_query",
    "domain": "union",
    "confidence": "high",
    "slots": {
      "doc_type": "会议纪要",
      "meeting_type": "职工代表大会"
    }
  },
  "applied_mappings": {
    "职代会": "职工代表大会"
  }
}
```

## Error Responses

### Error Schema

```typescript
interface ErrorResponse {
  error: string;
  message: string;
  trace_id: string;
  details?: {
    field?: string;
    constraint?: string;
    value?: any;
  };
}
```

### Common Errors

| HTTP Status | Error Type | Description |
|-------------|------------|-------------|
| 400 | `invalid_query` | Query is empty or exceeds maximum length |
| 400 | `invalid_context` | Missing or invalid company_id |
| 400 | `invalid_options` | Invalid option values |
| 429 | `turn_limit_exceeded` | Maximum conversation turns reached |
| 500 | `llm_error` | LLM service error during slot extraction |
| 500 | `redis_error` | Redis connection error |

### Error Example

```json
{
  "error": "turn_limit_exceeded",
  "message": "Maximum conversation turns (10) reached. Please start a new session.",
  "trace_id": "trace-uuid-v4"
}
```

## HTTP Status Codes

| Status | Description |
|--------|-------------|
| 200 | Success |
| 400 | Bad Request (invalid input) |
| 429 | Too Many Requests (turn limit exceeded) |
| 500 | Internal Server Error |
| 503 | Service Unavailable (LLM or Redis unavailable) |

## Performance Expectations

| Metric | Target |
|--------|--------|
| Initial query processing | < 1500ms p95 |
| Follow-up query processing | < 1000ms p95 |
| Slot extraction | < 800ms p95 |
| Query generation | < 1000ms p95 |
| Total (including retrieval) | < 3000ms p95 |

## Versioning

API versioning follows the SemVer specification. Breaking changes will result in a minor version increment, while backward-compatible additions will result in a patch version increment.
