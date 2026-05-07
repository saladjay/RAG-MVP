# Implementation Plan: RAG Service Architecture Refactoring

**Branch**: `008-rag-architecture-refactor` | **Date**: 2026-05-07 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/008-rag-architecture-refactor/spec.md`

## Summary

Consolidate RAG Service architecture from 13+ Capabilities → 3, 3 parallel Gateways → 1 LiteLLM entry point, 15+ API endpoints → 5, and 941 lines of config → ~300. Uses pure Python `typing.Protocol` for strategy pattern — no new libraries. Caller-facing API reduced to a single `POST /query` with sensible defaults.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI, LiteLLM, Pydantic, Pydantic Settings, Phidata, Langfuse SDK, Milvus, httpx
**Storage**: Milvus (vector DB), Redis (session state)
**Testing**: pytest, pytest-asyncio, pytest-cov
**Target Platform**: Linux/Windows server (uvicorn)
**Project Type**: Web service (FastAPI REST API)
**Performance Goals**: No performance regression — same latency as current
**Constraints**: No additional Python libraries; caller implementation as simple as possible
**Scale/Scope**: ~16 capability files, ~941 config lines, ~15 endpoints to consolidate

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Documentation Standards (Principle I & II)
- [x] All files will include header with content and API brief description
- [x] Documentation headers will be updated immediately on content changes
- [x] Call flow diagrams will be generated at `.specify/specs/008/research.md`
- [x] Architecture documentation will reference all APIs (document location → function name)

### Testing Standards (Principle III & IV)
- [x] Tests will use real implementations (minimal mocks)
- [x] Server tests will include server startup scripts
- [x] Python execution will use `uv`-managed virtual environment
- [x] Blocking points for real test implementation will be documented

### Component Governance (Principle V)
- [x] New base components have not been created without approval — reusing existing `Capability` base class and `typing.Protocol` (stdlib)
- [x] Existing base components are documented — `Capability[T, T]` ABC preserved, `CapabilityRegistry` preserved
- [x] Package management uses `uv` for Python dependencies — no new dependencies added

## Project Structure

### Documentation (this feature)

```text
specs/008-rag-architecture-refactor/
├── plan.md              # This file
├── research.md          # Phase 0 — design decisions and call flow diagrams
├── data-model.md        # Phase 1 — entity models and strategy interfaces
├── quickstart.md        # Phase 1 — migration guide for callers
├── contracts/
│   └── api.md           # Phase 1 — unified API contract
└── tasks.md             # Phase 2 (via /speckit.tasks)
```

### Source Code (repository root)

```text
src/rag_service/
│
├── main.py                          # MODIFY: register 3 capabilities, include unified router
├── config.py                        # MODIFY: consolidate to 5 config classes (~300 lines)
│
├── api/
│   ├── unified_routes.py            # CREATE: 5 unified endpoints
│   ├── unified_schemas.py           # CREATE: unified request/response models
│   ├── routes.py                    # DEPRECATE: add deprecation headers to old endpoints
│   ├── qa_routes.py                 # DEPRECATE: add deprecation notice
│   ├── qa_schemas.py                # KEEP: schemas referenced by unified_schemas
│   ├── schemas.py                   # KEEP: schemas referenced by unified_schemas
│   └── kb_upload_routes.py          # DEPRECATE: add deprecation notice
│
├── capabilities/
│   ├── base.py                      # KEEP: Capability ABC + CapabilityRegistry (unchanged)
│   ├── query_capability.py          # CREATE: unified QueryCapability
│   ├── management_capability.py     # CREATE: unified ManagementCapability
│   ├── trace_capability.py          # CREATE: unified TraceCapability
│   ├── knowledge_query.py           # DEPRECATE → logic moves to MilvusRetrieval strategy
│   ├── external_kb_query.py         # DEPRECATE → logic moves to ExternalKBRetrieval strategy
│   ├── qa_pipeline.py               # DEPRECATE → logic moves to QueryCapability
│   ├── query_quality.py             # DEPRECATE → logic moves to DimensionGatherQuality strategy
│   ├── conversational_query.py      # DEPRECATE → logic moves to ConversationalQuality strategy
│   ├── document_management.py       # DEPRECATE → logic moves to ManagementCapability
│   ├── milvus_kb_upload.py          # DEPRECATE → logic moves to ManagementCapability
│   ├── model_discovery.py           # DEPRECATE → logic moves to ManagementCapability
│   ├── model_inference.py           # DEPRECATE → logic moves to LiteLLMGateway
│   ├── trace_observation.py         # DEPRECATE → logic moves to TraceCapability
│   ├── health_check.py              # DEPRECATE → logic moves to TraceCapability
│   ├── query_rewrite.py             # DEPRECATE → logic moves to QueryCapability internal
│   ├── hallucination_detection.py   # DEPRECATE → logic moves to QueryCapability internal
│   └── milvus_kb_query.py           # DEPRECATE → logic moves to MilvusRetrieval strategy
│
├── strategies/                      # CREATE: strategy implementations
│   ├── __init__.py
│   ├── retrieval.py                 # RetrievalStrategy protocol + MilvusRetrieval + ExternalKBRetrieval
│   └── quality.py                   # QualityStrategy protocol + BasicQuality + DimensionGatherQuality + ConversationalQuality
│
├── inference/
│   └── gateway.py                   # MODIFY: merge HTTP/GLM as internal LiteLLM providers
│
├── core/                            # KEEP: unchanged
├── observability/                   # KEEP: unchanged (three-layer stack)
├── retrieval/                       # KEEP: unchanged (Milvus, embeddings)
├── services/                        # KEEP: unchanged (session_store, belief_state_store, etc.)
├── models/                          # KEEP: unchanged (006/007 data models)
└── clients/                         # KEEP: unchanged (external_kb_client)
```

**Structure Decision**: Single project, modifying existing `src/rag_service/`. New `strategies/` subdirectory for Protocol-based strategy implementations. All existing files preserved during transition with deprecation notices.

## Implementation Phases

### Phase 1: Gateway Consolidation (Lowest Risk)

Merge HTTPCompletionGateway and GLMCompletionGateway into LiteLLMGateway as internal providers.

**Files**: `inference/gateway.py`, `config.py` (LiteLLM section only)
**Risk**: Low — internal change, no API impact
**Test**: Configure different providers, verify all inference goes through LiteLLM

### Phase 2: Config Consolidation

Merge 16 config classes into 5 with backward-compatible env var mapping.

**Files**: `config.py`
**Risk**: Medium — env var changes affect deployments
**Test**: Start service with old env vars, verify deprecation warnings and correct mapping

### Phase 3: Strategy Layer

Create Protocol-based strategy interfaces and move existing logic into strategy implementations.

**Files**: New `strategies/` directory
**Risk**: Low — additive, doesn't change existing code
**Test**: Unit tests for each strategy using existing test data

### Phase 4: Capability Consolidation

Create 3 unified capabilities (Query, Management, Trace) that use strategies internally.

**Files**: New capability files in `capabilities/`
**Risk**: Medium — integrates all previous phases
**Test**: Functional tests against existing test cases

### Phase 5: API Consolidation

Create unified router with 5 endpoints. Add deprecation headers to old endpoints.

**Files**: New `api/unified_routes.py`, `api/unified_schemas.py`, modify `main.py`
**Risk**: Medium — externally visible change
**Test**: Update E2E test RAGClient to use new endpoints, verify all tests pass

### Phase 6: Cleanup

Remove deprecated capabilities and routes after transition period.

**Files**: Delete deprecated files
**Risk**: Low — cleanup only
**Test**: Full regression test suite

## Complexity Tracking

> No constitution violations — all changes use existing dependencies and patterns.

| Aspect | Justification |
|--------|--------------|
| New `strategies/` directory | Minimal addition — uses `typing.Protocol` (stdlib), no new libraries |
| Unified request/response schemas | Reduces from 3+ schema files to 2, simplifying the API surface |
