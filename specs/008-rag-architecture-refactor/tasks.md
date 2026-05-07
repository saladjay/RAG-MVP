# Tasks: RAG Service Architecture Refactoring

**Input**: Design documents from `/specs/008-rag-architecture-refactor/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: Tests are MANDATORY per constitution (Principle III). Use real implementations, minimize mocks.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

**Constitution Compliance**:
- All implementation tasks must include documentation headers (Principle I)
- Testing tasks must use real implementations (Principle III)
- Python tasks must use `uv` environment (Principle IV)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create strategy protocol definitions and unified schema models that all user stories depend on.

- [x] T001 Create `src/rag_service/strategies/__init__.py` with exports for RetrievalStrategy, QualityStrategy protocols
- [x] T002 [P] Define `RetrievalStrategy` Protocol in `src/rag_service/strategies/retrieval.py` — async `retrieve(query, top_k, context, trace_id) -> list[dict]` method signature per data-model.md
- [x] T003 [P] Define `QualityStrategy` Protocol in `src/rag_service/strategies/quality.py` — async `pre_process(query, session_id, config) -> tuple[str, Optional[dict]]` and `post_process(answer, chunks, session_id) -> dict` per data-model.md
- [x] T004 [P] Create unified request schema in `src/rag_service/api/unified_schemas.py` — `UnifiedQueryRequest` (query, context, session_id, top_k, stream) and `QueryResponse` (answer, sources, hallucination_status, metadata) per contracts/api.md
- [x] T005 [P] Create `DocumentRequest` schema in `src/rag_service/api/unified_schemas.py` — single model with operation field (upload/update/delete) replacing separate PUT/DELETE endpoints

**Checkpoint**: Strategy protocols and unified schemas defined. No runtime changes yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Consolidate config and implement strategy classes. MUST complete before ANY user story work begins.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Config Consolidation

- [x] T006 Consolidate Milvus config: merge `MilvusConfig`, `MilvusKBConfig`, and `EmbeddingConfig` into a single `MilvusConfig` class in `src/rag_service/config.py` — keep all existing env var names working via aliases, add new unified field names per data-model.md
- [x] T007 [P] Consolidate LiteLLM config: merge `LiteLLMConfig`, `CloudCompletionConfig`, `GLMConfig`, `CloudEmbeddingConfig`, `CloudRerankConfig` into a single `LiteLLMConfig` with nested `ProviderConfig` models in `src/rag_service/config.py` — add `LITELLM_PROVIDER` field, keep old env vars working with deprecation logging
- [x] T008 [P] Consolidate query config: merge `QAConfig`, `QueryQualityConfig`, `ConversationalQueryConfig`, `ExternalKBConfig` into a single `QueryConfig` with nested `ExternalKBSettings` in `src/rag_service/config.py` — add `QUERY_RETRIEVAL_BACKEND` and `QUERY_QUALITY_MODE` fields, keep all old env vars working
- [x] T009 [P] Consolidate server config: merge `ServerConfig`, `CORSConfig`, `FeatureFlags` into a single `ServerConfig` in `src/rag_service/config.py`
- [x] T010 Update `Settings` class in `src/rag_service/config.py` to use 5 consolidated config sections (milvus, litellm, langfuse, server, query), remove `default_gateway` field, add backward-compat env var mapping for `CLOUD_COMPLETION_*` → `LITELLM_*`, `GLM_*` → `LITELLM_GLM_*`
- [x] T011 Verify `src/rag_service/config.py` is under 350 lines total — target ~300 lines per plan.md SC-003

### Strategy Implementations

- [x] T012 Implement `MilvusRetrieval` class in `src/rag_service/strategies/retrieval.py` — extract retrieval logic from `capabilities/knowledge_query.py` and `capabilities/milvus_kb_query.py`, satisfy `RetrievalStrategy` Protocol
- [x] T013 [P] Implement `ExternalKBRetrieval` class in `src/rag_service/strategies/retrieval.py` — extract retrieval logic from `capabilities/external_kb_query.py`, satisfy `RetrievalStrategy` Protocol
- [x] T014 [P] Implement `BasicQuality` class (pass-through) in `src/rag_service/strategies/quality.py` — satisfy `QualityStrategy` Protocol
- [x] T015 [P] Implement `DimensionGatherQuality` class in `src/rag_service/strategies/quality.py` — extract logic from `capabilities/query_quality.py`, satisfy `QualityStrategy` Protocol, use existing `SessionStoreService` and data models from `src/rag_service/models/`
- [x] T016 [P] Implement `ConversationalQuality` class in `src/rag_service/strategies/quality.py` — extract logic from `capabilities/conversational_query.py`, satisfy `QualityStrategy` Protocol, use existing `BeliefStateStoreService`, `ColloquialMapperService`

**Checkpoint**: Foundation ready — 5 config classes, 5 strategy implementations. User story work can begin.

---

## Phase 3: User Story 2 - Single Inference Gateway (Priority: P1) 🎯

**Goal**: Merge HTTPCompletionGateway and GLMCompletionGateway into LiteLLMGateway as internal providers. Remove `default_gateway` selector. Callers never specify a gateway.

**Independent Test**: Configure `LITELLM_PROVIDER=cloud_http` in `.env`, send a query, verify inference goes through LiteLLM. Change to `LITELLM_PROVIDER=glm`, verify same code path works without caller changes.

**Spec reference**: FR-003, FR-004 | Success Criteria: SC-004

### Implementation for User Story 2

- [x] T017 [US2] Add internal provider routing to `LiteLLMGateway` in `src/rag_service/inference/gateway.py` — add `_route_to_provider()` method that selects between cloud_http, glm, and standard LiteLLM providers based on `config.litellm.provider`
- [x] T018 [US2] Move `HTTPCompletionGateway.complete()` logic into `LiteLLMGateway._cloud_http_complete()` in `src/rag_service/inference/gateway.py` — preserve all existing HTTP Cloud behavior (auth, retry, streaming)
- [x] T019 [US2] Move `GLMCompletionGateway.complete()` logic into `LiteLLMGateway._glm_complete()` in `src/rag_service/inference/gateway.py` — preserve GLM-specific options (enable_thinking, Bearer token auth)
- [x] T020 [US2] Move `HTTPEmbeddingGateway` logic into `LiteLLMGateway` as internal embedding method in `src/rag_service/inference/gateway.py`
- [x] T021 [US2] Update `LiteLLMGateway` constructor in `src/rag_service/inference/gateway.py` to accept unified `LiteLLMConfig` and auto-configure internal provider from `config.provider` field
- [x] T022 [US2] Remove `get_http_gateway()` and `get_glm_gateway()` factory functions from `src/rag_service/inference/gateway.py` — replace with single `get_gateway()` that always returns `LiteLLMGateway` with configured provider
- [x] T023 [US2] Update any code referencing `get_http_gateway()` or `get_glm_gateway()` to use `get_gateway()` instead — check `capabilities/qa_pipeline.py`, `capabilities/model_inference.py`, `api/routes.py`

**Checkpoint**: LiteLLMGateway is the only exposed gateway class. `LITELLM_PROVIDER` env var controls provider selection. No caller code changes needed to switch providers.

---

## Phase 4: User Story 1 - Unified Query Interface (Priority: P1) 🎯 MVP

**Goal**: Create 3 unified Capabilities (Query, Management, Trace) that replace 13+ existing capabilities. QueryCapability uses strategies internally. All existing functionality preserved.

**Independent Test**: Send `POST /api/v1/query {"query": "test"}` and verify response contains answer, sources, trace_id regardless of retrieval backend or quality mode. Verify registry has exactly 3 entries.

**Spec reference**: FR-001, FR-002, FR-005, FR-006, FR-008, FR-011, FR-012, FR-014 | Success Criteria: SC-002, SC-006, SC-007, SC-009, SC-010

### Implementation for User Story 1

- [x] T024 [US1] Create `QueryCapability` in `src/rag_service/capabilities/query_capability.py` — inject `RetrievalStrategy` and `QualityStrategy` from config (`QueryConfig.retrieval_backend`, `QueryConfig.quality_mode`), implement `execute(UnifiedQueryRequest) -> QueryResponse` with pipeline: quality.pre_process → retrieval.retrieve → litellm.generate → hallucination.check → quality.post_process
- [x] T025 [US1] Wire query rewrite logic into `QueryCapability` in `src/rag_service/capabilities/query_capability.py` — extract from `capabilities/query_rewrite.py`, make it an internal step controlled by `QueryConfig.enable_query_rewrite`
- [x] T026 [US1] Wire hallucination detection logic into `QueryCapability` in `src/rag_service/capabilities/query_capability.py` — extract from `capabilities/hallucination_detection.py`, make it an internal step controlled by `QueryConfig.enable_hallucination_check`
- [x] T027 [US1] Add streaming support to `QueryCapability` in `src/rag_service/capabilities/query_capability.py` — implement `stream_execute()` method that yields tokens from LiteLLMGateway
- [x] T028 [P] [US1] Create `ManagementCapability` in `src/rag_service/capabilities/management_capability.py` — consolidate document upload from `capabilities/document_management.py` and `capabilities/milvus_kb_upload.py`, model listing from `capabilities/model_discovery.py`, satisfy FR-005
- [x] T029 [P] [US1] Create `TraceCapability` in `src/rag_service/capabilities/trace_capability.py` — consolidate trace observation from `capabilities/trace_observation.py` and health check from `capabilities/health_check.py`, satisfy FR-006
- [x] T030 [US1] Update `main.py` lifespan in `src/rag_service/main.py` — replace 10 individual capability registrations with 3 unified capabilities (QueryCapability, ManagementCapability, TraceCapability), wire config-driven strategy selection
- [x] T031 [US1] Verify CapabilityRegistry contains exactly 3 entries after startup — log `registry.list_capabilities()` in `src/rag_service/main.py` and confirm SC-007

**Checkpoint**: 3 capabilities registered. All existing query, document, trace, health, and model functionality accessible through new capabilities. Old capabilities still exist in codebase but are no longer registered.

---

## Phase 5: User Story 4 - Consistent API Surface (Priority: P2)

**Goal**: Create unified router with exactly 5 endpoints. Old endpoints respond with deprecation headers. E2E test framework's RAGClient updated.

**Independent Test**: Hit each of the 5 new endpoints and verify correct responses. Hit old endpoints and verify `Deprecation` header in response. Update RAGClient URL and run E2E tests.

**Spec reference**: FR-009, FR-013 | Success Criteria: SC-001, SC-005, SC-008

### Implementation for User Story 4

- [x] T032 [US4] Create unified query endpoint `POST /api/v1/query` in `src/rag_service/api/unified_routes.py` — delegate to `registry.get("QueryCapability").execute()`, handle `QueryQualityPromptRequired` exception with prompt response per contracts/api.md
- [x] T033 [US4] Create streaming query endpoint `POST /api/v1/query/stream` in `src/rag_service/api/unified_routes.py` — delegate to `QueryCapability.stream_execute()`, return `text/event-stream` per contracts/api.md
- [x] T034 [US4] Create unified document endpoint `POST /api/v1/documents` in `src/rag_service/api/unified_routes.py` — route to `ManagementCapability` with operation field (upload/update/delete) per contracts/api.md
- [x] T035 [P] [US4] Create trace endpoint `GET /api/v1/traces/{trace_id}` in `src/rag_service/api/unified_routes.py` — delegate to `TraceCapability`, unchanged response format
- [x] T036 [P] [US4] Create health endpoint `GET /api/v1/health` in `src/rag_service/api/unified_routes.py` — delegate to `TraceCapability.health_check()`
- [x] T037 [P] [US4] Create models endpoint `GET /api/v1/models` in `src/rag_service/api/unified_routes.py` — delegate to `ManagementCapability`
- [x] T038 [US4] Add deprecation headers to old endpoints in `src/rag_service/api/routes.py` — add `response.headers["Deprecation"] = "true; version=0.2.0"` to `POST /ai/agent`, `POST /query`, `POST /external/query`, `GET /observability/metrics`, `DELETE /documents/{id}`, `PUT /documents/{id}`
- [x] T039 [P] [US4] Add deprecation headers to old QA endpoints in `src/rag_service/api/qa_routes.py` — add deprecation header to `POST /query`, `POST /query/stream`, `GET /health`
- [x] T040 [P] [US4] Add deprecation headers to old KB endpoints in `src/rag_service/api/kb_upload_routes.py` — add deprecation header to `POST /upload`, `POST /collection/create`, `GET /collection/info`, `GET /health`
- [x] T041 [US4] Update `src/rag_service/main.py` — include `unified_routes.router` with prefix `/api/v1`, keep old routers for backward compatibility
- [x] T042 [US4] Update E2E test framework RAGClient in `src/e2e_test/clients/` (if exists) — change base URL from `/qa/query` to `/api/v1/query` per FR-013 and SC-005

**Checkpoint**: 5 unified endpoints operational. Old endpoints return correct responses with `Deprecation` header. API count ≤ 5 new + old deprecated.

---

## Phase 6: User Story 3 - Simplified Configuration (Priority: P2)

**Goal**: Verify config is under 350 lines, old env vars accepted with warnings, .env.example updated.

**Independent Test**: Start service with only 5 config sections in `.env`, verify all functionality. Start with old env vars, verify deprecation warnings logged.

**Spec reference**: FR-007 | Success Criteria: SC-003

### Implementation for User Story 3

- [x] T043 [US3] Add deprecation warning logging for old env vars in `src/rag_service/config.py` — when `CLOUD_COMPLETION_URL` detected, log warning mapping to `LITELLM_CLOUD_HTTP_URL`; same for `GLM_*`, `QA_*`, `QUERY_QUALITY_*`, `CONVERSATIONAL_QUERY_*`
- [x] T044 [US3] Update `src/rag_service/.env.example` (or project root `.env.example`) with new unified variable names — 5 sections: MILVUS, LITELLM, QUERY, LANGFUSE, SERVER; document deprecated vars as comments
- [x] T045 [US3] Verify `src/rag_service/config.py` line count ≤ 350 — if over, identify remaining consolidation opportunities (remove duplicated validators, merge similar field definitions)
- [x] T046 [US3] Verify service starts with minimum config — only `MILVUS_HOST`, `LITELLM_PROVIDER`, `LITELLM_MODEL`, `SERVER_PORT` set; all other fields use sensible defaults

**Checkpoint**: Config file under 350 lines. 5 clear sections. Old env vars work with warnings. New deployments only need 5 sections.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation updates, architecture doc refresh, final validation.

- [x] T047 [P] Update `docs/architecture.md` to reflect new 3-Capability architecture — update System Overview diagram, Request Flow diagram, Directory → Layer Mapping per quickstart.md
- [x] T048 [P] Verify three-layer observability stack unchanged — run a query through unified endpoint, check Langfuse/Phidata/LiteLLM observers capture all metrics per SC-010
- [x] T049 [P] Verify all edge cases from spec.md handle gracefully — test: query with missing comp_id when backend=external_kb, quality_mode=conversational when Redis down, old endpoint after transition, invalid provider config, query_rewrite failure recovery
- [x] T050 Run quickstart.md validation — follow the migration guide in quickstart.md step by step against the running service

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 (protocols defined) — BLOCKS all user stories
- **US2 - Gateway (Phase 3)**: Depends on Phase 2 (consolidated config provides `LITELLM_PROVIDER`)
- **US1 - Unified Query (Phase 4)**: Depends on Phase 2 (strategies) AND Phase 3 (unified gateway)
- **US4 - API Surface (Phase 5)**: Depends on Phase 4 (3 capabilities registered in registry)
- **US3 - Config Polish (Phase 6)**: Depends on Phase 2 (config consolidation) — can run in parallel with Phase 3-5 for verification
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

```
Phase 1 (Setup)
    └── Phase 2 (Foundational: Config + Strategies)
         ├── Phase 3 / US2 (Gateway Consolidation)
         │    └── Phase 4 / US1 (Capability Consolidation) ← MVP
         │         └── Phase 5 / US4 (API Consolidation)
         └── Phase 6 / US3 (Config Polish) — parallel with Phases 3-5
              └── Phase 7 (Polish)
```

### Critical Path

```
T001-T005 → T006-T016 → T017-T023 → T024-T031 → T032-T042 → T050
```

### Within Each User Story

- Config tasks before strategy tasks (Phase 2)
- Strategy protocols before implementations (Phase 1 → Phase 2)
- Gateway consolidation before capability consolidation (Phase 3 → Phase 4)
- Capabilities before API routes (Phase 4 → Phase 5)

### Parallel Opportunities

**Phase 1** (all parallel): T002, T003, T004, T005
**Phase 2 Config** (3 parallel): T006, T007, T008 + T009
**Phase 2 Strategies** (5 parallel): T012, T013, T014, T015, T016
**Phase 4**: T028, T029 (ManagementCapability, TraceCapability) parallel with T024-T027 (QueryCapability)
**Phase 5**: T035, T036, T037 (trace/health/models endpoints) parallel with T032-T034 (query/document endpoints)
**Phase 5 Deprecation**: T038, T039, T040 all parallel (different files)
**Phase 7**: T047, T048, T049 all parallel

---

## Parallel Example: Phase 2 (Strategies)

```bash
# All strategy implementations can be built in parallel:
Task: "Implement MilvusRetrieval in src/rag_service/strategies/retrieval.py"
Task: "Implement ExternalKBRetrieval in src/rag_service/strategies/retrieval.py"
Task: "Implement BasicQuality in src/rag_service/strategies/quality.py"
Task: "Implement DimensionGatherQuality in src/rag_service/strategies/quality.py"
Task: "Implement ConversationalQuality in src/rag_service/strategies/quality.py"
```

## Parallel Example: Phase 4 (Capabilities)

```bash
# QueryCapability is on critical path, but these two can run in parallel:
Task: "Create ManagementCapability in src/rag_service/capabilities/management_capability.py"
Task: "Create TraceCapability in src/rag_service/capabilities/trace_capability.py"
```

---

## Implementation Strategy

### MVP First (Phases 1-4 only)

1. Complete Phase 1: Setup (protocols + schemas) — ~1 session
2. Complete Phase 2: Foundational (config + strategies) — ~2 sessions
3. Complete Phase 3: US2 - Gateway consolidation — ~1 session
4. Complete Phase 4: US1 - 3 unified capabilities — ~2 sessions
5. **STOP and VALIDATE**: Send queries through capabilities, verify all existing functionality works
6. Service is internally refactored but old API endpoints still work

### Full Delivery (All Phases)

1. MVP (Phases 1-4) → Internal architecture clean
2. Add Phase 5: US4 - Unified API surface → External API clean
3. Add Phase 6: US3 - Config polish → Deployment config clean
4. Add Phase 7: Polish → Documentation and edge cases
5. After transition period: delete deprecated files

### Task Count Summary

| Phase | Tasks | User Story |
|-------|-------|-----------|
| Phase 1: Setup | 5 | — |
| Phase 2: Foundational | 11 | — |
| Phase 3: US2 Gateway | 7 | US2 (P1) |
| Phase 4: US1 Capabilities | 8 | US1 (P1) |
| Phase 5: US4 API Surface | 11 | US4 (P2) |
| Phase 6: US3 Config | 4 | US3 (P2) |
| Phase 7: Polish | 4 | — |
| **Total** | **50** | |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Phase ordering follows spec.md assumption 6: Gateway → Capability → API → Config
- Old capabilities and routes are preserved during transition — only deleted in post-release cleanup
- No new Python libraries — all patterns use stdlib (`typing.Protocol`)
- All 006/007 data models (DimensionInfo, SessionState, BeliefState, etc.) are unchanged
- Three-layer observability stack is completely untouched
