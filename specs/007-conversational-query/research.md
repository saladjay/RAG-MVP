# Research: Conversational Query Enhancement Module

**Feature**: 007-conversational-query
**Date**: 2026-04-10
**Status**: Phase 0 Complete

## Overview

This document captures research findings, technical decisions, and architecture diagrams for implementing the Conversational Query Enhancement Module.

## Technical Decisions

### Decision 1: Capability Interface Pattern

**Choice**: Extend existing `Capability` base class from `rag_service/capabilities/base.py`

**Rationale**:
- Consistency with existing RAG service architecture (QA Pipeline, Query Rewrite, Query Quality)
- Clean separation between HTTP API layer and business logic
- Built-in trace_id propagation and logging
- Easy testing through CapabilityInput/Output pattern

**Alternatives Considered**:
- Direct API implementation: Rejected due to tight coupling with FastAPI routes
- Standalone service: Rejected due to unnecessary deployment complexity

### Decision 2: Conversation State Storage

**Choice**: Redis with 15-minute TTL

**Rationale**:
- Fast access suitable for multi-turn conversation latency requirements (<3s p95)
- Automatic TTL expiration handles session cleanup without background jobs
- Supports future horizontal scaling (state stored externally)
- Consistent with non-functional requirements clarified during spec review

**Alternatives Considered**:
- In-memory storage: Rejected due to single-instance limitation and memory exhaustion risk
- Database storage: Rejected due to performance overhead (unnecessary for transient session data)

### Decision 3: Belief State Representation

**Choice**: Slot-based belief state with JSON serialization

**Rationale**:
- Flexible for varying query dimensions (temporal, spatial, document, content, quantity)
- Easy to extend with new slot types without schema changes
- Simple to serialize for Redis storage
- Compatible with LLM-based slot filling approaches

**Alternatives Considered**:
- Strict schema with typed slots: Rejected due to complexity and brittleness
- Probabilistic belief state: Rejected due to complexity overhead not justified by requirements

### Decision 4: Colloquial Term Mapping Strategy

**Choice**: Hybrid approach with static mappings + LLM-based inference

**Rationale**:
- Static mappings for common colloquial terms provide fast, predictable results
- LLM-based inference for unknown terms enables handling of novel expressions
- Balance between performance (static) and flexibility (LLM)
- Can gradually build mapping library from LLM inferences

**Alternatives Considered**:
- Pure static mappings: Rejected due to inability to handle new expressions
- Pure LLM-based: Rejected due to latency and cost overhead

### Decision 5: Query Generation Strategy

**Choice**: Three-query variation with must_include terms and keyword expansion

**Rationale**:
- Multiple query variations improve recall by capturing different phrasings
- must_include terms ensure core intent is preserved
- Keyword expansion adds synonyms and related terms
- Independent queries allow vector search to find best matches

**Alternatives Considered**:
- Single query expansion: Rejected due to lower recall
- Query rewriting with LLM: Rejected due to latency and consistency concerns

### Decision 6: Business Domain Classification

**Choice**: Rule-based domain detection with 10 primary domains

**Rationale**:
- Domains have distinct query patterns and terminology
- Rule-based detection is fast and predictable
- Enables domain-specific query generation (e.g., finance queries include "报销" while safety queries don't)
- Matches user mental model of document organization

**Domains**:
1. finance (财务报销)
2. hr (人事工作)
3. safety (安全生产)
4. governance (党建工作)
5. it (信息化建设)
6. procurement (采购管理)
7. admin (行政管理)
8. party (党务工作)
9. union (工会工作)
10. committee (专业委员会)
11. other (其他)

### Decision 7: Follow-up Query Detection

**Choice**: Pronoun-based detection with conversation history reference

**Rationale**:
- Chinese language heavily uses pronouns (这/那/这个/那个/它) for reference
- Direct pronoun detection is simpler than full coreference resolution
- Conversation history provides context for interpretation
- Sufficient for common follow-up patterns

**Alternatives Considered**:
- Full coreference resolution: Rejected due to complexity and performance overhead
- No follow-up detection: Rejected due to poor user experience

### Decision 8: Integration Point in QA Pipeline

**Choice**: Pre-process query BEFORE query_quality capability

**Rationale**:
- Conversational query handling happens first to establish context
- Belief state accumulation happens over multiple turns
- Once context is established, pass to query quality for dimension analysis
- Then proceed to query rewrite and retrieval

**Flow**:
```
User Query → ConversationalQueryCapability → [multi-turn if needed] → QueryQualityCapability → QueryRewriteCapability → KB Query → QA Pipeline
```

### Decision 9: Conversation Turn Limit

**Choice**: Maximum 10 conversation turns per session

**Rationale**:
- Prevents resource exhaustion (infinite loops, abusive sessions)
- Provides natural reset point for complex conversations
- Aligned with non-functional requirement from spec clarification

**Behavior**: After 10 turns, prompt user to summarize or start new session.

### Decision 10: 2025 Document Type Analysis

**Choice**: Extended conversation patterns based on 2025 document corpus analysis

**Rationale**:
- Analysis of 38 documents from 2025 directory revealed new conversation patterns
- New meeting types (职工代表大会, 工会会员代表大会, 工作会议, 启动会) require specific handling
- Colloquial mappings (会议记录→会议纪要, 职代会→职工代表大会) improve user understanding
- Extended organization entities (专业委员会, 领导小组) enable better context tracking

**Key Findings**:
1. **New Meeting Types**: 职工代表大会, 工会会员代表大会, 工作会议, 启动会
2. **New Colloquial Mappings**:
   - 会议记录 → 会议纪要
   - 职代会 → 职工代表大会
   - 三八活动 → 妇女节活动
3. **Extended Organizations**: 专业委员会 (审计委员会, 产品技术委员会), 领导小组
4. **Enhanced Categories**: 工会工作 with subcategories, new 专业委员会 domain

## Architecture Diagrams

### Call Flow: Conversational Query Enhancement

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                       Conversational Query Enhancement Call Flow                     │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  ┌─────────┐     ┌─────────────────┐     ┌──────────────┐     ┌──────────────┐     │
│  │ Client  │────▶│  FastAPI Route  │────▶│ QAPipeline   │────▶│Conversational│     │
│  │         │◀────│  /qa/query      │◀────│ Capability   │◀────│ QueryCapability│     │
│  └─────────┘     └─────────────────┘     └──────────────┘     └──────────────┘     │
│                           │                        │                    │            │
│                           │                        │                    ▼            │
│                           │                        │           ┌──────────────┐     │
│                           │                        │           │BeliefStateStore│     │
│                           │                        │           │(Redis)       │     │
│                           │                        │           └──────────────┘     │
│                           │                        │                    │            │
│                           │                        ▼                    ▼            │
│                           │           ┌─────────────────────────────────────┐     │
│                           │           │         LiteLLM/Prompt Service       │     │
│                           │           │  (Conversation & Query Gen Prompts) │     │
│                           │           └─────────────────────────────────────┘     │
│                           │                        │                    │            │
│                           ▼                        ▼                    ▼            │
│                    ┌─────────────┐         ┌──────────────┐     ┌──────────────┐  │
│                    │ HTTP Client │         │QueryQuality  │     │ Colloquial   │  │
│                    │  (axios)    │         │ Capability   │     │ Mapper       │  │
│                    └─────────────┘         └──────────────┘     └──────────────┘  │
│                                                                                     │
│  File Locations:                                                                  │
│  - FastAPI Route: src/rag_service/api/qa_routes.py (/qa/query endpoint)          │
│  - QAPipeline Capability: src/rag_service/capabilities/qa_pipeline.py            │
│  - ConversationalQuery Capability: src/rag_service/capabilities/conversational_query.py│
│  - BeliefStateStore: src/rag_service/services/belief_state_store.py             │
│  - ColloquialMapper: src/rag_service/services/colloquial_mapper.py              │
│  - Prompt Client: src/rag_service/services/prompt_client.py                     │
│  - Gateway: src/rag_service/inference/gateway.py (get_gateway())                │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Sequence Diagram: Multi-Turn Conversation

```
┌─────────┐    ┌─────────────┐    ┌─────────────────┐    ┌──────────┐    ┌─────────┐
│ Client  │    │ API Handler │    │Conversational    │    │BeliefState│    │   LLM   │
│         │    │             │    │ QueryCapability  │    │ Store    │    │         │
└────┬────┘    └──────┬──────┘    └────────┬────────┘    └────┬─────┘    └────┬────┘
     │                │                    │                 │               │
     │ POST /qa/query│                    │                 │               │
     │───────────────▶│                    │                 │               │
     │                │                    │                 │               │
     │ {query: "安全规定"}                  │                 │               │
     │ {context: {company_id, ...}}        │                 │               │
     │                │                    │                 │               │
     │                │ execute(input)     │                 │               │
     │                │───────────────────▶│                 │               │
     │                │                    │                 │               │
     │                │                    │ get_session(trace_id)            │
     │                │                    │─────────────────▶│               │
     │                │                    │◀─────────────────│ {state: new} │
     │                │                    │                 │               │
     │                │                    │ extract_slots(query)            │
     │                │                    │─────────────────────────────────▶│
     │                │                    │                 │               │
     │                │                    │◀─────────────────────────────────│
     │                │                    │ {year: null, topic: "安全"}     │
     │                │                    │                 │               │
     │                │                    │ update_session({missing: year})│
     │                │                    │─────────────────▶│               │
     │                │                    │◀─────────────────│               │
     │                │◀───────────────────│ {turns: 1, action: "prompt"}   │
     │                │                    │                 │               │
     │◀───────────────│ {message: "请问您需要查找哪一年的安全规定？"}                  │
     │                │                    │                 │               │
     │───────────────▶│ POST /qa/query     │                 │               │
     │ {"2024年"}     │                    │                 │               │
     │                │───────────────────▶│                 │               │
     │                │                    │ get_session(trace_id)            │
     │                │                    │─────────────────▶│               │
     │                │                    │◀─────────────────│ {turns: 1,    │
     │                │                    │                 │  pending: year}│
     │                │                    │                 │               │
     │                │                    │ merge_slots({year: 2024})       │
     │                │                    │                 │               │
     │                │                    │ detect_domain("安全")           │
     │                │                    │─────────────────────────────────▶│
     │                │                    │                 │               │
     │                │                    │◀─────────────────────────────────│
     │                │                    │ {domain: safety}                 │
     │                │                    │                 │               │
     │                │                    │ generate_queries(safety, 2024)  │
     │                │                    │─────────────────────────────────▶│
     │                │                    │                 │               │
     │                │                    │◀─────────────────────────────────│
     │                │                   │ {q1, q2, q3, must_include, ...} │
     │                │                    │                 │               │
     │                │                    │ update_session({complete})      │
     │                │                    │─────────────────▶│               │
     │                │                    │◀─────────────────│               │
     │                │                    │                 │               │
     │                │                    │ proceed_to_qa_pipeline()        │
     │                │                    │─────────────────▶│ (next)       │
     │                │                    │                 │               │
     │                │◀───────────────────│ {queries, answer, sources}      │
     │◀───────────────│                    │                 │               │
```

### Data Flow: Query Generation

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           Query Generation Data Flow                                 │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  Input: Collected Slots from Belief State                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │ {                                                                             │    │
│  │   "domain": "finance",                                                       │    │
│  │   "year": 2024,                                                              │    │
│  │   "expense_type": "住宿",                                                    │    │
│  │   "city": "北京",                                                             │    │
│  │   "level": null                                                               │    │
│  │ }                                                                             │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                      │                                            │
│                                      ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │              Domain-Specific Template Selection                              │    │
│  │  ┌───────────────────────────────────────────────────────────────────────┐  │    │
│  │  │ Finance Domain Templates:                                               │  │    │
│  │  │   - Standard: "…{city}{expense_type}报销标准是多少？"                   │  │    │
│  │  │   - Rule: "…{city}{expense_type}需要哪些单据？"                          │  │    │
│  │  │   - Process: "…{city}{expense_type}报销流程是什么？"                     │  │    │
│  │  │   - Scope: "…{city}{expense_type}报销范围是什么？"                       │  │    │
│  │  └───────────────────────────────────────────────────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                      │                                            │
│                                      ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │              Colloquial Term Expansion                                      │    │
│  │  ┌───────────────────────────────────────────────────────────────────────┐  │    │
│  │  │ Expand expense_type:                                                   │  │    │
│  │  │   "住宿" → ["住宿", "酒店", "住宿费"]                                   │  │    │
│  │  │ Expand city:                                                           │  │    │
│  │  │   "北京" → ["北京", "京"]                                               │  │    │
│  │  │ Add domain keywords:                                                    │  │    │
│  │  │   finance → ["报销", "标准", "额度", "上限"]                            │  │    │
│  │  └───────────────────────────────────────────────────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                      │                                            │
│                                      ▼                                            │
│  Output: Query Generation Result                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │ {                                                                             │    │
│  │   "q1": "北京住宿报销标准是多少？",                                           │    │
│  │   "q2": "北京市酒店费用报销上限是多少？",                                     │    │
│  │   "q3": "京地区住宿费用标准如何规定？",                                       │    │
│  │   "must_include": ["北京", "住宿", "报销", "标准"],                           │    │
│  │   "keywords": ["北京", "京", "住宿", "酒店", "住宿费", "报销", "标准", "额度", "上限"], │    │
│  │   "domain": "business_query"                                                │    │
│  │ }                                                                             │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                     │
│  File Locations:                                                                  │
│  - Capability: src/rag_service/capabilities/conversational_query.py               │
│  - Data Model: src/rag_service/models/conversational_query.py (QueryGenerationResult)│
│  - Colloquial Mapper: src/rag_service/services/colloquial_mapper.py              │
│  - LLM Gateway: src/rag_service/inference/gateway.py (get_gateway())              │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

## Open Questions (Resolved)

| Question | Resolution | Status |
|----------|-----------|--------|
| Session timeout duration | 15 minutes with 10-turn limit (from spec clarification) | Resolved |
| System availability target | 99.5% single-instance (from spec clarification) | Resolved |
| Observability requirements | Full tracing with JSON logs + trace_id + Langfuse (from spec) | Resolved |
| Session state storage | Redis with TTL (from spec clarification) | Resolved |
| Integration point with QA Pipeline | Before query_quality, multi-turn handling first | Resolved |
| Query generation approach | Three-query variation with must_include terms | Resolved |
| Colloquial mapping strategy | Hybrid static + LLM-based inference | Resolved |

## Dependencies on Other Features

| Feature | Dependency | Usage |
|---------|-----------|-------|
| Feature 001 (RAG Service MVP) | Base Capability class, LiteLLM gateway | Extends Capability pattern |
| Feature 003 (Prompt Service) | Prompt templates, SDK client | Conversation and query generation prompts |
| Feature 005 (QA Pipeline) | Integration point | Conversational query runs before query quality |
| Feature 006 (Query Quality Enhancement) | Dimension analysis | Conversational query establishes context, then passes to query quality |

## Performance Considerations

1. **LLM Latency**: Slot extraction adds ~500-800ms, query generation adds ~700-1000ms (two LLM calls)
2. **Session Lookup**: Redis GET ~1-5ms
3. **Colloquial Mapping**: Static lookup <1ms, LLM-based inference ~500ms
4. **Total Budget**: <3 seconds p95 includes conversation handling + query generation + retrieval

## Security Considerations

1. **Session Isolation**: Each trace_id maps to separate session key in Redis
2. **Input Validation**: Slot values validated before being used in query generation
3. **Traceability**: All operations logged with trace_id for audit
4. **Colloquial Term Injection**: Static mappings only, no user-contributed mappings
