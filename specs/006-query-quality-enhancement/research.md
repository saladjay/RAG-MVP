# Research: Query Quality Enhancement Module

**Feature**: 006-query-quality-enhancement
**Date**: 2026-04-09
**Status**: Phase 0 Complete

## Overview

This document captures research findings, technical decisions, and architecture diagrams for implementing the Query Quality Enhancement Module.

## Technical Decisions

### Decision 1: Capability Interface Pattern

**Choice**: Extend existing `Capability` base class from `rag_service/capabilities/base.py`

**Rationale**:
- Consistency with existing RAG service architecture (QA Pipeline, Query Rewrite, etc.)
- Clean separation between HTTP API layer and business logic
- Built-in trace_id propagation and logging
- Easy testing through CapabilityInput/Output pattern

**Alternatives Considered**:
- Direct API implementation: Rejected due to tight coupling with FastAPI routes
- Standalone service: Rejected due to unnecessary deployment complexity

### Decision 2: Session State Storage

**Choice**: Redis with 15-minute TTL

**Rationale**:
- Fast access suitable for multi-turn conversation latency requirements (<3s p95)
- Automatic TTL expiration handles session cleanup without background jobs
- Supports future horizontal scaling (state stored externally)
- Consistent with non-functional requirements clarified during spec review

**Alternatives Considered**:
- In-memory storage: Rejected due to single-instance limitation and memory exhaustion risk
- Database storage: Rejected due to performance overhead (unnecessary for transient session data)

### Decision 3: Dimension Analysis Approach

**Choice**: LLM-based structured extraction using Prompt Service

**Rationale**:
- Flexible for natural language understanding (Chinese queries with varied formats)
- Leverages existing Prompt Service integration (feature 003)
- Easy to update dimension detection rules via prompt templates
- Returns structured output (present/missing dimensions) for programmatic handling

**Alternatives Considered**:
- Regex/pattern matching: Rejected due to complexity of Chinese language and varied query formats
- Rule-based engine: Rejected due to maintenance burden and brittleness

### Decision 4: Integration Point in QA Pipeline

**Choice**: Pre-process query BEFORE query_rewrite capability

**Rationale**:
- Dimension analysis happens first to identify missing information
- If dimensions are complete, proceed with normal query rewriting and retrieval
- If dimensions are missing, prompt user for information before any retrieval
- Enables early exit (better UX) vs. retrieving with poor-quality query

**Flow**:
```
User Query → QueryQualityCapability → [prompt if needed] → QueryRewriteCapability → KB Query → QA Pipeline
```

### Decision 5: Dual Knowledge Base Search

**Choice**: When file_type cannot be determined, search both PublicDocDispatch and PublicDocReceive simultaneously

**Rationale**:
- Ensures comprehensive results when user intent is ambiguous
- Parallel execution minimizes latency impact
- Clear feedback to user about which KB(s) were searched

**Implementation**: Use `asyncio.gather()` to query both collections when uncertainty detected.

### Decision 6: Conversation Turn Limit

**Choice**: Maximum 10 conversation turns per session

**Rationale**:
- Prevents resource exhaustion (infinite loops, abusive sessions)
- Provides natural reset point for complex queries
- Aligned with non-functional requirement from spec clarification

**Behavior**: After 10 turns, prompt user to summarize or start new session.

### Decision 7: 2025 Document Type Analysis

**Choice**: Extended dimension types based on 2025 document corpus analysis

**Rationale**:
- Analysis of 38 documents from 2025 directory revealed new document patterns not captured in original spec
- 会议纪要 (Meeting Minutes) is semantically distinct from general 纪要 (Summary/Minutes)
- New meeting types and organizational entities require dimension expansion
- Subject categories need hierarchical structure for better query matching

**Key Findings**:
1. **Document Type Distinction**:
   - 会议纪要: Specific to formal meeting records (e.g., 职工代表大会会议纪要)
   - 纪要: General summary documents
   - 公示: Public announcement documents

2. **New Meeting Types**:
   - 职工代表大会 (Workers' Congress)
   - 工会会员代表大会 (Union Member Congress)
   - 工作会议 (Working Meeting)
   - 启动会 (Kickoff Meeting)

3. **Extended Organization Entities**:
   - Professional Committees: 审计委员会, 产品技术委员会
   - Leading Groups: 领导小组
   - Assembly Bodies: 职工代表大会, 工会会员代表大会

4. **Enhanced Subject Categories** (with sub-categories):
   - 党建工作: 党费收支, 议事规则, 前置研究, 组织生活会, 民主评议, 意识形态工作
   - 工会工作: 职工代表大会, 工会活动, 知识课程分享, 妇女节活动
   - 信息化建设: OA系统, 网络安全, 软件正版化, 信息化项目
   - 专业委员会: 审计委员会, 产品技术委员会, 领导小组

**Implementation Notes**:
- Dimension analysis LLM prompt must distinguish between 会议纪要 and 纪要
- Subject matching should support hierarchical category lookup
- Colloquial expression mapping: "会议记录" → 会议纪要, "职代会" → 职工代表大会

## Architecture Diagrams

### Call Flow: Query Quality Enhancement

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         Query Quality Enhancement Call Flow                          │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  ┌─────────┐     ┌─────────────────┐     ┌──────────────┐     ┌──────────────┐     │
│  │ Client  │────▶│  FastAPI Route  │────▶│ QAPipeline   │────▶│ QueryQuality │     │
│  │         │◀────│  /qa/query      │◀────│ Capability   │◀────│  Capability   │     │
│  └─────────┘     └─────────────────┘     └──────────────┘     └──────────────┘     │
│                           │                        │                    │            │
│                           │                        │                    ▼            │
│                           │                        │           ┌──────────────┐     │
│                           │                        │           │ SessionStore │     │
│                           │                        │           │ (Redis)      │     │
│                           │                        │           └──────────────┘     │
│                           │                        │                    │            │
│                           │                        ▼                    ▼            │
│                           │           ┌─────────────────────────────────────┐     │
│                           │           │         LiteLLM/Prompt Service       │     │
│                           │           │    (Dimension Analysis Prompt)      │     │
│                           │           └─────────────────────────────────────┘     │
│                           │                        │                    │            │
│                           ▼                        ▼                    ▼            │
│                    ┌─────────────┐         ┌──────────────┐     ┌──────────────┐  │
│                    │ HTTP Client │         │ QueryRewrite │     │  Response    │  │
│                    │  (axios)    │         │  Capability   │     │  Builder    │  │
│                    └─────────────┘         └──────────────┘     └──────────────┘  │
│                                                                                     │
│  File Locations:                                                                  │
│  - FastAPI Route: src/rag_service/api/qa_routes.py (/qa/query endpoint)          │
│  - QAPipeline Capability: src/rag_service/capabilities/qa_pipeline.py            │
│  - QueryQuality Capability: src/rag_service/capabilities/query_quality.py        │
│  - SessionStore: src/rag_service/services/session_store.py                        │
│  - QueryRewrite Capability: src/rag_service/capabilities/query_rewrite.py        │
│  - Prompt Client: src/rag_service/services/prompt_client.py                       │
│  - Gateway: src/rag_service/inference/gateway.py (get_gateway())                  │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### Sequence Diagram: Multi-Turn Dimension Collection

```
┌─────────┐    ┌─────────────┐    ┌─────────────────┐    ┌──────────┐    ┌─────────┐
│ Client  │    │ API Handler │    │ QueryQuality    │    │ Session  │    │   LLM   │
│         │    │             │    │   Capability     │    │  Store   │    │         │
└────┬────┘    └──────┬──────┘    └────────┬────────┘    └────┬─────┘    └────┬────┘
     │                │                    │                 │               │
     │ POST /qa/query│                    │                 │               │
     │───────────────▶│                    │                 │               │
     │                │                    │                 │               │
     │ {query: "安全通知"}                  │                 │               │
     │ {context: {company_id, ...}}        │                 │               │
     │                │                    │                 │               │
     │                │ execute(input)     │                 │               │
     │                │───────────────────▶│                 │               │
     │                │                    │                 │               │
     │                │                    │ get_session(trace_id)            │
     │                │                    │─────────────────▶│               │
     │                │                    │◀─────────────────│               │
     │                │                    │ {turns: 0, state: {}}            │
     │                │                    │                 │               │
     │                │                    │ analyze_dimensions(query)        │
     │                │                    │─────────────────────────────────▶│
     │                │                    │                 │               │
     │                │                    │◀─────────────────────────────────│
     │                │                    │ {missing: ["year"], ...}         │
     │                │                    │                 │               │
     │                │                    │ update_session({needs_dim: year})│
     │                │                    │─────────────────▶│               │
     │                │                    │◀─────────────────│               │
     │                │◀───────────────────│ {turns: 1}                        │
     │                │                    │                 │               │
     │◀───────────────│ {response: "请问您需要查找哪一年的安全通知？"}                  │
     │                │                    │                 │               │
     │───────────────▶│ POST /qa/query     │                 │               │
     │ {"2024年"}     │                    │                 │               │
     │                │───────────────────▶│                 │               │
     │                │                    │ get_session(trace_id)            │
     │                │                    │─────────────────▶│               │
     │                │                    │◀─────────────────│ {turns: 1,    │
     │                │                    │                 │  needs_dim: year}
     │                │                    │                 │               │
     │                │                    │ merge_dimensions({year: 2024})   │
     │                │                    │                 │               │
     │                │                    │ update_session({dims_complete})  │
     │                │                    │─────────────────▶│               │
     │                │                    │◀─────────────────│               │
     │                │                    │                 │               │
     │                │                    │ proceed_to_retrieval()           │
     │                │                    │─────────────────▶│ (QA Pipeline)│
     │                │                    │                 │               │
     │                │◀───────────────────│ {answer, sources}                │
     │◀───────────────│                    │                 │               │
```

### Data Flow: Dimension Analysis

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           Dimension Analysis Data Flow                               │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  Input: User Query                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │ "关于安全管理的通知"                                                            │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                      │                                            │
│                                      ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │                    QueryQualityCapability.analyze()                          │    │
│  │  ┌───────────────────────────────────────────────────────────────────────┐  │    │
│  │  │ 1. Load dimension analysis prompt from Prompt Service                 │  │    │
│  │  │    Template: "query_dimension_analysis"                               │  │    │
│  │  │    Variables: {query, company_id, valid_dimensions}                   │  │    │
│  │  └───────────────────────────────────────────────────────────────────────┘  │    │
│  │  ┌───────────────────────────────────────────────────────────────────────┐  │    │
│  │  │ 2. Call LLM (LiteLLM gateway)                                          │  │    │
│  │  │    Model: configured default (e.g., glm-4.5-air)                      │  │    │
│  │  │    Output format: JSON with present/missing dimensions                │  │    │
│  │  └───────────────────────────────────────────────────────────────────────┘  │    │
│  │  ┌───────────────────────────────────────────────────────────────────────┐  │    │
│  │  │ 3. Parse LLM response into DimensionAnalysisResult                    │  │    │
│  │  │    - present: Set[Dimension]                                          │  │    │
│  │  │    - missing: Set[Dimension]                                          │  │    │
│  │  │    - confidence: high/medium/low                                       │  │    │
│  │  │    - suggestions: List[str] (if applicable)                          │  │    │
│  │  └───────────────────────────────────────────────────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                      │                                            │
│                                      ▼                                            │
│  Output: DimensionAnalysisResult                                                    │
│  ┌─────────────────────────────────────────────────────────────────────────────┐    │
│  │ {                                                                             │    │
│  │   "present": ["document_type:通知", "subject:安全管理"],                     │    │
│  │   "missing": ["year"],                                                       │    │
│  │   "confidence": "high",                                                      │    │
│  │   "prompt_text": "请问您需要查找哪一年的安全管理通知？"                           │    │
│  │ }                                                                             │    │
│  └─────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                     │
│  File Locations:                                                                  │
│  - Prompt Template: Prompt Service (template_id: "query_dimension_analysis")     │
│  - Capability: src/rag_service/capabilities/query_quality.py                     │
│  - Data Model: src/rag_service/models/query_quality.py (DimensionAnalysisResult)  │
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
| Integration point with QA Pipeline | Before query_rewrite, returns early if dimensions missing | Resolved |

## Dependencies on Other Features

| Feature | Dependency | Usage |
|---------|-----------|-------|
| Feature 001 (RAG Service MVP) | Base Capability class, LiteLLM gateway | Extends Capability pattern |
| Feature 003 (Prompt Service) | Prompt templates, SDK client | Dimension analysis prompts |
| Feature 005 (QA Pipeline) | Integration point | Query quality runs before query rewrite |

## Performance Considerations

1. **LLM Latency**: Dimension analysis adds ~500-1000ms (single LLM call)
2. **Session Lookup**: Redis GET ~1-5ms
3. **Total Budget**: <3 seconds p95 includes dimension analysis + prompts + retrieval

## Security Considerations

1. **Session Isolation**: Each trace_id maps to separate session key in Redis
2. **Input Validation**: Dimension values validated before merging into query context
3. **Traceability**: All operations logged with trace_id for audit
