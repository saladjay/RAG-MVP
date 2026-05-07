# Tasks: Query Quality Enhancement Module

**Input**: Design documents from `/specs/006-query-quality-enhancement/`
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

- **Single project**: `src/` at repository root
- Paths shown below use `src/rag_service/` structure per plan.md

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and configuration for query quality enhancement

- [X] T001 Add Redis dependency to pyproject.toml (aioredis for async Redis support)
- [X] T002 Add query quality configuration section to src/rag_service/config.py (session timeout, max turns, TTL)
- [X] T003 [P] Update .env.example with Redis and query quality environment variables
- [X] T004 [P] Create query dimension analysis prompt template in Prompt Service (template_id: "query_dimension_analysis") - include 2025 document types (会议纪要, 会议类型, 专业委员会) and expanded subject categories

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T005 Create query quality data models in src/rag_service/models/query_quality.py (DimensionType, DimensionStatus, DimensionAnalysisResult, SessionState, KnowledgeBaseRoute) - ensure models support extended dimension values from 2025 analysis (会议纪要, 会议类型, 专业委员会 categories)
- [X] T006 Implement Redis session store service in src/rag_service/services/session_store.py (get_session, update_session, delete_session with TTL support)
- [X] T007 Create base QueryQualityCapability class structure in src/rag_service/capabilities/query_quality.py (extend Capability base class, implement validate_input and get_health)
- [X] T008 Update QA context schemas in src/rag_service/api/qa_schemas.py (add enable_query_quality option to QAOptions)
- [X] T009 Configure Redis connection initialization in src/rag_service/main.py (initialize aioredis client on startup)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Query Dimension Analysis (Priority: P1) 🎯 MVP

**Goal**: Analyze user queries against required document dimensions and identify missing information

**Independent Test**: Submit a query with missing dimensions (e.g., "关于安全管理的通知") and verify the system identifies the missing year dimension and prompts appropriately

### Tests for User Story 1

- [ ] T010 [P] [US1] Contract test for dimension analysis response format in tests/contract/test_query_quality_api.py
- [ ] T011 [P] [US1] Unit test for DimensionAnalysisResult model validation in tests/unit/test_query_quality.py
- [ ] T012 [P] [US1] Integration test for query dimension analysis flow in tests/integration/test_query_quality_e2e.py

### Implementation for User Story 1

- [X] T013 [P] [US1] Implement dimension analysis LLM call in src/rag_service/capabilities/query_quality.py (_analyze_dimensions method using Prompt Service)
- [X] T014 [P] [US1] Implement dimension parsing from LLM response in src/rag_service/capabilities/query_quality.py (_parse_dimension_response method)
- [X] T015 [P] [US1] Implement quality score calculation in src/rag_service/capabilities/query_quality.py (_calculate_quality_score method)
- [X] T016 [US1] Implement QueryQualityCapability.execute method in src/rag_service/capabilities/query_quality.py (session management, dimension analysis, action determination)
- [X] T017 [US1] Add structured JSON logging for dimension analysis in src/rag_service/capabilities/query_quality.py (log missing dimensions, quality score, action taken)
- [X] T018 [US1] Add prompt text generation for missing dimensions in src/rag_service/capabilities/query_quality.py (_generate_prompt_text method)
- [X] T019 [US1] Update QA Pipeline to integrate QueryQualityCapability in src/rag_service/capabilities/qa_pipeline.py (call before query_rewrite, handle "prompt" action)

**Checkpoint**: At this point, User Story 1 should be fully functional - queries with missing dimensions trigger prompts

---

## Phase 4: User Story 2 - Query Dimension Completion (Priority: P1)

**Goal**: Incorporate user-provided dimension information into enhanced queries and proceed with retrieval

**Independent Test**: Respond to dimension prompt with missing information (e.g., "2024年") and verify the enhanced query includes the provided dimension and search proceeds

### Tests for User Story 2

- [ ] T020 [P] [US2] Integration test for multi-turn dimension completion in tests/integration/test_query_quality_e2e.py
- [ ] T021 [P] [US2] Unit test for session state dimension merging in tests/unit/test_query_quality.py

### Implementation for User Story 2

- [ ] T022 [P] [US2] Implement dimension value validation in src/rag_service/capabilities/query_quality.py (_validate_dimension_value method)
- [ ] T023 [P] [US2] Implement session dimension merging in src/rag_service/services/session_store.py (merge new dimensions with established_dimensions)
- [ ] T024 [US2] Implement enhanced query generation in src/rag_service/capabilities/query_quality.py (_build_enhanced_query method)
- [ ] T025 [US2] Implement conflict detection for inconsistent information in src/rag_service/capabilities/query_quality.py (_detect_dimension_conflicts method)
- [ ] T026 [US2] Add trace_id propagation to all session operations in src/rag_service/services/session_store.py
- [ ] T027 [US2] Update QA Pipeline to handle enhanced query from QueryQualityCapability in src/rag_service/capabilities/qa_pipeline.py (pass enhanced_query to query_rewrite)

**Checkpoint**: At this point, User Story 2 should be fully functional - multi-turn dimension collection works and enhanced queries proceed to retrieval

---

## Phase 5: User Story 3 - Automatic Query Enrichment (Priority: P2)

**Goal**: Automatically enrich queries with reasonable defaults (e.g., current year) without user input

**Independent Test**: Submit a query without year (e.g., "关于安全生产的通知") and verify the system adds current year context automatically

### Tests for User Story 3

- [ ] T028 [P] [US3] Unit test for auto-enrichment logic in tests/unit/test_query_quality.py
- [ ] T029 [P] [US3] Integration test for enriched query with defaults in tests/integration/test_query_quality_e2e.py

### Implementation for User Story 3

- [ ] T030 [P] [US3] Implement default value inference in src/rag_service/capabilities/query_quality.py (_infer_defaults method - current year, main organization, etc.)
- [ ] T031 [P] [US3] Implement enrichment rules per dimension type in src/rag_service/capabilities/query_quality.py (_get_enrichment_rules method)
- [ ] T032 [US3] Add auto-enrichment option handling in src/rag_service/capabilities/query_quality.py (respect auto_enrich flag in QueryQualityInput)
- [ ] T033 [US3] Add logging for enrichment decisions in src/rag_service/capabilities/query_quality.py (log which defaults were applied)

**Checkpoint**: At this point, User Story 3 should be fully functional - partial queries are automatically enriched with sensible defaults

---

## Phase 6: User Story 4 - Query Quality Feedback (Priority: P2)

**Goal**: Provide feedback to users about query quality and suggestions for improvement after search completion

**Independent Test**: Complete a search and verify quality feedback is displayed showing which dimensions were present/missing

### Tests for User Story 4

- [ ] T034 [P] [US4] Unit test for feedback message generation in tests/unit/test_query_quality.py
- [ ] T035 [P] [US4] Integration test for quality feedback in response in tests/integration/test_query_quality_e2e.py

### Implementation for User Story 4

- [ ] T036 [P] [US4] Implement feedback message generation in src/rag_service/capabilities/query_quality.py (_generate_feedback method)
- [ ] T037 [P] [US4] Implement suggestion generation based on missing dimensions in src/rag_service/capabilities/query_quality.py (_generate_suggestions method)
- [ ] T038 [US4] Add quality feedback to QueryQualityOutput schema in src/rag_service/models/query_quality.py
- [ ] T039 [US4] Update QA Pipeline to include quality feedback in response metadata in src/rag_service/capabilities/qa_pipeline.py

**Checkpoint**: At this point, User Story 4 should be fully functional - users receive quality feedback after search completion

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T040 [P] Add comprehensive docstrings to all public methods in src/rag_service/capabilities/query_quality.py
- [ ] T041 [P] Add comprehensive docstrings to all public methods in src/rag_service/services/session_store.py
- [ ] T042 [P] Add comprehensive docstrings to all data models in src/rag_service/models/query_quality.py
- [ ] T043 [P] Update CLAUDE.md with query quality capability documentation
- [ ] T044 Add error handling for Redis connection failures in src/rag_service/services/session_store.py (graceful degradation)
- [ ] T045 Add error handling for LLM failures in src/rag_service/capabilities/query_quality.py (fallback to original query)
- [ ] T046 Implement session cleanup on shutdown in src/rag_service/main.py (close Redis connections)
- [ ] T047 Add metrics for query quality operations in src/rag_service/capabilities/query_quality.py (analysis duration, prompt rate, quality score distribution)
- [ ] T048 Run all tests and verify >80% coverage in tests/
- [ ] T049 Validate quickstart.md examples work end-to-end

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - US1 (P1) and US2 (P1) can proceed in parallel after Foundational
  - US3 (P2) depends on US2 completion (needs dimension completion flow)
  - US4 (P2) depends on US1 completion (needs analysis results)
- **Polish (Phase 7)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P1)**: Can start after Foundational (Phase 2) - Integrates with US1 output but independently testable
- **User Story 3 (P2)**: Depends on US2 - uses dimension completion flow from US2
- **User Story 4 (P2)**: Depends on US1 - uses dimension analysis from US1

### Within Each User Story

- Tests MUST be written and FAIL before implementation (Constitution Principle III)
- Models before services
- Services before capabilities
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- **Setup (Phase 1)**: T001, T002, T003, T004 can all run in parallel
- **Foundational (Phase 2)**: No parallelism (blocking prerequisites)
- **US1 Tests**: T010, T011, T012 can run in parallel
- **US1 Models**: T013, T014, T015 can run in parallel
- **US2 Tests**: T020, T021 can run in parallel
- **US2 Models**: T022, T023 can run in parallel
- **US3 Tests**: T028, T029 can run in parallel
- **US3 Models**: T030, T031 can run in parallel
- **US4 Tests**: T034, T035 can run in parallel
- **US4 Models**: T036, T037 can run in parallel
- **Polish**: T040, T041, T042, T043 can run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task T010: "Contract test for dimension analysis response format in tests/contract/test_query_quality_api.py"
Task T011: "Unit test for DimensionAnalysisResult model validation in tests/unit/test_query_quality.py"
Task T012: "Integration test for query dimension analysis flow in tests/integration/test_query_quality_e2e.py"

# Launch all models/methods for User Story 1 together:
Task T013: "Implement dimension analysis LLM call in src/rag_service/capabilities/query_quality.py"
Task T014: "Implement dimension parsing from LLM response in src/rag_service/capabilities/query_quality.py"
Task T015: "Implement quality score calculation in src/rag_service/capabilities/query_quality.py"
```

---

## Implementation Strategy

### MVP First (User Stories 1 & 2 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Query Dimension Analysis)
4. Complete Phase 4: User Story 2 (Query Dimension Completion)
5. **STOP and VALIDATE**: Test multi-turn dimension collection independently
6. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add US1 (Dimension Analysis) → Test independently → Deploy/Demo (MVP!)
3. Add US2 (Dimension Completion) → Test independently → Deploy/Demo (Full multi-turn!)
4. Add US3 (Auto Enrichment) → Test independently → Deploy/Demo
5. Add US4 (Quality Feedback) → Test independently → Deploy/Demo
6. Polish → Final release

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (Dimension Analysis)
   - Developer B: User Story 2 (Dimension Completion)
3. After US1 and US2 complete:
   - Developer A: User Story 3 (Auto Enrichment)
   - Developer B: User Story 4 (Quality Feedback)
4. Stories complete and integrate independently

---

## Summary

| Metric | Count |
|--------|-------|
| Total Tasks | 49 |
| Setup Phase | 4 |
| Foundational Phase | 5 |
| User Story 1 (P1) | 10 |
| User Story 2 (P1) | 8 |
| User Story 3 (P2) | 6 |
| User Story 4 (P2) | 6 |
| Polish Phase | 10 |
| Parallel Opportunities | 18 tasks marked [P] |

### MVP Scope (Recommended for First Delivery)

- **Tasks T001-T019**: Setup + Foundational + User Story 1
- **Delivers**: Query dimension analysis with prompts for missing information
- **Testable Independently**: Yes - submit incomplete query, get dimension prompt
- **Estimated Effort**: ~19 tasks

### Format Validation

✅ All tasks follow the checklist format:
- Checkbox prefix: `- [ ]`
- Task ID: Sequential (T001-T049)
- [P] marker: Applied to 18 parallelizable tasks
- [Story] label: Applied to all user story phase tasks (US1, US2, US3, US4)
- File paths: Included in all implementation tasks
