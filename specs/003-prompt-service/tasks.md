# Tasks: Prompt Management Service

**Input**: Design documents from `/specs/003-prompt-service/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

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

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root
- Paths shown below match the structure defined in plan.md

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create project directory structure src/prompt_service/ with subdirectories: core/, models/, services/, api/, middleware/, client/
- [X] T002 Initialize pyproject.toml with uv-managed dependencies: fastapi, uvicorn, pydantic, pydantic-settings, langfuse, jinja2, cachetools, httpx, python-json-logger, pytest, pytest-asyncio
- [X] T003 [P] Create .gitignore with Python patterns: __pycache__/, *.pyc, .venv/, .env, dist/, *.egg-info/
- [X] T004 [P] Create pytest.ini with test discovery and async configuration
- [X] T005 [P] Create Dockerfile for containerized deployment

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T006 Create configuration management in src/prompt_service/config.py with Pydantic settings for Langfuse (host, public_key, secret_key), cache (enabled, ttl), service (port, log_level)
- [X] T007 [P] Create exception hierarchy in src/prompt_service/core/exceptions.py: PromptServiceError base, PromptNotFoundError, PromptValidationError, PromptServiceUnavailableError, ABTestNotFoundError
- [X] T008 [P] Create structured logger in src/prompt_service/core/logger.py with trace_id injection via ContextVar, JSON formatter
- [X] T009 [P] Create base data models in src/prompt_service/models/prompt.py: StructuredSection, VariableDef, PromptTemplate
- [X] T010 [P] Create Langfuse client wrapper in src/prompt_service/services/langfuse_client.py with connection handling, graceful degradation, get_prompt(), create_prompt(), update_prompt()
- [X] T011 Create FastAPI application in src/prompt_service/main.py with lifespan context manager for Langfuse client initialization, CORS middleware, health check endpoint at /health
- [X] T012 [P] Create base API schemas in src/prompt_service/api/schemas.py: HealthResponse, ErrorResponse
- [X] T013 [P] Create caching middleware in src/prompt_service/middleware/cache.py with LRU cache (cachetools), cache_key generation, invalidation logic

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Prompt Retrieval Middleware (Priority: P1) 🎯 MVP

**Goal**: Business code can retrieve prompts via simple interface without direct Langfuse dependency

**Independent Test**: Call GET /api/v1/prompts/{template_id}/retrieve with variables, verify rendered prompt content matches expected active version

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T014 [P] [US1] Contract test for prompt retrieval in tests/contract/test_prompt_retrieval.py: test retrieve with template_id returns active version, test retrieve with variables interpolates correctly, test retrieve with missing template returns 404
- [X] T015 [P] [US1] Integration test for prompt retrieval in tests/integration/test_prompt_retrieval_e2e.py: test full retrieve flow with mock Langfuse, test graceful degradation when Langfuse unavailable

### Implementation for User Story 1

- [X] T016 [P] [US1] Create PromptAssemblyService in src/prompt_service/services/prompt_assembly.py with assemble_prompt() method: render structured sections, inject context section, format retrieved_docs section, Jinja2 template rendering with StrictUndefined
- [X] T017 [P] [US1] Create PromptRetrievalService in src/prompt_service/services/prompt_retrieval.py with execute() method: check L1 cache, load template from LangfuseClient, assemble via PromptAssemblyService, return PromptResponse
- [X] T018 [US1] Create API request/response schemas in src/prompt_service/api/schemas.py: PromptRetrieveRequest, PromptRetrieveResponse, Section, RetrievedDoc
- [X] T019 [US1] Implement POST /api/v1/prompts/{template_id}/retrieve endpoint in src/prompt_service/api/routes.py: validate input, call PromptRetrievalService, handle errors with proper status codes
- [X] T020 [US1] Add cache integration in PromptRetrievalService: cache rendered prompts, invalidate on changes, return cached responses with from_cache flag

**Checkpoint**: At this point, User Story 1 should be fully functional - business code can retrieve prompts without direct Langfuse dependency

---

## Phase 4: User Story 2 - Online Prompt Editing (Priority: P1)

**Goal**: Product managers can update prompt templates without deployment

**Independent Test**: Create a prompt via API, retrieve it, update it via API, retrieve again and verify new content is returned

### Tests for User Story 2

- [X] T021 [P] [US2] Contract test for prompt management in tests/contract/test_prompt_management.py: test create prompt returns 201, test update prompt creates new version, test delete prompt soft-deletes
- [X] T022 [P] [US2] Integration test for prompt editing in tests/integration/test_prompt_editing_e2e.py: test edit-publish-retrieve flow, test concurrent edit handling

### Implementation for User Story 2

- [X] T023 [P] [US2] Create PromptManagementService in src/prompt_service/services/prompt_management.py with create(), update(), delete(), list() methods, validate sections and variables, call LangfuseClient operations
- [X] T024 [P] [US2] Create API schemas in src/prompt_service/api/schemas.py: PromptCreateRequest, PromptUpdateRequest, PromptListResponse, PromptInfoResponse
- [X] T025 [US2] Implement GET /api/v1/prompts endpoint in src/prompt_service/api/routes.py: pagination support, tag filtering, search functionality
- [X] T026 [US2] Implement POST /api/v1/prompts endpoint in src/prompt_service/api/routes.py: validate template_id format, create via PromptManagementService, return 201 with version info
- [X] T027 [US2] Implement PUT /api/v1/prompts/{template_id} endpoint in src/prompt_service/api/routes.py: validate change_description, create new version, invalidate cache for template_id
- [X] T028 [US2] Implement DELETE /api/v1/prompts/{template_id} endpoint in src/prompt_service/api/routes.py: soft delete via PromptManagementService
- [X] T029 [US2] Add cache invalidation in PromptManagementService: publish cache invalidation event after update, invalidate L1 cache locally

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently - prompts can be retrieved and edited online

---

## Phase 5: User Story 3 - A/B Testing for Prompts (Priority: P2)

**Goal**: Data scientists can compare prompt variants with traffic split and metrics

**Independent Test**: Create A/B test with two variants, make multiple requests, verify traffic distribution matches split percentage

### Tests for User Story 3

- [X] T030 [P] [US3] Contract test for A/B testing in tests/contract/test_ab_testing.py: test create AB test validates traffic split, test retrieve AB test returns metrics
- [X] T031 [P] [US3] Integration test for A/B test routing in tests/integration/test_ab_testing_e2e.py: test deterministic variant assignment, test metrics tracking

### Implementation for User Story 3

- [X] T032 [P] [US3] Create ABTest and PromptVariant models in src/prompt_service/models/ab_test.py with traffic_percentage, impressions, successes, status fields
- [X] T033 [P] [US3] Create ABTestingService in src/prompt_service/services/ab_testing.py with create_test(), assign_variant(), record_impression(), record_success(), get_results(), select_winner() methods
- [X] T034 [US3] Implement deterministic variant routing in ABTestingService.assign_variant(): hash(user_id + test_id), bucket selection based on traffic_percentage, consistent assignment
- [X] T035 [P] [US3] Create API schemas in src/prompt_service/api/schemas.py: ABTestCreateRequest, ABTestResponse, ABTestResultsResponse, SelectWinnerRequest
- [X] T036 [US3] Implement POST /api/v1/ab-tests endpoint in src/prompt_service/api/routes.py: validate traffic percentages sum to 100, create via ABTestingService
- [X] T037 [US3] Implement GET /api/v1/ab-tests endpoint in src/prompt_service/api/routes.py: list all tests, filter by status and template_id
- [X] T038 [US3] Implement GET /api/v1/ab-tests/{test_id} endpoint in src/prompt_service/api/routes.py: return detailed results with metrics per variant
- [X] T039 [US3] Implement POST /api/v1/ab-tests/{test_id}/winner endpoint in src/prompt_service/api/routes.py: select winning variant, create new prompt version, archive test
- [X] T040 [US3] Integrate A/B test routing into PromptRetrievalService: check for active AB test, call ABTestingService.assign_variant(), return variant_id in response

**Checkpoint**: All user stories 1-3 should now be independently functional - A/B tests can route traffic and track metrics

---

## Phase 6: User Story 4 - Trace Analysis and Insights (Priority: P3)

**Goal**: Product analysts can view aggregate metrics and identify patterns in prompt performance

**Independent Test**: Execute prompts with known outcomes, view analytics endpoint, verify metrics and patterns are correctly displayed

### Tests for User Story 4

- [X] T041 [P] [US4] Contract test for analytics in tests/contract/test_analytics.py: test analytics returns aggregate metrics, test trace search filters correctly
- [X] T042 [P] [US4] Integration test for trace analysis in tests/integration/test_trace_analysis_e2e.py: test metrics aggregation, test error pattern detection

### Implementation for User Story 4

- [X] T043 [P] [US4] Create TraceRecord and EvaluationMetrics models in src/prompt_service/models/trace.py with trace_id, template_id, variant_id, input_variables, success, latency_ms fields
- [X] T044 [P] [US4] Create TraceAnalysisService in src/prompt_service/services/trace_analysis.py with get_insights(), search_traces(), aggregate_metrics() methods, in-memory aggregation for recent traces
- [X] T045 [US4] Implement metrics calculation in TraceAnalysisService: usage count, error rate, latency percentiles (p50, p95, p99), variant comparison
- [X] T046 [P] [US4] Create API schemas in src/prompt_service/api/schemas.py: AnalyticsResponse, TraceSearchResponse, MetricsSummary
- [X] T047 [US4] Implement GET /api/v1/analytics/prompts/{template_id} endpoint in src/prompt_service/api/routes.py: date range filtering, include AB test results if active
- [X] T048 [US4] Implement GET /api/v1/analytics/traces endpoint in src/prompt_service/api/routes.py: filtering by template_id, variant_id, date range, pagination
- [X] T049 [US4] Add trace logging in PromptRetrievalService: create TraceRecord for each retrieval, link to version and variant, store in Langfuse via LangfuseClient

**Checkpoint**: All user stories 1-4 should now be independently functional - trace data provides insights for optimization

---

## Phase 7: User Story 5 - Prompt Versioning and Rollback (Priority: P4)

**Goal**: Developers can view version history and rollback to previous versions

**Independent Test**: Create multiple prompt versions, rollback to previous version, retrieve prompt and verify old content is returned

### Tests for User Story 5

- [X] T050 [P] [US5] Contract test for versioning in tests/contract/test_versioning.py: test version history returns all versions, test rollback creates new version from old content
- [X] T051 [P] [US5] Integration test for rollback in tests/integration/test_rollback_e2e.py: test rollback restores previous content, test audit log records rollback action

### Implementation for User Story 5

- [X] T052 [P] [US5] Create VersionHistory model in src/prompt_service/models/prompt.py with version, change_description, changed_by, content_snapshot, can_rollback fields
- [X] T053 [P] [US5] Create VersionControlService in src/prompt_service/services/version_control.py with get_history(), rollback(), create_version_snapshot() methods
- [X] T054 [P] [US5] Create API schemas in src/prompt_service/api/schemas.py: VersionHistoryResponse, RollbackRequest, RollbackResponse
- [X] T055 [US5] Implement GET /api/v1/prompts/{template_id}/versions endpoint in src/prompt_service/api/routes.py: return chronological version history with pagination
- [X] T056 [US5] Implement POST /api/v1/prompts/{template_id}/rollback endpoint in src/prompt_service/api/routes.py: validate target version exists, restore content snapshot, create new version, invalidate cache
- [X] T057 [US5] Integrate version tracking in PromptManagementService: create VersionHistory snapshot on each update, include change_description

**Checkpoint**: All user stories 1-5 should now be independently functional - complete prompt management with versioning safety

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Client SDK, documentation, validation, and deployment readiness

- [X] T058 [P] Create Python client SDK in src/prompt_service/client/sdk.py: PromptClient class with get_prompt(), list_prompts(), get_prompt_info() methods, httpx for async HTTP, retry logic, fallback handling
- [X] T059 [P] Create SDK exceptions in src/prompt_service/client/exceptions.py: PromptServiceError, PromptNotFoundError, PromptValidationError, PromptServiceUnavailableError
- [X] T060 [P] Create SDK dataclasses in src/prompt_service/client/models.py: PromptResponse, PromptOptions, PromptInfo, Section
- [X] T061 Create package __init__.py files for all modules: src/prompt_service/__init__.py, src/prompt_service/core/__init__.py, src/prompt_service/models/__init__.py, src/prompt_service/services/__init__.py, src/prompt_service/api/__init__.py, src/prompt_service/middleware/__init__.py, src/prompt_service/client/__init__.py
- [X] T062 [P] Create conftest.py in tests/unit/conftest.py with shared fixtures: mock_langfuse_client, test_prompt_template, test_ab_test, test_trace_record
- [X] T063 [P] Create server startup fixture in tests/integration/conftest.py with test FastAPI app, test database cleanup
- [X] T064 [P] Add unit tests for PromptAssemblyService in tests/unit/test_prompt_assembly.py: test section rendering, test Jinja2 interpolation, test context injection, test retrieved_docs formatting
- [X] T065 [P] Add unit tests for ABTestingService in tests/unit/test_ab_testing.py: test deterministic routing, test traffic distribution, test metrics tracking
- [X] T066 [P] Add unit tests for TraceAnalysisService in tests/unit/test_trace_analysis.py: test metrics aggregation, test percentile calculation
- [X] T067 Add comprehensive documentation headers to all modules per Principle I: update all files with module docstrings describing purpose and API brief
- [X] T068 [P] Update README.md in repository root with quickstart instructions, API endpoint documentation, SDK usage examples
- [X] T069 [P] Create deployment documentation in docs/deployment.md: Docker build steps, environment variables, health check configuration
- [X] T070 Validate quickstart.md scenarios: test each integration scenario from specs/003-prompt-service/quickstart.md
- [X] T071 Run full test suite and ensure 80%+ coverage: uv run pytest --cov=src/prompt_service --cov-report=term-missing
- [X] T072 [P] Security hardening: validate all inputs, sanitize error messages, add rate limiting middleware
- [X] T073 Performance optimization: verify <100ms prompt assembly, add cache metrics endpoint, optimize Jinja2 template rendering

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3 → P4)
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P1)**: Can start after Foundational (Phase 2) - Independent of US1 but shares caching infrastructure
- **User Story 3 (P2)**: Can start after Foundational (Phase 2) - Integrates with US1 (retrieval service) but independently testable
- **User Story 4 (P3)**: Can start after Foundational (Phase 2) - Depends on US1 (trace logging in retrieval) and US3 (AB test metrics)
- **User Story 5 (P4)**: Can start after Foundational (Phase 2) - Integrates with US2 (prompt management) but independently testable

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models before services
- Services before endpoints
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel (T003, T004, T005)
- All Foundational tasks marked [P] can run in parallel within Phase 2 (T007, T008, T009, T010, T012, T013)
- Once Foundational phase completes, US1 and US2 can start in parallel (both P1 priority)
- All tests for a user story marked [P] can run in parallel
- Models within a story marked [P] can run in parallel
- Different user stories can be worked on in parallel by different team members

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Contract test for prompt retrieval in tests/contract/test_prompt_retrieval.py"
Task: "Integration test for prompt retrieval in tests/integration/test_prompt_retrieval_e2e.py"

# Launch all services for User Story 1 together:
Task: "Create PromptAssemblyService in src/prompt_service/services/prompt_assembly.py"
Task: "Create PromptRetrievalService in src/prompt_service/services/prompt_retrieval.py"
```

---

## Parallel Example: User Story 2

```bash
# Launch all services for User Story 2 together:
Task: "Create PromptManagementService in src/prompt_service/services/prompt_management.py"
Task: "Create API schemas in src/prompt_service/api/schemas.py"
```

---

## Implementation Strategy

### MVP First (User Stories 1 & 2 Only - P1 Priority)

1. Complete Phase 1: Setup (T001-T005)
2. Complete Phase 2: Foundational (T006-T013) - CRITICAL
3. Complete Phase 3: User Story 1 (T014-T020)
4. Complete Phase 4: User Story 2 (T021-T029)
5. **STOP and VALIDATE**: Test US1 and US2 independently
6. Deploy/demo core prompt management: retrieve + edit

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP: retrieval only!)
3. Add User Story 2 → Test independently → Deploy/Demo (MVP+: retrieval + editing)
4. Add User Story 3 → Test independently → Deploy/Demo (A/B testing)
5. Add User Story 4 → Test independently → Deploy/Demo (Analytics)
6. Add User Story 5 → Test independently → Deploy/Demo (Versioning)
7. Complete Polish → Production ready
8. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (Prompt Retrieval)
   - Developer B: User Story 2 (Prompt Editing)
3. After US1 and US2 complete:
   - Developer A: User Story 3 (A/B Testing)
   - Developer B: User Story 5 (Versioning)
4. Developer C joins: User Story 4 (Trace Analysis)
5. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
- All file paths are absolute from repository root (src/prompt_service/...)
- Tests are mandatory per constitution - use real Langfuse for integration tests, minimal mocks only for external APIs
