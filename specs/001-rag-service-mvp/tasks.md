# Tasks: RAG Service MVP - AI Component Validation Platform

**Input**: Design documents from `/specs/001-rag-service-mvp/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/
**User Requirements**:
1. Determine stable component versions and manage Python packages with uv
2. **CORE ARCHITECTURE**: Unified capability interface layer - components NEVER directly exposed to HTTP endpoints

**Tests**: Tests are MANDATORY per constitution (Principle III). Use real implementations, minimize mocks. Each node/implementation must have complete unit tests.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

**Constitution Compliance**:
- All implementation tasks must include documentation headers (Principle I)
- Testing tasks must use real implementations (Principle III)
- Python tasks must use `uv` environment (Principle IV)

---

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, dependency resolution, and basic structure

- [X] T001 Determine stable component versions and create pyproject.toml in project root
- [X] T002 Initialize uv virtual environment and install dependencies using uv
- [X] T003 [P] Create src/rag_service/ package structure per implementation plan
- [X] T004 [P] Create tests/ directory structure with unit/, integration/, contract/ subdirectories
- [X] T005 [P] Configure pytest with pytest.ini for test discovery and async support
- [X] T006 [P] Create tests/conftest.py with shared fixtures for server startup and real service instances
- [X] T007 [P] Setup .env.example file with all required environment variables
- [X] T008 [P] Create docker-compose.yml for Milvus and optional local services
- [X] T009 [P] Create .gitignore for Python, uv, and IDE files
- [X] T010 [P] Create README.md with quick reference to quickstart.md

**Status**: COMPLETE

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Configuration & Core

- [X] T011 Create src/rag_service/config.py with environment variable loading and validation
- [X] T012 [P] Create src/rag_service/core/exceptions.py with custom exception classes

### Logging Framework (Global Foundation)

- [X] T012a [P] Create src/rag_service/core/logger.py with structured logging configuration using Python logging
- [X] T012b [P] Implement log level configuration via environment variable (LOG_LEVEL=DEBUG/INFO/WARNING/ERROR)
- [X] T012c [P] Create custom log formatters with trace_id injection for request correlation
- [X] T012d [P] Implement log handlers: console handler with colors, file handler with rotation (optional)
- [X] T012e [P] Create structured log context builder with request_id, trace_id, user_id, session_id fields
- [X] T012f [P] Implement lazy loading of logger instances (get_logger pattern) for all modules
- [X] T012g [P] Create src/rag_service/core/logging_config.py with logging setup for FastAPI/uvicorn integration
- [X] T012h [P] Add request-scoped logging middleware for trace_id injection into all log records
- [X] T012i [P] Implement non-blocking logging to prevent log failures from blocking requests
- [X] T012j [P] Create unit test for logging framework in tests/unit/test_logger.py

### Capability Interface Layer (CORE ARCHITECTURE)

**Purpose**: Unified interface layer between HTTP endpoints and components. Components are NEVER directly exposed to API layer.

- [X] T012k [P] Create src/rag_service/capabilities/ directory structure with __init__.py
- [X] T012l [P] Create src/rag_service/capabilities/base.py with abstract Capability class (execute, validate_input methods)
- [X] T012m [P] Create src/rag_service/capabilities/knowledge_query.py with KnowledgeQueryCapability (wraps Milvus)
- [X] T012n [P] Create src/rag_service/capabilities/model_inference.py with ModelInferenceCapability (wraps LiteLLM)
- [X] T012o [P] Create src/rag_service/capabilities/trace_observation.py with TraceObservationCapability (wraps Langfuse/Phidata)
- [X] T012p [P] Create src/rag_service/capabilities/document_management.py with DocumentManagementCapability (wraps Milvus)
- [X] T012q [P] Create src/rag_service/capabilities/model_discovery.py with ModelDiscoveryCapability (wraps LiteLLM)
- [X] T012r [P] Create src/rag_service/capabilities/health_check.py with HealthCheckCapability (checks all components)
- [X] T012s Implement capability registration in src/rag_service/main.py (app.capabilities dict)
- [X] T012t [P] Create unit tests for all capabilities in tests/unit/test_capabilities.py

**Checkpoint**: Capability interface layer complete - API routes can now interact with components through unified interfaces

### Observability Foundation (All 3 Layers)

- [X] T036 [P] Create src/rag_service/observability/trace_manager.py with unified trace_id generation and propagation
- [X] T037 [P] Create src/rag_service/observability/langfuse_client.py (Prompt Layer) with async trace capture
- [X] T038 [P] Create src/rag_service/observability/litellm_observer.py (LLM Layer) with cost/performance/routing metrics
- [X] T039 [P] Create src/rag_service/observability/phidata_observer.py (Agent Layer) with execution/reasoning metrics
- [X] T040 Implement unified trace_id propagation across Phidata → CrewAI → LiteLLM layers
- [X] T041 Implement non-blocking trace flush to prevent observability failures from blocking requests

### API Foundation

- [X] T042 Create src/rag_service/main.py with FastAPI app initialization and lifecycle management
- [X] T043 [P] Create src/rag_service/api/schemas.py with Pydantic models for request/response
- [X] T044 [P] Create src/rag_service/api/routes.py with /health and /models endpoints (ONLY uses capabilities, NOT components directly)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

**Status**: COMPLETE

---

## Phase 3: User Story 1 - Knowledge Base Query (Priority: P1) 🎯 MVP

**Goal**: Query knowledge base via HTTP POST and receive AI-generated answers with retrieved context

**Independent Test**: Send POST /ai/agent with question → receive response with answer + retrieved chunks + trace_id

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T045 [P] [US1] Write contract test for /ai/agent endpoint in tests/contract/test_api_contract.py
- [X] T046 [P] [US1] Write integration test for knowledge base query flow in tests/integration/test_e2e_flow.py
- [X] T047 [P] [US1] Write unit test for knowledge base retrieval in tests/unit/test_knowledge_base.py
- [X] T048 [P] [US1] Write unit test for agent orchestration in tests/unit/test_agent.py
- [X] T049 [P] [US1] Write unit test for unified trace propagation in tests/unit/test_unified_trace.py

### Implementation for User Story 1

- [X] T050 [P] [US1] Create src/rag_service/retrieval/embeddings.py with OpenAI embedding service
- [X] T051 [P] [US1] Create src/rag_service/retrieval/knowledge_base.py with Milvus client and search methods
- [X] T052 [US1] Implement knowledge base connection pooling in Milvus client
- [X] T053 [P] [US1] Create src/rag_service/inference/gateway.py with LiteLLM client integration
- [X] T054 [P] [US1] Create src/rag_service/inference/models.py with model provider configuration classes
- [X] T055 [US1] Implement /ai/agent POST endpoint in src/rag_service/api/routes.py using capabilities (depends on T040-T044)
- [X] T056 [US1] Create src/rag_service/core/agent.py with Phidata agent orchestration and tool definitions
- [X] T057 [US1] Implement retrieval tool for Phidata agent (depends on T041)
- [X] T058 [US1] Implement LLM inference tool for Phidata agent (depends on T043)
- [X] T059 [US1] Wire unified trace_id through agent execution flow (Phidata → LiteLLM)
- [X] T060 [US1] Implement error handling for no-retrieval-results scenario
- [X] T061 [US1] Add logging for knowledge base query operations

**Checkpoint**: User Story 1 complete - can query knowledge base and get AI answers with trace correlation ✅

---

## Phase 4: User Story 2 - Multi-Model Inference (Priority: P2)

**Goal**: Validate multiple AI models through unified LiteLLM gateway without changing client code

**Independent Test**: Configure Ollama/OpenAI/Claude → make requests → verify routing to correct provider

### Tests for User Story 2

- [X] T062 [P] [US2] Write contract test for LiteLLM gateway routing in tests/contract/test_litellm_contract.py
- [X] T063 [P] [US2] Write integration test for multi-provider model selection in tests/integration/test_e2e_flow.py
- [X] T064 [P] [US2] Write unit test for gateway provider selection in tests/unit/test_gateway.py

### Implementation for User Story 2

- [X] T065 [P] [US2] Create litellm_config.yaml for multi-provider configuration in project root
- [X] T066 [US2] Add vLLM provider configuration to litellm_config.yaml
- [X] T067 [US2] Add SGLang provider configuration to litellm_config.yaml
- [X] T068 [US2] Implement model provider switching logic in src/rag_service/inference/gateway.py
- [X] T069 [US2] Implement fallback chain configuration for provider failures
- [X] T070 [US2] Add model hint parameter support to /ai/agent endpoint
- [X] T071 [US2] Update GET /models endpoint to return available providers with availability status
- [X] T072 [US2] Integrate provider selection with unified trace_id capture

**Checkpoint**: User Stories 1 AND 2 both work - can query with multiple models ✅

---

## Phase 5: User Story 3 - Observability and Tracing (Priority: P3)

**Goal**: Complete three-layer observability with cross-layer trace correlation for optimization

**Independent Test**: Make query → retrieve trace by ID → verify all layer metrics (Phidata, LiteLLM, Langfuse)

### Tests for User Story 3

- [X] T073 [P] [US3] Write contract test for Langfuse integration in tests/contract/test_langfuse_contract.py
- [X] T074 [P] [US3] Write integration test for cross-layer trace correlation in tests/integration/test_trace_correlation.py
- [X] T075 [P] [US3] Write unit test for Phidata observer in tests/unit/test_phidata_observer.py
- [X] T076 [P] [US3] Write unit test for LiteLLM observer in tests/unit/test_litellm_observer.py
- [X] T077 [P] [US3] Write unit test for Langfuse client in tests/unit/test_langfuse_client.py

### Implementation for User Story 3

- [X] T078 [P] [US3] Implement trace retrieval endpoint GET /traces/{trace_id} in src/rag_service/api/routes.py using TraceObservationCapability
- [X] T079 [P] [US3] Add span creation for each processing stage in src/rag_service/observability/langfuse_client.py
- [X] T080 [US3] Implement cost aggregation (per-request, per-user, per-scenario) in src/rag_service/observability/litellm_observer.py
- [X] T081 [P] [US3] Implement routing decision capture in src/rag_service/observability/litellm_observer.py
- [X] T082 [P] [US3] Implement tool call tracking in src/rag_service/observability/phidata_observer.py
- [X] T083 [P] [US3] Implement reasoning path capture in src/rag_service/observability/phidata_observer.py
- [X] T084 [US3] Implement prompt version tracking in src/rag_service/observability/langfuse_client.py
- [X] T085 [US3] Implement retrieved docs injection tracking in src/rag_service/observability/langfuse_client.py
- [X] T086 [US3] Add GET /observability/metrics endpoint with aggregated cross-layer metrics
- [X] T087 [US3] Implement background trace flush with error handling

**Checkpoint**: User Stories 1, 2, AND 3 all work - complete observability with optimization loop ✅

---

## Phase 6: User Story 4 - Knowledge Base Management (Priority: P4)

**Goal**: Add, update, remove documents from knowledge base

**Independent Test**: Upload document → verify indexed → query returns new content

### Tests for User Story 4

- [X] T088 [P] [US4] Write contract test for Milvus document operations in tests/contract/test_milvus_contract.py
- [X] T089 [P] [US4] Write integration test for document lifecycle in tests/integration/test_e2e_flow.py
- [X] T090 [P] [US4] Write unit test for document indexing in tests/unit/test_knowledge_base.py

### Implementation for User Story 4

- [X] T091 [P] [US4] Implement document upload endpoint POST /documents in src/rag_service/api/routes.py using DocumentManagementCapability
- [X] T092 [P] [US4] Implement document deletion endpoint DELETE /documents/{doc_id} in src/rag_service/api/routes.py using DocumentManagementCapability
- [X] T093 [US4] Implement document update endpoint PUT /documents/{doc_id} in src/rag_service/api/routes.py using DocumentManagementCapability
- [X] T094 [US4] Implement document indexing with embedding generation in src/rag_service/retrieval/knowledge_base.py
- [X] T095 [US4] Implement document re-indexing on update
- [X] T096 [US4] Add document management operations to trace recording

**Checkpoint**: All 4 user stories complete - full RAG service with observability and document management ✅

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [X] T097 [P] Add comprehensive documentation headers to all source files (Principle I)
- [X] T098 [P] Run pytest with --cov to verify 80%+ test coverage (Principle III)
- [X] T099 [P] Add type hints to all function signatures in src/rag_service/
- [X] T100 Implement request timeout handling at each processing stage
- [X] T101 [P] Create run_tests.sh script for server startup and test execution
- [X] T102 [P] Performance test: verify <10s response time with 10 concurrent requests
- [X] T103 [P] Security review: validate all inputs and sanitize error messages
- [X] T104 Verify capability layer properly abstracts all components (no direct component access from API)
- [X] T105 Run quickstart.md validation to ensure setup works in 15 minutes

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3 → P4)
- **Polish (Phase 7)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Extends US1 with multi-model routing
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Enhances observability across all stories
- **User Story 4 (P4)**: Can start after Foundational (Phase 2) - Adds document management, independent of US1-US3

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models/Components before services
- Services before endpoints
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- Once Foundational phase completes, all user stories can start in parallel (if team capacity allows)
- All tests for a user story marked [P] can run in parallel
- Models/components within a story marked [P] can run in parallel
- Different user stories can be worked on in parallel by different team members

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task T045: Contract test for /ai/agent endpoint
Task T046: Integration test for knowledge base query flow
Task T047: Unit test for knowledge base retrieval
Task T048: Unit test for agent orchestration
Task T049: Unit test for unified trace propagation

# Launch all retrieval/inference components together:
Task T050: Embedding service
Task T051: Knowledge base client
Task T053: LiteLLM gateway
Task T054: Model provider configurations
```

## Parallel Example: Capability Layer (Phase 2 - CORE ARCHITECTURE)

```bash
# Launch all capability interface components together:
Task T012k: Create capabilities/ directory structure
Task T012l: Create base Capability abstract class
Task T012m: Create KnowledgeQueryCapability
Task T012n: Create ModelInferenceCapability
Task T012o: Create TraceObservationCapability
Task T012p: Create DocumentManagementCapability
Task T012q: Create ModelDiscoveryCapability
Task T012r: Create HealthCheckCapability
# Note: T012s (capability registration) must wait until components exist
# T012t (unit tests) can run in parallel with capability implementations
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo
4. Add User Story 3 → Test independently → Deploy/Demo
5. Add User Story 4 → Test independently → Deploy/Demo
6. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (Knowledge Base Query)
   - Developer B: User Story 2 (Multi-Model Inference)
   - Developer C: User Story 3 (Observability & Tracing)
3. Stories complete and integrate independently
4. Developer D: User Story 4 (Knowledge Base Management) - can start anytime after Foundational

---

## Component Version Resolution (User Requirement)

### Stable Component Versions to Determine

The following component versions must be validated for compatibility:

| Component | Purpose | Stable Version Strategy |
|-----------|---------|--------------------------|
| Python | Runtime | 3.11.x (latest 3.11) |
| FastAPI | Web framework | Latest stable 0.110+ |
| Phidata | Agent orchestration | Latest compatible with FastAPI |
| LiteLLM | Model gateway | Latest 1.0+ with provider support |
| Langfuse | Observability (Prompt Layer) | Latest 2.x Python SDK |
| pymilvus | Knowledge base | 2.3.x with connection pooling |
| pytest | Testing | Latest with pytest-asyncio support |
| uvicorn | ASGI server | Latest compatible with FastAPI |

### Setup Tasks (T001-T002) Detail

**T001: Determine stable component versions**
- Research compatibility matrix between FastAPI, Phidata, LiteLLM, Langfuse
- Test Python 3.11 compatibility with all components
- Pin specific versions in pyproject.toml after validation
- Document any known compatibility issues in research.md

**T002: Initialize uv environment**
- Create uv venv: `uv venv`
- Activate and install: `source .venv/bin/activate && uv pip install -e .`
- Verify all imports work: `python -c "import fastapi, phidata, litellm, langfuse, pymilvus"`
- Lock versions: `uv lock` to generate uv.lock file

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence

---

## Task Summary

- **Total Tasks**: 105
- **Tasks per User Story**:
  - US1 (Knowledge Base Query): 17 tasks (T045-T061) ✅ COMPLETE
  - US2 (Multi-Model Inference): 11 tasks (T062-T072) ✅ COMPLETE
  - US3 (Observability): 15 tasks (T073-T087) ✅ COMPLETE
  - US4 (KB Management): 9 tasks (T088-T096) ✅ COMPLETE
- **Setup Tasks**: 10 tasks (T001-T010) ✅ COMPLETE
- **Foundational Tasks**: 34 tasks (T011-T044) ✅ COMPLETE
  - Configuration & Core: 2 tasks (T011-T012) ✅ COMPLETE
  - Logging Framework: 10 tasks (T012a-T012j) ✅ COMPLETE
  - Capability Interface Layer: 10 tasks (T012k-T012t) ✅ COMPLETE
  - Observability Foundation: 6 tasks (T036-T041) ✅ COMPLETE
  - API Foundation: 3 tasks (T042-T044) ✅ COMPLETE
- **Polish Tasks**: 9 tasks (T097-T105) ✅ COMPLETE

### Progress: 105/105 tasks complete (100%) ✅

## Implementation Complete!

The RAG Service MVP is now fully implemented with:
- ✅ Knowledge base query with AI-generated answers
- ✅ Multi-model inference via LiteLLM gateway
- ✅ Three-layer observability (Phidata, LiteLLM, Langfuse)
- ✅ Document management (upload, update, delete)
- ✅ Cross-cutting concerns (documentation, testing, security)

**Next Steps:**
1. Run `uv run uvicorn rag_service.main:app` to start the service
2. Access http://localhost:8000/docs for API documentation
3. Test the `/ai/agent` endpoint with sample queries
4. Configure environment variables for Milvus, OpenAI/Anthropic API keys
5. Monitor observability via `/traces/{trace_id}` and `/observability/metrics`

### Parallel Opportunities Identified

- **Setup Phase**: 8/10 tasks can run in parallel
- **Foundational Phase**:
  - Logging Framework: 10/10 tasks can run in parallel
  - Capability Layer: 9/10 tasks can run in parallel (T012s depends on components)
  - Observability Foundation: 5/6 tasks can run in parallel
  - API Foundation: 2/3 tasks can run in parallel
- **User Story 1**: 5/6 tests and 4/6 components can run in parallel
- **User Story 2**: 3/3 tests can run in parallel
- **User Story 3**: 5/5 tests can run in parallel
- **User Story 4**: 3/3 tests can run in parallel

### MVP Scope Recommendation

**MVP = Phase 1 + Phase 2 + Phase 3 (User Story 1)**

This delivers:
- Working RAG service with knowledge base queries
- AI-generated answers with retrieved context
- **Unified capability interface layer** (components never exposed directly)
- Basic observability with unified trace_id
- Complete test coverage for core functionality

**Estimated Effort**: ~52 tasks (Setup + Foundational + US1)
**Critical Note**: Capability Interface Layer (T012k-T012t) is CORE architecture - MUST be completed before any user story implementation
