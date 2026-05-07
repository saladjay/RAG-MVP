# Tasks: Conversational Query Enhancement Module

**Input**: Design documents from `/specs/007-conversational-query/`
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

**Purpose**: Project initialization and configuration for conversational query enhancement

- [X] T001 Add Redis dependency to pyproject.toml (aioredis for async Redis support)
- [X] T002 Add conversational query configuration section to src/rag_service/config.py (session timeout, max turns, TTL, domain mappings)
- [X] T003 [P] Update .env.example with Redis and conversational query environment variables
- [X] T004 [P] Create slot extraction prompt template in Prompt Service (template_id: "slot_extraction")
- [X] T005 [P] Create query generation prompt template in Prompt Service (template_id: "query_generation")

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T006 Create conversational query data models in src/rag_service/models/conversational_query.py (QueryType, BusinessDomain, ExtractedQueryElements, BeliefState, QueryGenerationResult, ColloquialTermMapping)
- [X] T007 Implement Redis belief state store service in src/rag_service/services/belief_state_store.py (get_state, update_state, delete_state with TTL support)
- [X] T008 Create colloquial term mapper service in src/rag_service/services/colloquial_mapper.py (static mappings, LLM-based inference, domain-specific mappings)
- [X] T009 Create base ConversationalQueryCapability class structure in src/rag_service/capabilities/conversational_query.py (extend Capability base class, implement validate_input and get_health)
- [X] T010 Update QA context schemas in src/rag_service/api/qa_schemas.py (add enable_conversational_query option to QAOptions)
- [X] T011 Configure Redis connection initialization in src/rag_service/main.py (initialize aioredis client on startup)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 6 - Structured Query Extraction and Classification (Priority: P1) 🎯 Foundation

**Goal**: Perform structured extraction of query elements and classify query type to determine appropriate response strategy

**Independent Test**: Submit various query types and verify the structured output matches expected extraction and classification

### Tests for User Story 6

- [ ] T012 [P] [US6] Contract test for extraction response format in tests/contract/test_conversational_query_api.py
- [ ] T013 [P] [US6] Unit test for ExtractedQueryElements model validation in tests/unit/test_conversational_query.py
- [ ] T014 [P] [US6] Integration test for slot extraction flow in tests/integration/test_conversational_query_e2e.py

### Implementation for User Story 6

- [X] T015 [P] [US6] Implement slot extraction LLM call in src/rag_service/capabilities/conversational_query.py (_extract_slots method using Prompt Service)
- [X] T016 [P] [US6] Implement slot parsing from LLM response in src/rag_service/capabilities/conversational_query.py (_parse_slot_response method)
- [X] T017 [P] [US6] Implement query type classification in src/rag_service/capabilities/conversational_query.py (_classify_query_type method)
- [X] T018 [P] [US6] Implement follow-up detection in src/rag_service/capabilities/conversational_query.py (_detect_followup method)
- [X] T019 [P] [US6] Implement confidence scoring in src/rag_service/capabilities/conversational_query.py (_calculate_confidence method)
- [X] T020 [US6] Add structured JSON logging for slot extraction in src/rag_service/capabilities/conversational_query.py (log extracted slots, confidence, action taken)

**Checkpoint**: Structured extraction complete - other user stories can now proceed in parallel

---

## Phase 4: User Story 7 - Business Domain Classification (Priority: P1)

**Goal**: Classify queries into business domains to enable intelligent routing and specialized handling

**Independent Test**: Submit queries from different business domains and verify correct classification and routing

### Tests for User Story 7

- [ ] T021 [P] [US7] Unit test for business domain classification in tests/unit/test_conversational_query.py
- [ ] T022 [P] [US7] Integration test for domain classification flow in tests/integration/test_conversational_query_e2e.py

### Implementation for User Story 7

- [X] T023 [P] [US7] Implement domain classification logic in src/rag_service/capabilities/conversational_query.py (_classify_domain method with keyword-based priority ordering)
- [X] T024 [P] [US7] Implement domain-specific keyword sets in src/rag_service/services/colloquial_mapper.py (10 domains: finance, hr, safety, governance, it, procurement, admin, party, union, committee)
- [X] T025 [US7] Add domain-based routing logic in src/rag_service/capabilities/conversational_query.py (route queries to domain-specific processing)

**Checkpoint**: Domain classification complete - enables domain-specific query generation

---

## Phase 5: User Story 2 - Colloquial Expression Recognition (Priority: P1)

**Goal**: Map colloquial expressions to formal document terminology for accurate retrieval

**Independent Test**: Submit queries with colloquial terms and verify correct translation to formal terminology

### Tests for User Story 2

- [ ] T026 [P] [US2] Unit test for colloquial term mapping in tests/unit/test_colloquial_mapper.py
- [ ] T027 [P] [US2] Integration test for colloquial mapping in queries in tests/integration/test_conversational_query_e2e.py

### Implementation for User Story 2

- [ ] T028 [P] [US2] Implement static colloquial mappings in src/rag_service/services/colloquial_mapper.py (load from config, support 2025 mappings: 会议记录→会议纪要, 职代会→职工代表大会, 三八活动→妇女节活动)
- [ ] T029 [P] [US2] Implement LLM-based colloquial inference in src/rag_service/services/colloquial_mapper.py (query LLM for unknown terms)
- [ ] T030 [P] [US2] Implement domain-specific colloquial mappings in src/rag_service/services/colloquial_mapper.py (different mappings per business domain)
- [ ] T031 [US2] Integrate colloquial mapping into slot extraction in src/rag_service/capabilities/conversational_query.py (apply mappings during slot extraction)

**Checkpoint**: Colloquial recognition complete - queries can use informal language

---

## Phase 6: User Story 1 - Conversational Information Gathering (Priority: P1)

**Goal**: Multi-turn dialogue for gathering missing query dimensions through natural conversation

**Independent Test**: Initiate conversations with incomplete queries and verify appropriate follow-up prompts

### Tests for User Story 1

- [ ] T032 [P] [US1] Unit test for belief state slot merging in tests/unit/test_belief_state_store.py
- [ ] T033 [P] [US1] Integration test for multi-turn conversation flow in tests/integration/test_conversational_query_e2e.py

### Implementation for User Story 1

- [ ] T034 [P] [US1] Implement pending slot detection in src/rag_service/capabilities/conversational_query.py (_identify_pending_slots method)
- [ ] T035 [P] [US1] Implement prompt text generation in src/rag_service/capabilities/conversational_query.py (_generate_prompt_text method)
- [ ] T036 [P] [US1] Implement belief state slot merging in src/rag_service/services/belief_state_store.py (merge new slots with existing, detect conflicts)
- [ ] T037 [US1] Implement turn limit enforcement in src/rag_service/capabilities/conversational_query.py (check max_turns, prompt for new session)
- [ ] T038 [US1] Add conversation history tracking in src/rag_service/services/belief_state_store.py (query_history, response_history, extraction_history)

**Checkpoint**: Multi-turn dialogue complete - can gather information through conversation

---

## Phase 7: User Story 4 - Conversation Context Persistence (Priority: P1)

**Goal**: Preserve conversation context across turns for natural multi-turn dialogue flow

**Independent Test**: Engage in multi-turn conversations and verify context is maintained across turns

### Tests for User Story 4

- [ ] T039 [P] [US4] Unit test for context inheritance in follow-up queries in tests/unit/test_conversational_query.py
- [ ] T040 [P] [US4] Integration test for context persistence across turns in tests/integration/test_conversational_query_e2e.py

### Implementation for User Story 4

- [ ] T041 [P] [US4] Implement follow-up slot inheritance in src/rag_service/capabilities/conversational_query.py (_inherit_slots method for pronoun references)
- [ ] T042 [P] [US4] Implement context reference resolution in src/rag_service/capabilities/conversational_query.py (_resolve_pronoun_reference method)
- [ ] T043 [P] [US4] Implement topic change detection in src/rag_service/capabilities/conversational_query.py (_detect_topic_change method)
- [ ] T044 [US4] Implement context management for topic changes in src/rag_service/services/belief_state_store.py (clear irrelevant context, preserve relevant)

**Checkpoint**: Context persistence complete - multi-turn conversations maintain continuity

---

## Phase 8: User Story 8 - Structured Query Generation (Priority: P1)

**Goal**: Generate three independent search queries optimized for document retrieval with must_include terms and keyword expansion

**Independent Test**: Submit queries and verify generated output contains appropriate question variations and keyword expansions

### Tests for User Story 8

- [ ] T045 [P] [US8] Unit test for query generation output in tests/unit/test_conversational_query.py
- [ ] T046 [P] [US8] Integration test for query generation by domain in tests/integration/test_conversational_query_e2e.py

### Implementation for User Story 8

- [ ] T047 [P] [US8] Implement query generation LLM call in src/rag_service/capabilities/conversational_query.py (_generate_queries method using Prompt Service)
- [ ] T048 [P] [US8] Implement domain-specific query templates in src/rag_service/capabilities/conversational_query.py (business_query templates: standard/rule/process/scope, meta_info templates)
- [ ] T049 [P] [US8] Implement must_include term extraction in src/rag_service/capabilities/conversational_query.py (_extract_must_include method)
- [ ] T050 [P] [US8] Implement keyword expansion in src/rag_service/capabilities/conversational_query.py (_expand_keywords method with synonyms and colloquial terms)
- [ ] T051 [US8] Implement domain context generation in src/rag_service/capabilities/conversational_query.py (_generate_domain_context method)

**Checkpoint**: Query generation complete - produces optimized retrieval queries

---

## Phase 9: User Story 3 - Synonym and Related Term Expansion (Priority: P2)

**Goal**: Automatically expand queries with related terms to improve recall

**Independent Test**: Submit queries and verify related terms are included in the search

### Tests for User Story 3

- [ ] T052 [P] [US3] Unit test for synonym expansion in tests/unit/test_conversational_query.py
- [ ] T053 [P] [US3] Integration test for expanded queries in tests/integration/test_conversational_query_e2e.py

### Implementation for User Story 3

- [ ] T054 [P] [US3] Implement domain-specific synonym mappings in src/rag_service/services/colloquial_mapper.py (related terms by business domain)
- [ ] T055 [P] [US3] Implement synonym expansion logic in src/rag_service/capabilities/conversational_query.py (_expand_synonyms method)
- [ ] T056 [US3] Integrate synonym expansion into query generation in src/rag_service/capabilities/conversational_query.py (add expanded keywords to output)

**Checkpoint**: Synonym expansion complete - improves search recall

---

## Phase 10: User Story 5 - Proactive Query Improvement Suggestions (Priority: P2)

**Goal**: Provide proactive suggestions for query refinement before search execution

**Independent Test**: Submit vague queries and verify helpful suggestions are provided

### Tests for User Story 5

- [ ] T057 [P] [US5] Unit test for suggestion generation in tests/unit/test_conversational_query.py
- [ ] T058 [P] [US5] Integration test for proactive suggestions in tests/integration/test_conversational_query_e2e.py

### Implementation for User Story 5

- [ ] T059 [P] [US5] Implement document availability analysis in src/rag_service/capabilities/conversational_query.py (_analyze_availability method)
- [ ] T060 [P] [US5] Implement suggestion generation in src/rag_service/capabilities/conversational_query.py (_generate_suggestions method)
- [ ] T061 [US5] Implement suggestion selection logic in src/rag_service/capabilities/conversational_query.py (_select_suggestions method based on availability)
- [ ] T062 [US5] Add suggestion response format in src/rag_service/models/conversational_query.py (ConversationalQueryOutput with suggestions)

**Checkpoint**: Proactive suggestions complete - guides users to better queries

---

## Phase 11: Integration & Core Implementation

**Purpose**: Wire together all components into working ConversationalQueryCapability

- [ ] T063 Implement ConversationalQueryCapability.execute method in src/rag_service/capabilities/conversational_query.py (coordinate all components)
- [ ] T064 Implement action determination logic in src/rag_service/capabilities/conversational_query.py (decide: proceed/prompt/complete)
- [ ] T065 Implement session management in src/rag_service/capabilities/conversational_query.py (get/create/update belief state)
- [ ] T066 Implement trace_id propagation through all conversational query operations
- [ ] T067 Update QA Pipeline to integrate ConversationalQueryCapability in src/rag_service/capabilities/qa_pipeline.py (call before query_quality, handle multi-turn responses)

**Checkpoint**: Integration complete - conversational query capability is functional

---

## Phase 12: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T068 [P] Add comprehensive docstrings to all public methods in src/rag_service/capabilities/conversational_query.py
- [ ] T069 [P] Add comprehensive docstrings to all public methods in src/rag_service/services/belief_state_store.py
- [ ] T070 [P] Add comprehensive docstrings to all public methods in src/rag_service/services/colloquial_mapper.py
- [ ] T071 [P] Add comprehensive docstrings to all data models in src/rag_service/models/conversational_query.py
- [ ] T072 [P] Update CLAUDE.md with conversational query capability documentation
- [ ] T073 Add error handling for Redis connection failures in src/rag_service/services/belief_state_store.py (graceful degradation)
- [ ] T074 Add error handling for LLM failures in src/rag_service/capabilities/conversational_query.py (fallback to original query)
- [ ] T075 Implement session cleanup on shutdown in src/rag_service/main.py (close Redis connections)
- [ ] T076 Add metrics for conversational query operations in src/rag_service/capabilities/conversational_query.py (extraction duration, turn count, domain distribution)
- [ ] T077 Run all tests and verify >80% coverage in tests/
- [ ] T078 Validate quickstart.md examples work end-to-end

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Story 6 (Phase 3)**: Depends on Foundational - BLOCKS US7 (needs extraction)
- **User Story 7 (Phase 4)**: Depends on US6 (needs extraction results)
- **User Stories 2, 1, 4, 8 (Phases 5-8)**: Can proceed in parallel after Foundational
- **User Story 3 (Phase 9)**: Depends on US2 (needs colloquial mappings)
- **User Story 5 (Phase 10)**: Depends on US8 (needs query generation)
- **Integration (Phase 11)**: Depends on all user stories
- **Polish (Phase 12)**: Depends on integration complete

### User Story Dependencies

- **User Story 6 (P1)**: Foundation - must be complete before US7
- **User Story 7 (P1)**: Depends on US6 (domain classification needs extraction)
- **User Story 2 (P1)**: Independent after Foundational
- **User Story 1 (P1)**: Independent after Foundational (but benefits from US6 extraction)
- **User Story 4 (P1)**: Independent after Foundational (but benefits from US1 dialogue flow)
- **User Story 8 (P1)**: Independent after Foundational (but benefits from US6, US7 extraction and classification)
- **User Story 3 (P2)**: Depends on US2 (uses colloquial mappings)
- **User Story 5 (P2)**: Depends on US8 (needs query generation for suggestions)

### Parallel Opportunities

- **Setup (Phase 1)**: T001, T002, T003, T004, T005 can all run in parallel
- **Foundational (Phase 2)**: No parallelism (blocking prerequisites)
- **US6 Tests**: T012, T013, T014 can run in parallel
- **US6 Implementation**: T015, T016, T017, T018, T019 can run in parallel
- **US7 Tests**: T021, T022 can run in parallel
- **US7 Implementation**: T023, T024 can run in parallel (T025 depends on T023)
- **US2 Tests**: T026, T027 can run in parallel
- **US2 Implementation**: T028, T029, T030 can run in parallel (T031 depends on T028)
- **Polish**: T068, T069, T070, T071, T072 can run in parallel

---

## Summary

| Metric | Count |
|--------|-------|
| Total Tasks | 78 |
| Setup Phase | 5 |
| Foundational Phase | 6 |
| User Story 6 (P1) | 9 |
| User Story 7 (P1) | 5 |
| User Story 2 (P1) | 6 |
| User Story 1 (P1) | 7 |
| User Story 4 (P1) | 6 |
| User Story 8 (P1) | 7 |
| User Story 3 (P2) | 5 |
| User Story 5 (P2) | 6 |
| Integration Phase | 5 |
| Polish Phase | 11 |
| Parallel Opportunities | 25 tasks marked [P] |

### MVP Scope (Recommended for First Delivery)

- **Tasks T001-T020**: Setup + Foundational + User Story 6 (Structured Extraction)
- **Delivers**: Core slot extraction and query classification
- **Testable Independently**: Yes - submit queries, verify structured extraction
- **Estimated Effort**: ~20 tasks

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add US6 (Extraction) → Test independently → Core capability ready
3. Add US7 (Domain) + US2 (Colloquial) → Test independently → Enhanced understanding
4. Add US1 (Gathering) + US4 (Context) → Test independently → Multi-turn ready
5. Add US8 (Generation) → Test independently → Query generation ready
6. Add US3 (Expansion) + US5 (Suggestions) → Test independently → Full feature set
7. Integration + Polish → Final release

### Format Validation

✅ All tasks follow the checklist format:
- Checkbox prefix: `- [ ]`
- Task ID: Sequential (T001-T078)
- [P] marker: Applied to 25 parallelizable tasks
- [Story] label: Applied to all user story phase tasks (US1-US8)
- File paths: Included in all implementation tasks
