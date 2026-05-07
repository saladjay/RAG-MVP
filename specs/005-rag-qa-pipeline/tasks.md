# Tasks: RAG QA Pipeline

**Input**: Design documents from `/specs/005-rag-qa-pipeline/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/qa-api.yaml

**Tests**: Tests are MANDATORY per constitution (Principle III). Use real implementations, minimize mocks.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

**Constitution Compliance**:
- All implementation tasks must include documentation headers (Principle I)
- Testing tasks must use real implementations (Principle III)
- Python tasks must use `uv` environment (Principle IV)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- **RAG Service**: `src/rag_service/` at repository root
- **Tests**: `tests/unit/`, `tests/integration/`, `tests/contract/` at repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure for QA pipeline

- [X] T001 Add QA configuration to `src/rag_service/config.py` (QAConfig class with rewrite, hallucination, fallback settings)
- [X] T002 [P] Create default fallback messages config in `config/qa_fallback.yaml` (kb_unavailable, kb_empty, kb_error, hallucination_failed)
- [X] T003 [P] Create query rewrite prompt template in `rag_service/prompts/qa_prompts.yaml` (query_rewrite_prompt)
- [X] T004 [P] Create answer generation prompt template in `rag_service/prompts/qa_prompts.yaml` (answer_generation_prompt)
- [X] T005 [P] Create strict answer generation prompt in `rag_service/prompts/qa_prompts.yaml` (answer_generation_strict_prompt for regeneration)
- [X] T006 Update main.py to import new QA routes for registration

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T007 Create QA request/response schemas in `src/rag_service/api/qa_schemas.py` (QAQueryRequest, QAContext, QAOptions, QAQueryResponse, QASourceInfo, HallucinationStatus, QAMetadata, QATiming, QAErrorResponse)
- [X] T008 [P] Create internal capability input models in `src/rag_service/capabilities/qa_pipeline.py` (QAPipelineInput, QAPipelineOutput, QAPipelineMetadata)
- [X] T009 [P] Create query rewrite models in `src/rag_service/capabilities/query_rewrite.py` (QueryRewriteInput, QueryRewriteOutput)
- [X] T010 [P] Create hallucination detection models in `src/rag_service/capabilities/hallucination_detection.py` (HallucinationCheckInput, HallucinationCheckOutput)
- [X] T011 [P] Create default fallback service models in `src/rag_service/services/default_fallback.py` (FallbackRequest, FallbackResponse, FallbackErrorType)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Basic QA with External Knowledge (Priority: P1) 🎯 MVP

**Goal**: Users submit natural language questions and receive answers based on retrieved documents from external KB

**Independent Test**: Submit a query via `POST /qa/query`, verify response includes answer + sources from external KB, verify fallback message when KB returns empty

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T012 [P] [US1] Contract test for QA query endpoint in `tests/contract/test_qa_api.py` (validate request schema, response schema, error responses)
- [X] T013 [P] [US1] Integration test for basic QA flow in `tests/integration/test_qa_pipeline_e2e.py` (real external KB, real LiteLLM, verify answer + sources)
- [X] T014 [P] [US1] Integration test for fallback scenarios in `tests/integration/test_qa_pipeline_e2e.py` (KB empty, KB error, KB unavailable)

### Implementation for User Story 1

- [X] T015 [P] [US1] Create DefaultFallbackService in `src/rag_service/services/default_fallback.py` (get_fallback method, YAML loading, template support)
- [X] T016 [P] [US1] Create QAPipelineCapability stub in `src/rag_service/capabilities/qa_pipeline.py` (execute method, trace ID propagation)
- [X] T017 [US1] Implement ExternalKBQueryCapability integration in QAPipelineCapability (call ExternalKBClient.query(), handle empty/error results with DefaultFallbackService)
- [X] T018 [US1] Implement ModelInferenceCapability integration in QAPipelineCapability (call LiteLLMGateway.acomplete() for answer generation with retrieved chunks as context)
- [X] T019 [US1] Implement QAPipelineCapability response assembly (QAQueryResponse with answer, sources, metadata, timing)
- [X] T020 [US1] Create QA query endpoint in `src/rag_service/api/qa_routes.py` (POST /qa/query, request validation, error handling, QAPipelineCapability.execute() call)
- [X] T021 [US1] Add request validation to QA query endpoint (query not empty, company_id format, file_type enum, top_k range)
- [X] T022 [US1] Add error handling to QA query endpoint (KB unavailable → fallback, generation failed → error, timeout handling)
- [X] T023 [US1] Add logging to QAPipelineCapability (trace ID, query, retrieval count, generation timing)
- [X] T024 [US1] Update main.py health check to include QA pipeline status (external_kb, litellm, fallback_ready)

**Checkpoint**: At this point, User Story 1 should be fully functional - users can query and get answers with sources

---

## Phase 4: User Story 3 - Hallucination Detection (Priority: P1) 🎯 MVP

**Goal**: Verify generated answers are based on retrieved content, flag or regenerate when hallucination detected

**Independent Test**: Submit queries that could cause hallucination, verify detection catches unsupported claims, verify regeneration happens or warning is shown

### Tests for User Story 3

- [X] T025 [P] [US3] Unit test for similarity calculation in `tests/unit/test_hallucination_detection.py` (cosine similarity, threshold comparison)
- [ ] T026 [P] [US3] Integration test for hallucination detection in `tests/integration/test_qa_pipeline_e2e.py` (real answers vs chunks, verify confidence scores)
- [ ] T027 [P] [US3] Integration test for regeneration flow in `tests/integration/test_qa_pipeline_e2e.py` (hallucination detected → regenerate with strict prompt → re-check)

### Implementation for User Story 3

- [X] T028 [P] [US3] Create HallucinationDetectionCapability in `src/rag_service/capabilities/hallucination_detection.py` (execute method, sentence-transformers integration, similarity calculation, confidence scoring)
- [X] T029 [US3] Implement embedding generation in HallucinationDetectionCapability (encode answer, encode chunks, compute average similarity)
- [X] T030 [US3] Implement threshold comparison in HallucinationDetectionCapability (compare to QAConfig.hallucination_threshold, return passed/failed with confidence)
- [X] T031 [US3] Integrate HallucinationDetectionCapability into QAPipelineCapability (call after generation, check if enabled, handle disabled case)
- [X] T032 [US3] Implement regeneration flow in QAPipelineCapability (if hallucination detected, regenerate with strict prompt, re-check, max attempts from config)
- [X] T033 [US3] Add hallucination status to QAQueryResponse (checked, passed, confidence, flagged_claims, warning_message)
- [X] T034 [US3] Add timing for hallucination check to QAMetadata (verify_ms)
- [X] T035 [US3] Add logging for hallucination detection (confidence, threshold, passed/failed, regeneration attempts)

**Checkpoint**: At this point, User Stories 1 AND 3 should both work - QA pipeline with hallucination verification

---

## Phase 5: User Story 2 - Query Rewriting for Improved Retrieval (Priority: P2)

**Goal**: Rewrite user queries to improve retrieval accuracy, fallback to original query if rewriting fails

**Independent Test**: Submit vague/ambiguous queries, verify rewritten query is more specific, verify fallback to original if rewrite fails

### Tests for User Story 2

- [X] T036 [P] [US2] Unit test for query rewriting logic in `tests/unit/test_query_rewrite.py` (rewrite vs original, fallback behavior)
- [ ] T037 [P] [US2] Integration test for query rewriting in `tests/integration/test_qa_pipeline_e2e.py` (real LiteLLM, verify rewritten query format, verify improved retrieval)

### Implementation for User Story 2

- [X] T038 [P] [US2] Create QueryRewriteCapability in `src/rag_service/capabilities/query_rewrite.py` (execute method, LiteLLMGateway.acomplete() call, prompt template interpolation)
- [X] T039 [US2] Implement context injection in QueryRewriteCapability (company_id, file_type, current_date into prompt)
- [X] T040 [US2] Implement fallback logic in QueryRewriteCapability (if LLM fails, return original; if empty, return original; if too long, return original)
- [X] T041 [US2] Integrate QueryRewriteCapability into QAPipelineCapability (call before retrieval, check if enabled, pass rewritten query to ExternalKBQueryCapability)
- [X] T042 [US2] Add query rewrite status to QAMetadata (query_rewritten flag, original_query, rewritten_query)
- [X] T043 [US2] Add timing for query rewriting to QAMetadata (rewrite_ms)
- [X] T044 [US2] Add logging for query rewriting (original vs rewritten, rewrite status, fallback occurrences)

**Checkpoint**: At this point, User Stories 1, 2, AND 3 should all work - complete QA pipeline with rewriting and verification

---

## Phase 6: User Story 4 - Streaming Response for Real-time Feedback (Priority: P3)

**Goal**: Stream answer tokens to users as they're generated, run hallucination detection asynchronously

**Independent Test**: Submit query via streaming endpoint, verify tokens arrive incrementally, verify X-Hallucination-Checked header updates

### Tests for User Story 4

- [X] T045 [P] [US4] Integration test for streaming response in `tests/integration/test_qa_streaming_e2e.py` (Server-Sent Events, token streaming, header updates)

### Implementation for User Story 4

- [X] T046 [US4] Create streaming endpoint in `src/rag_service/api/qa_routes.py` (POST /qa/query/stream, FastAPI StreamingResponse)
- [X] T047 [US4] Implement token streaming in QAPipelineCapability (async generator, yield tokens as they arrive)
- [X] T048 [US4] Implement async hallucination detection for streaming (run in background after streaming completes, update status via WebSocket or header)
- [X] T049 [US4] Add X-Hallucination-Checked header to streaming response (pending → passed/failed/skipped)
- [X] T050 [US4] Add X-Trace-ID header to streaming response
- [X] T051 [US4] Handle streaming interruption (log partial response, connection drop handling)

**Checkpoint**: All user stories should now be independently functional

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [X] T052 [P] Create architecture documentation in `docs/qa-pipeline-architecture.md` (component diagram, call flow, data flow)
- [X] T053 [P] Create API reference documentation in `docs/qa-pipeline-api.md` (endpoint descriptions, request/response examples, error codes)
- [X] T054 [P] Add performance optimization (caching for embeddings, connection pooling, batch processing)
- [X] T055 [P] Add unit tests for edge cases (malformed KB responses, unsupported languages, unrelated queries)
- [X] T056 [P] Add security hardening (input sanitization, rate limiting preparation, audit logging)
- [ ] T057 Run quickstart.md validation (follow quickstart guide, verify all steps work)
- [X] T058 Update CLAUDE.md with Feature 005 components (already done in planning phase)
- [X] T059 [P] Add performance benchmarks (measure end-to-end latency, verify < 10s target)
- [ ] T060 Run full test suite and ensure 80% coverage (pytest --cov)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - User Story 1 (P1) should be completed first for MVP
  - User Story 3 (P1) should be completed second for complete MVP
  - User Story 2 (P2) can be done in parallel with US1/US3 but integrates into the pipeline
  - User Story 4 (P3) can be done independently after US1+US3
- **Polish (Phase 7)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories - Core MVP
- **User Story 3 (P1)**: Depends on User Story 1 (requires answer generation to verify) - Completes MVP
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Integrates into US1 pipeline but independently testable
- **User Story 4 (P3)**: Depends on User Story 1 (requires answer generation to stream) - Can optionally include US3

### Within Each User Story

- Tests MUST be written and FAIL before implementation (TDD approach)
- Models before services
- Services before endpoints
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- **Setup (Phase 1)**: T002, T003, T004, T005 can run in parallel (different files)
- **Foundational (Phase 2)**: T008, T009, T010, T011 can run in parallel (different capability files)
- **US1 Tests**: T012, T013, T014 can run in parallel
- **US1 Implementation**: T015, T016 can run in parallel after tests
- **US3 Tests**: T025, T026, T027 can run in parallel
- **US3 Implementation**: T028 can start after tests
- **US2 Tests**: T036, T037 can run in parallel
- **US2 Implementation**: T038 can start after tests
- **US4**: Can be done in parallel with US2 (no dependencies)
- **Polish**: Most tasks can run in parallel (T052-T056, T059)

---

## Parallel Example: User Story 1

```bash
# After Foundational phase completes, launch US1 tests together:
Task: "Contract test for QA query endpoint in tests/contract/test_qa_api.py"
Task: "Integration test for basic QA flow in tests/integration/test_qa_pipeline_e2e.py"
Task: "Integration test for fallback scenarios in tests/integration/test_qa_pipeline_e2e.py"

# After tests fail, launch US1 implementation in parallel:
Task: "Create DefaultFallbackService in src/rag_service/services/default_fallback.py"
Task: "Create QAPipelineCapability stub in src/rag_service/capabilities/qa_pipeline.py"
```

---

## Parallel Example: User Story 3

```bash
# Launch US3 tests together after US1 is complete:
Task: "Unit test for similarity calculation in tests/unit/test_hallucination_detection.py"
Task: "Integration test for hallucination detection in tests/integration/test_qa_pipeline_e2e.py"
Task: "Integration test for regeneration flow in tests/integration/test_qa_pipeline_e2e.py"

# After tests fail, start implementation:
Task: "Create HallucinationDetectionCapability in src/rag_service/capabilities/hallucination_detection.py"
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 3 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Basic QA pipeline)
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Complete Phase 4: User Story 3 (Hallucination Detection)
6. **STOP and VALIDATE**: Test US1 + US3 together (Complete MVP)
7. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (Basic MVP!)
3. Add User Story 3 → Test independently → Deploy/Demo (Complete MVP!)
4. Add User Story 2 → Test independently → Deploy/Demo (Improved retrieval)
5. Add User Story 4 → Test independently → Deploy/Demo (Better UX)
6. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (Basic QA)
   - Developer B: User Story 2 (Query Rewriting) - in parallel, integrates later
3. After US1 completes:
   - Developer A: User Story 3 (Hallucination Detection)
   - Developer C: User Story 4 (Streaming) - can start in parallel
4. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing (TDD approach)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- US3 (Hallucination Detection) is P1 priority and should be part of MVP alongside US1
- US2 (Query Rewriting) is P2 but can be implemented independently
- US4 (Streaming) is P3 and is optional for MVP
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence

---

## Task Summary

| Phase | Tasks | Priority | Description |
|-------|-------|----------|-------------|
| 1: Setup | 6 | - | Config, prompts, fallback setup |
| 2: Foundational | 5 | - | Data models, schemas |
| 3: US1 | 13 | P1 | Basic QA pipeline |
| 4: US3 | 11 | P1 | Hallucination detection |
| 5: US2 | 9 | P2 | Query rewriting |
| 6: US4 | 7 | P3 | Streaming response |
| 7: Polish | 9 | - | Documentation, optimization |
| **Total** | **60** | | |

**MVP Scope (P1 only)**: Phases 1-4 (35 tasks) - Complete QA pipeline with hallucination detection
**Full Scope**: All phases (60 tasks) - Including query rewriting and streaming
