# RAG Service Architecture

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client                                   │
│                   (HTTP / SDK / CLI)                             │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API Gateway Layer                           │
│                      (FastAPI + uvicorn)                         │
│                                                                  │
│  Unified Routes (POST /api/v1/*):                                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐         │
│  │  /query  │ │/documents│ │ /traces  │ │ /health   │         │
│  │  /stream │ │          │ │  /{id}   │ │ /models   │         │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └─────┬─────┘         │
│                                                                  │
│  Legacy Routes (deprecated, with Deprecation header):            │
│  /api/v1/ai/agent  /qa/query  /kb/upload  /api/v1/external/...  │
└────────┼──────────────┼──────────────┼──────────────┼───────────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Capability Interface Layer                     │
│              (3 Unified Capabilities + Strategy Pattern)         │
│                                                                  │
│  ┌───────────────┐ ┌──────────────┐ ┌──────────────┐            │
│  │    Query      │ │ Management   │ │    Trace     │            │
│  │  Capability   │ │  Capability  │ │  Capability  │            │
│  │               │ │              │ │              │            │
│  │ Strategies:   │ │ Delegates:   │ │ Delegates:   │            │
│  │ • Retrieval   │ │ • Doc upload │ │ • Health     │            │
│  │ • Quality     │ │ • Doc delete │ │ • Traces     │            │
│  └───────┬───────┘ │ • Models     │ └──────┬───────┘            │
│          │         └──────┬───────┘        │                    │
└──────────┼───────────────┼────────────────┼────────────────────┘
           │               │                │
           ▼               ▼                ▼
┌─────────────┐  ┌──────────────────┐  ┌────────────────┐
│  Retrieval  │  │  Inference       │  │  Observability │
│  Strategies │  │  Gateway         │  │                │
│             │  │                  │  │ ┌────────────┐ │
│ ┌─────────┐ │  │ ┌──────────────┐ │  │ │  LiteLLM   │ │
│ │ Milvus  │ │  │ │  LiteLLM     │ │  │ │  Observer  │ │
│ │ Vector  │ │  │ │  Gateway     │ │  │ ├────────────┤ │
│ │   DB    │ │  │ │  (unified)   │ │  │ │  Phidata   │ │
│ └─────────┘ │  │ ├──────────────┤ │  │ │  Observer  │ │
│             │  │ │Cloud HTTP    │ │  │ ├────────────┤ │
│ ┌─────────┐ │  │ │(internal)    │ │  │ │  Langfuse  │ │
│ │External │ │  │ ├──────────────┤ │  │ │  Observer  │ │
│ │  KB     │ │  │ │GLM/BigModel  │ │  │ └────────────┘ │
│ │HTTP API │ │  │ │(internal)    │ │  │                │
│ └─────────┘ │  │ └──────────────┘ │  └────────────────┘
└─────────────┘  └──────────────────┘
```

---

## 2. Core Request Flow (Unified Query Pipeline)

```
Client Request: POST /api/v1/query
    {"query": "What is RAG?"}
         │
         │  ① Middleware: generate trace_id
         ▼
    ┌─────────────┐
    │  FastAPI     │─── trace_id = "trace_abc123"
    │  Route       │─── set_trace_id(trace_id)
    └──────┬──────┘
           │  ② Route → QueryCapability
           ▼
    ┌─────────────────────────────────────────┐
    │         QueryCapability                  │
    │                                         │
    │  ③ Quality.pre_process(query)           │
    │     └─ basic: pass-through              │
    │     └─ dimension_gather: analyze dims   │
    │     └─ conversational: extract slots    │
    │                                         │
    │  ④ Query rewrite (if enabled)           │
    │     └─ rewrites query for better recall │
    │                                         │
    │  ⑤ RetrievalStrategy.retrieve()         │
    │     └─ Milvus: hybrid search            │
    │     └─ ExternalKB: HTTP API query       │
    │                                         │
    │  ⑥ LiteLLMGateway.acomplete_routed()    │
    │     └─ Routes to configured provider     │
    │       (cloud_http / glm / litellm)      │
    │                                         │
    │  ⑦ Hallucination detection (if enabled)  │
    │     └─ Similarity / LLM-based check     │
    │                                         │
    │  ⑧ Quality.post_process(answer, chunks)  │
    └──────────────┬──────────────────────────┘
                   │
                   ▼
    Response:
    {
      "answer": "RAG is ...",
      "sources": [{...}, {...}],
      "hallucination_status": {"passed": true, ...},
      "metadata": {"retrieval_count": 5, ...}
    }
```

---

## 3. Strategy Pattern

```
┌─────────────────────────────────────────────────────┐
│              Strategy Selection (config-driven)      │
│                                                      │
│  QUERY_RETRIEVAL_BACKEND=       QUERY_QUALITY_MODE=  │
│  ┌─────────────┐                ┌──────────────┐     │
│  │ milvus      │                │ basic        │     │
│  │   ↓         │                │   ↓          │     │
│  │ Milvus      │                │ pass-through │     │
│  │ Retrieval   │                ├──────────────┤     │
│  ├─────────────┤                │dimension_    │     │
│  │ external_kb │                │gather        │     │
│  │   ↓         │                │   ↓          │     │
│  │ ExternalKB  │                │ dimension    │     │
│  │ Retrieval   │                │ analysis     │     │
│  └─────────────┘                ├──────────────┤     │
│                                 │conversational│     │
│                                 │   ↓          │     │
│                                 │ slot fill +  │     │
│                                 │ belief state │     │
│                                 └──────────────┘     │
└─────────────────────────────────────────────────────┘
```

---

## 4. Layer Responsibility Matrix

```
┌────────────────────────────────────────────────────────────────────────┐
│ Layer           │ Responsibility            │ Spec Requirement        │
├─────────────────┼───────────────────────────┼─────────────────────────┤
│ API Gateway     │ 5 unified HTTP endpoints  │ FR-001, FR-009          │
│                 │ Request/Response models    │ FR-011                  │
│                 │ trace_id generation        │ FR-006                  │
│                 │ Deprecation headers (old)  │ FR-013                  │
├─────────────────┼───────────────────────────┼─────────────────────────┤
│ Capability      │ 3 unified capabilities    │ Architecture Core       │
│ Interface       │ Strategy pattern           │                         │
│ (3 Capabilities)│ HTTP isolated from impl   │                         │
│                 │ Config-driven selection    │                         │
├─────────────────┼───────────────────────────┼─────────────────────────┤
│ Strategies      │ Retrieval (Milvus/ExtKB)  │ FR-002                  │
│                 │ Quality (basic/dim/conv)   │ FR-008                  │
│                 │ Swappable via Protocol     │                         │
├─────────────────┼───────────────────────────┼─────────────────────────┤
│ Inference       │ Single LiteLLMGateway      │ FR-003, FR-004          │
│ Gateway         │ Internal providers         │ FR-005                  │
│ (unified)       │ Provider routing           │                         │
├─────────────────┼───────────────────────────┼─────────────────────────┤
│ Observability   │ Three-layer tracing        │ FR-007, FR-013          │
│ (unchanged)     │ Non-blocking recording     │ FR-012                  │
│                 │ Cross-layer trace_id       │ FR-014~016              │
└─────────────────┴───────────────────────────┴─────────────────────────┘
```

---

## 5. Directory → Layer Mapping

```
src/rag_service/
│
├── api/                          ← API Gateway Layer
│   ├── unified_routes.py            5 unified endpoints (POST /api/v1/*)
│   ├── unified_schemas.py           Unified request/response models
│   ├── routes.py                    Legacy endpoints (deprecated)
│   ├── qa_routes.py                 Legacy QA endpoints (deprecated)
│   ├── kb_upload_routes.py          Legacy KB endpoints (deprecated)
│   └── schemas.py                   Legacy request/response models
│
├── capabilities/                 ← Capability Interface Layer
│   ├── base.py                      Capability[T, T] + Registry
│   ├── query_capability.py          Unified query pipeline (strategies)
│   ├── management_capability.py     Document management + model listing
│   ├── trace_capability.py          Health checks + trace observation
│   ├── query_quality.py             Dimension gather (delegates from strategy)
│   ├── conversational_query.py      Conversational (delegates from strategy)
│   └── ... (legacy capabilities kept for transition)
│
├── strategies/                   ← Strategy Pattern Layer (new)
│   ├── retrieval.py                 RetrievalStrategy Protocol + Milvus + ExternalKB
│   └── quality.py                   QualityStrategy Protocol + Basic + DimGather + Conv
│
├── core/                         ← Shared Infrastructure
│   ├── exceptions.py                 Exception hierarchy
│   └── logger.py                     Structured JSON logger + trace_id
│
├── inference/                    ← Inference Layer (unified gateway)
│   └── gateway.py                    LiteLLMGateway (with internal HTTP/GLM providers)
│
├── models/                       ← Data Models (unchanged)
│   ├── query_quality.py              Dimension analysis models
│   └── conversational_query.py       Belief state, slot extraction models
│
├── services/                     ← Cross-cutting Services
│   ├── session_store.py              Redis session management
│   ├── belief_state_store.py         Belief state persistence
│   ├── colloquial_mapper.py          Colloquial term mapping
│   └── default_fallback.py           Fallback messages
│
├── observability/                ← Observability Layer (unchanged)
│   ├── trace_manager.py              UnifiedTraceManager (cross-layer)
│   ├── trace_propagation.py          trace_id ContextVar propagation
│   ├── litellm_observer.py           LLM layer metrics
│   ├── phidata_observer.py           Agent layer metrics
│   └── langfuse_client.py            Prompt layer metrics
│
├── config.py                     ← Unified Configuration (5 sections)
│
└── main.py                       ← Application entry + lifespan
```

---

## 6. Configuration (5 Sections)

```
┌─────────────────────────────────────────────────────────────┐
│                    Settings (5 sections)                      │
├──────────────────┬──────────────────────────────────────────┤
│ Section          │ Contents                                 │
├──────────────────┼──────────────────────────────────────────┤
│ milvus           │ Connection, vector search, hybrid search,│
│                  │ chunking, local embedding                 │
├──────────────────┼──────────────────────────────────────────┤
│ litellm          │ Provider selection, API config,           │
│                  │ internal HTTP/GLM/embedding/rerank        │
├──────────────────┼──────────────────────────────────────────┤
│ query            │ Retrieval backend, quality mode,          │
│                  │ pipeline toggles, external KB, Redis      │
├──────────────────┼──────────────────────────────────────────┤
│ langfuse         │ Observability (unchanged)                 │
├──────────────────┼──────────────────────────────────────────┤
│ server           │ Host/port, CORS, feature flags            │
└──────────────────┴──────────────────────────────────────────┘

Backward compatibility: old env vars (CLOUD_COMPLETION_*, GLM_*, etc.)
still accepted with deprecation warnings. Old Settings attributes
(settings.cloud_completion, settings.qa, etc.) work via property aliases.
```

---

## 7. Key Design Decisions

```
┌────────────────────────────────────────────────────────────────┐
│ Decision                │ Rationale                            │
├─────────────────────────┼──────────────────────────────────────┤
│ 3 Unified Capabilities  │ 13+ → 3 capabilities reduce         │
│ (not 13+ individual)    │ cognitive load and maintenance       │
├─────────────────────────┼──────────────────────────────────────┤
│ Strategy Pattern        │ Retrieval/Quality strategies swap    │
│ (typing.Protocol)       │ without code changes, config-driven  │
├─────────────────────────┼──────────────────────────────────────┤
│ Single LiteLLMGateway   │ 3 parallel gateways → 1 entry point │
│ (internal providers)    │ Provider routing hidden from callers │
├─────────────────────────┼──────────────────────────────────────┤
│ 5 Config Sections       │ 16 config classes → 5 sections      │
│ (with backward compat)  │ Old env vars still work with warnings│
├─────────────────────────┼──────────────────────────────────────┤
│ Capability abstraction  │ Components swappable without API     │
│                         │ changes, clean test boundaries       │
├─────────────────────────┼──────────────────────────────────────┤
│ Three-layer Observ.     │ Each layer records independently,    │
│ (unchanged)             │ linked by trace_id, non-blocking     │
└─────────────────────────┴──────────────────────────────────────┘
```

---

## 8. External Dependencies

```
                    ┌─────────────┐
                    │   Milvus    │  Vector DB
                    │  :19530     │  (knowledge storage & retrieval)
                    └─────────────┘
                          ▲
                          │ vector search / insert
                          │
┌──────────┐    ┌─────────┴──────────┐    ┌─────────────┐
│ Cloud    │    │                    │    │  Langfuse   │
│ HTTP LLM │◀──│   RAG Service      │──▶│  (cloud)    │
│ :9091    │    │   :8000            │    │  Prompt mgmt│
└──────────┘    │                    │    └─────────────┘
                │  ┌──────────────┐  │
┌──────────┐    │  │  LiteLLM     │  │    ┌─────────────┐
│ GLM      │◀──│  │  Gateway     │  │    │   Redis     │
│ BigModel │    │  │  (unified)   │──│──▶│  :6379      │
│ (cloud)  │    │  └──────────────┘  │    │  (Session)  │
└──────────┘    │                    │    └─────────────┘
                └────────────────────┘
┌──────────┐          ▲
│ OpenAI   │──────────┘
│ (cloud)  │
└──────────┘
```
