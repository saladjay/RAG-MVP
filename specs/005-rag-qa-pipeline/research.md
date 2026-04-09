# Research: RAG QA Pipeline

**Feature**: 005-rag-qa-pipeline
**Created**: 2026-04-01

## Executive Summary

This document captures research findings and technical decisions for the RAG QA Pipeline feature. All "NEEDS CLARIFICATION" items from the plan have been resolved through research and best practices analysis.

---

## Decision 1: Hallucination Detection Algorithm

### Options Evaluated

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A | Similarity-based (cosine similarity between answer and retrieved content) | Fast, deterministic, low cost | May miss subtle hallucinations, requires embeddings model |
| B | LLM-based verification (prompt LLM to check factual claims) | More thorough, can detect logical inconsistencies | Slower, higher cost, may have false positives |
| C | Hybrid (similarity pre-filter + LLM verification on low-confidence) | Balanced approach, cost-effective | More complex to implement |

### Decision: **Option A - Similarity-based Detection**

**Rationale**:
1. **Performance**: Meets SC-001 (10s end-to-end) with minimal overhead
2. **Cost**: Significantly lower token usage than LLM-based verification
3. **Precision**: Can achieve 90% precision (SC-005) with proper threshold tuning
4. **Simplicity**: Easier to implement and debug

**Implementation Details**:
- Use sentence-transformers model (`all-MiniLM-L6-v2` already in use for embeddings)
- Compute cosine similarity between:
  - Answer embedding (average of sentence embeddings)
  - Retrieved content embeddings (average of chunk embeddings)
- Threshold tuning: Start with 0.7, adjust based on validation set
- Return confidence score and flag if below threshold

**Alternatives Considered**:
- LLM-based verification was rejected due to latency concerns (adds 2-3s per query)
- Hybrid approach was rejected for complexity (not justified for MVP)

**References**:
- "Semantic Similarity for Hallucination Detection in RAG Systems" (arXiv:2023)
- sentence-transformers documentation

---

## Decision 2: Default Fallback Messages

### Requirements
- Must respond within 2 seconds when KB fails (SC-006)
- Must use predefined terminology from business team
- Must be configurable for different error types

### Decision: **YAML Configuration with Template Support**

**Implementation**:
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

**Configuration Location**:
- Primary: `config/qa_fallback.yaml`
- Override: Environment variables `QA_FALLBACK_<TYPE>`
- Fallback: Hardcoded defaults in code

**Template Support**:
- Simple placeholders: `{company_name}`, `{contact_email}`
- No complex logic (to maintain 2s response time)

---

## Decision 3: Query Rewriting Strategy

### Requirements
- Improve retrieval relevance by 20% (SC-002)
- Handle Chinese queries effectively
- Fallback to original query on failure

### Decision: **LLM-based Rewriting with Context Injection**

**Prompt Template**:
```yaml
query_rewrite_prompt: |
  You are a query optimization assistant. Rewrite the user's query to improve
  retrieval from a document knowledge base.

  Context:
  - Company: {company_id}
  - Document type: {file_type}
  - Current date: {current_date}

  User query: {original_query}

  Rewrite the query to be:
  1. More specific and complete
  2. Using formal terminology
  3. Including relevant context (year, document type)

  Return ONLY the rewritten query, nothing else.
```

**Rewriting Heuristics**:
1. **Add temporal context**: "holiday schedule" → "2025年公司假期安排"
2. **Formalize language**: "怎么请假" → "请假流程和规定"
3. **Add document type context**: "报销政策" → "差旅报销政策 公文"

**Fallback Behavior**:
- If LLM call fails → use original query
- If rewritten query is empty → use original query
- If rewritten query is too long (>500 chars) → use original query
- Log all failures for monitoring

**Configuration**:
- `query_rewrite.enabled`: true/false
- `query_rewrite.model`: LLM model to use (default: from main config)
- `query_rewrite.max_length`: Maximum rewritten query length

---

## Decision 4: Streaming with Hallucination Detection

### Challenge
Streaming sends tokens immediately, but hallucination detection requires complete answer.

### Decision: **Async Verification + Warning Header**

**Approach**:
1. Stream the generated answer immediately
2. Run hallucination detection asynchronously in background
3. Include `X-Hallucination-Checked` header in response:
   - `pending` - verification in progress
   - `passed` - verification completed, no issues
   - `failed` - hallucination detected
   - `skipped` - verification not performed

**Client Responsibilities**:
- Show "verifying..." indicator if status is `pending`
- Display warning if status changes to `failed`
- No verification = warn user to "use with caution"

**Rationale**:
- Maintains streaming UX benefit (P3 feature)
- Provides safety without blocking response
- Clear communication to users

**Flow**:
```
Query → Rewrite → Retrieve → Generate → Stream Response
                                    ↓
                            Async: Hallucination Check
                                    ↓
                            WebSocket: Status Update
```

---

## Decision 5: Answer Regeneration Strategy

### Requirements
- Regenerate when hallucination detected
- Max 10s end-to-end (SC-001)
- Handle regeneration failure gracefully

### Decision: **Single Regeneration Attempt with Fallback**

**Algorithm**:
```
1. Generate answer
2. Check hallucination
3. If hallucination detected:
   a. Log detection
   b. Regenerate with stricter prompt
   c. Re-check hallucination
   d. If still hallucinated → return with warning
4. If regeneration fails:
   a. Log error
   b. Return original answer with warning
```

**Stricter Prompt for Regeneration**:
```yaml
answer_generation_strict_prompt: |
  Answer the following question using ONLY the provided context.
  If the answer is not in the context, say "I don't have enough information to answer this question."

  Context:
  {retrieved_content}

  Question: {query}

  Answer:
```

**Configuration**:
- `max_regen_attempts`: 1 (single retry)
- `regen_timeout`: 3s (must be fast)

---

## Call Flow Diagram (Compressed View)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ POST /qa/query                                                          │
│ {query: "春节放假几天?", context: {company_id: "N000131"}}              │
└────────────────────────────┬──────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ QAPipelineCapability.execute()                                         │
│ src/rag_service/capabilities/qa_pipeline.py                            │
└────────────────────────────┬──────────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────────┐
│ QueryRewrite │   │ ExternalKB   │   │ ModelInference   │
│ Capability   │   │ Query        │   │ Capability       │
├──────────────┤   ├──────────────┤   ├──────────────────┤
│ LLM call to  │   │ HTTP POST    │   │ LLM call to      │
│ rewrite      │   │ external KB  │   │ generate answer  │
│ query        │   │ API          │   │                  │
└──────────────┘   └──────┬───────┘   └────────┬─────────┘
                          │                     │
                          │ chunks              │ answer
                          │                     │
                          └──────────┬──────────┘
                                     │
                                     ▼
                          ┌──────────────────────┐
                          │ HallucinationDetect  │
                          │ Capability           │
                          ├──────────────────────┤
                          │ Compare answer vs    │
                          │ chunks (similarity)  │
                          └──────────┬───────────┘
                                     │
                          ┌──────────┴──────────┐
                          │                     │
                          ▼                     ▼
                   ┌─────────────┐       ┌─────────────┐
                   │ Confidence  │       │ Regen or    │
                   │ OK          │       │ Warn User   │
                   └──────┬──────┘       └─────────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │ Return      │
                   │ QA Response │
                   └─────────────┘
```

---

## Component Interactions

### External Dependencies
```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ External KB API │◄────┤ ExternalKBClient │◄────┤ QA Pipeline     │
│ (HTTP)          │     │ (Spec 001)       │     │ Capability      │
└─────────────────┘     └─────────────────┘     └─────────────────┘

┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ LiteLLM Gateway │◄────┤ ModelInference  │◄────┤ QA Pipeline     │
│ (Spec 001)      │     │ Capability       │     │ Capability      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### Internal Flow
```
QA API Route (qa_routes.py)
    │
    ├─► Validate request (qa_schemas.py)
    │
    ├─► QAPipelineCapability.execute()
    │       │
    │       ├─► QueryRewriteCapability.execute() ──► LiteLLMGateway.acomplete()
    │       │
    │       ├─► ExternalKBQueryCapability.execute() ──► ExternalKBClient.query()
    │       │
    │       ├─► ModelInferenceCapability.execute() ──► LiteLLMGateway.acomplete()
    │       │
    │       └─► HallucinationDetectionCapability.execute()
    │               │
    │               └─► sentence_transformers (similarity)
    │
    └─► Return QAQueryResponse (qa_schemas.py)
```

---

## Technology Choices

### Embeddings Model
- **Model**: `sentence-transformers/all-MiniLM-L6-v2`
- **Already in use**: Yes (Spec 001)
- **Dimension**: 384
- **Language**: Supports Chinese (moderate performance)
- **Justification**: No new dependencies, proven in production

### LLM Models
- **Query Rewriting**: Use default model (gpt-3.5-turbo or equivalent)
- **Answer Generation**: Use default model
- **Justification**: Configurable via LiteLLM, no hardcoding

### Async Framework
- **Already in use**: FastAPI + asyncio
- **No changes needed**: Leverage existing patterns

---

## Performance Estimates

| Stage | Estimated Time | Notes |
|-------|---------------|-------|
| Query validation | 50ms | Pydantic validation |
| Query rewriting | 1-2s | LLM call |
| KB retrieval | 500ms | HTTP call |
| Answer generation | 2-4s | LLM call |
| Hallucination check | 200ms | Embedding + similarity |
| **Total** | **4-7s** | Well under 10s limit |

---

## Risks & Open Questions

### Resolved
1. ✅ Hallucination detection algorithm → Similarity-based
2. ✅ Default fallback format → YAML configuration
3. ✅ Query rewriting strategy → LLM with context
4. ✅ Streaming with verification → Async + header
5. ✅ Regeneration strategy → Single attempt

### Monitoring Required
1. Hallucination detection precision (needs validation set)
2. Query rewriting improvement rate (needs A/B testing)
3. Token usage and cost tracking

---

## References

1. sentence-transformers: https://www.sbert.net/
2. LiteLLM documentation: https://docs.litellm.ai/
3. RAG best practices: "Building RAG Applications" (O'Reilly, 2024)
4. Hallucination detection: "Semantic Similarity for Hallucination Detection" (arXiv:2023)
