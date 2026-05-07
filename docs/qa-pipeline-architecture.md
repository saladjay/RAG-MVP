# RAG QA Pipeline Architecture

**Feature**: 005 - RAG QA Pipeline
**Status**: Implemented
**Last Updated**: 2026-04-02

## Overview

The RAG QA Pipeline is a complete question-answering system that orchestrates query rewriting, external knowledge base retrieval, LLM-based answer generation, and hallucination detection. It extends the existing RAG Service (Spec 001) with production-ready QA capabilities.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API Layer                                      │
│  ┌─────────────────┐    ┌─────────────────┐                              │
│  │ POST /qa/query  │    │ POST /qa/query/ │                              │
│  │   (Non-Stream)  │    │     stream      │                              │
│  └────────┬────────┘    └────────┬────────┘                              │
└───────────┼───────────────────────┼───────────────────────────────────────┘
            │                       │
            ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         QA Pipeline Capability                               │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │  1. Query Rewrite (Optional)                                          │ │
│  │     └──> QueryRewriteCapability                                       │ │
│  │         └──> LiteLLM Gateway (LLM-based query optimization)             │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │  2. External KB Retrieval (Required)                                   │ │
│  │     └──> ExternalKBQueryCapability                                     │ │
│  │         └──> ExternalKBClient (HTTP API)                               │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │  3. Answer Generation (Required)                                      │ │
│  │     └──> ModelInferenceCapability                                     │ │
│  │         └──> LiteLLM Gateway (Multi-provider LLM)                     │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │  4. Hallucination Detection (Optional)                                │ │
│  │     └──> HallucinationDetectionCapability                             │ │
│  │         └──> Sentence-Transformers (Similarity-based)                 │ │
│  │         └──> Regeneration with strict prompt if failed                │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      Default Fallback Service                               │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │  Predefined messages for:                                            │ │
│  │  - KB Unavailable                                                     │ │
│  │  - KB Empty                                                          │ │
│  │  - KB Error                                                          │ │
│  │  - Hallucination Failed                                              │ │
│  │  - Regeneration Failed                                               │ │
│  │  - Timeout                                                           │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Component Interactions

### 1. Query Flow (Non-Streaming)

```
Client Request (POST /qa/query)
    │
    ├─> Validate request (query, context, options)
    │
    ├─> Extract trace_id (from X-Trace-ID header or generate new)
    │
    ├─> QAPipelineCapability.execute()
    │   │
    │   ├─> [Optional] QueryRewriteCapability.execute()
    │   │   │   └─> LiteLLM Gateway.acomplete()
    │   │   │       └─> Returns: rewritten_query, was_rewritten, rewrite_reason
    │   │
    │   ├─> ExternalKBQueryCapability.execute()
    │   │   │   └─> ExternalKBClient.query()
    │   │   │       └─> Returns: chunks (with scores and metadata)
    │   │
    │   ├─> [If chunks empty] DefaultFallbackService.get_fallback(KB_EMPTY)
    │   │   │   └─> Returns: fallback message
    │   │   │   └─> Early return
    │   │
    │   ├─> ModelInferenceCapability.execute()
    │   │   │   └─> LiteLLM Gateway.acomplete()
    │   │   │       └─> Returns: generated_answer
    │   │
    │   ├─> [Optional] HallucinationDetectionCapability.execute()
    │   │   │   └─> Sentence-Transformers.encode() [answer + chunks]
    │   │   │   └─> Cosine similarity calculation
    │   │   │   └─> If failed: regenerate with strict prompt
    │   │   │   └─> Returns: checked, passed, confidence, flagged_claims
    │   │
    │   └─> Assemble response
    │       └─> QAQueryResponse (answer, sources, hallucination_status, metadata)
    │
    └─> Return JSON response to client
```

### 2. Streaming Flow

```
Client Request (POST /qa/query/stream)
    │
    ├─> Validate request
    │
    ├─> QAPipelineCapability.stream_execute()
    │   │
    │   ├─> [Optional] QueryRewriteCapability.execute()
    │   │
    │   ├─> ExternalKBQueryCapability.execute()
    │   │
    │   └─> ModelInferenceCapability.stream_execute()
    │       │
    │       └─> LiteLLM Gateway.astream_complete()
    │           │
    │           └─> Yield tokens as SSE (Server-Sent Events)
    │
    └─> Return StreamingResponse with headers:
        - X-Hallucination-Checked: pending/passed/failed/skipped
        - X-Trace-ID: <trace_id>
```

## Data Flow

### Request Processing

1. **API Layer** (`qa_routes.py`)
   - Validates incoming request
   - Extracts trace_id from headers
   - Creates `QAPipelineInput`

2. **Pipeline Orchestration** (`qa_pipeline.py`)
   - Calls capabilities in sequence
   - Handles errors and fallbacks
   - Collects timing metrics
   - Propagates trace_id throughout

3. **Capability Layer**
   - `QueryRewriteCapability`: Improves query specificity
   - `ExternalKBQueryCapability`: Retrieves relevant documents
   - `ModelInferenceCapability`: Generates answers
   - `HallucinationDetectionCapability`: Verifies factual accuracy

4. **Service Layer**
   - `DefaultFallbackService`: Provides error messages
   - `LiteLLMGateway`: Multi-provider LLM access
   - `ExternalKBClient`: HTTP client for KB API

### Response Assembly

The final response includes:

- **answer**: Generated text response
- **sources**: List of retrieved document chunks with:
  - chunk_id: Unique chunk identifier
  - document_id: Source document ID
  - document_name: Source document name
  - dataset_id: Dataset identifier
  - dataset_name: Dataset name
  - score: Retrieval relevance score (0-1)
  - content_preview: First 200 characters of chunk

- **hallucination_status**: Verification result with:
  - checked: Whether verification was performed
  - passed: Whether verification passed
  - confidence: Similarity confidence score (0-1)
  - flagged_claims: Claims that couldn't be verified
  - warning_message: User-facing warning if verification failed

- **metadata**: Execution metadata with:
  - trace_id: Request trace ID
  - query_rewritten: Whether query was rewritten
  - original_query: Original user query
  - rewritten_query: Rewritten query (if applicable)
  - rewrite_reason: Reason for rewrite (if applicable)
  - retrieval_count: Number of chunks retrieved
  - generation_model: Model used for generation
  - timing: Timing breakdown (rewrite_ms, retrieve_ms, generate_ms, verify_ms, total_ms)

## Error Handling

### Fallback Scenarios

| Scenario | Component | Fallback Action |
|----------|-----------|-----------------|
| Query rewrite fails | QueryRewriteCapability | Use original query |
| KB unavailable | ExternalKBClient | Return KB_UNAVAILABLE fallback |
| KB returns empty | ExternalKBClient | Return KB_EMPTY fallback |
| KB returns error | ExternalKBClient | Return KB_ERROR fallback |
| Generation fails | ModelInferenceCapability | Raise GenerationError |
| Hallucination check fails | HallucinationDetectionCapability | Mark as not checked |
| All chunks fail hallucination | QAPipelineCapability | Return with warning |

### Error Response Format

```json
{
  "detail": {
    "error": "error_code",
    "message": "Human-readable error message",
    "trace_id": "trace-id-for-debugging"
  }
}
```

## Performance Considerations

### Latency Breakdown

| Stage | Typical Latency | Notes |
|-------|----------------|-------|
| Query Rewrite | 500-2000ms | LLM API call |
| KB Retrieval | 200-1000ms | HTTP API call |
| Answer Generation | 1000-5000ms | LLM API call |
| Hallucination Check | 100-500ms | Embedding + similarity |
| **Total (Non-Streaming)** | **< 10000ms** | 95th percentile target |

### Optimization Strategies

1. **Query Caching**: Cache rewritten queries for common patterns
2. **Connection Pooling**: Reuse HTTP connections to external KB
3. **Async Processing**: Run all I/O operations asynchronously
4. **Streaming**: For long responses, use streaming endpoint
5. **Batch Processing**: Process multiple queries concurrently when possible

## Security Considerations

1. **Input Validation**: All queries validated for length and format
2. **Company ID Format**: Enforced pattern (N + digits)
3. **Trace ID Propagation**: All requests traceable
4. **Rate Limiting**: Prepared for future implementation
5. **Audit Logging**: All QA operations logged with trace_id

## Monitoring & Observability

### Logged Events

- Query received (with trace_id)
- Query rewrite (original → rewritten, reason)
- KB retrieval (chunk count, timing)
- Answer generation (model, tokens, timing)
- Hallucination check (confidence, threshold, passed/failed)
- Regeneration (attempt number, reason)
- Fallback usage (error_type, message)

### Metrics

- Request latency (p50, p95, p99)
- Query rewrite success rate
- KB retrieval success rate
- Answer generation success rate
- Hallucination check pass rate
- Regeneration rate
- Fallback usage rate

## Extension Points

The architecture supports future extensions:

1. **New Retrieval Sources**: Implement new capability following `ExternalKBQueryCapability` pattern
2. **Alternative LLMs**: Add new models via LiteLLM configuration
3. **Custom Prompts**: Modify prompts in `qa_prompts.yaml` or Langfuse
4. **Additional Verification**: Add new verification capabilities
5. **Caching Layer**: Add caching capability for performance
6. **Multi-tenancy**: Extend context for tenant-specific customization

## Dependencies

### Internal Components (from Spec 001)

- `ExternalKBClient`: HTTP client for external KB
- `LiteLLMGateway`: Multi-provider LLM gateway
- `ModelInferenceCapability`: LLM inference wrapper
- `LangfuseClient`: Observability integration

### External Dependencies

- **LiteLLM**: LLM model gateway
- **Sentence-Transformers**: Embedding models for similarity
- **External KB API**: Document retrieval service
- **Langfuse**: Observability platform (optional)

## File Structure

```
src/rag_service/
├── api/
│   ├── qa_routes.py          # QA API endpoints
│   └── qa_schemas.py         # Request/response models
├── capabilities/
│   ├── qa_pipeline.py        # Main orchestration
│   ├── query_rewrite.py      # Query rewriting
│   ├── hallucination_detection.py  # Verification
│   ├── external_kb_query.py  # KB retrieval (from 001)
│   └── model_inference.py    # LLM inference (from 001)
├── services/
│   └── default_fallback.py   # Fallback messages
├── inference/
│   └── gateway.py            # LiteLLM gateway (from 001)
├── clients/
│   └── external_kb_client.py # KB HTTP client (from 001)
└── config.py                 # Configuration

tests/
├── contract/
│   └── test_qa_api.py        # API contract tests
├── integration/
│   ├── test_qa_pipeline_e2e.py  # End-to-end tests
│   └── test_qa_streaming_e2e.py # Streaming tests
└── unit/
    ├── test_query_rewrite.py      # Query rewrite tests
    └── test_hallucination_detection.py  # Verification tests

config/
└── qa_fallback.yaml           # Fallback message templates
```
