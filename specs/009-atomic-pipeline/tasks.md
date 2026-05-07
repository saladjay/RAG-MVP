# Tasks: Atomic Pipeline Refactor

**Input**: Design documents from `/specs/009-atomic-pipeline/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Tests are NOT explicitly requested in the spec. No test tasks generated.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

**Constitution Compliance**:
- All implementation tasks must include documentation headers (Principle I)
- Python tasks must use `uv` environment (Principle IV)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create pipeline package structure and Protocol definitions

- [x] T001 Create pipeline package directories `src/rag_service/pipeline/` and `src/rag_service/pipeline/steps/` with `__init__.py` files
- [x] T002 [P] Implement StepCapability and MemoryCapability Protocol definitions in `src/rag_service/pipeline/protocols.py`

**Checkpoint**: Package structure ready, Protocol interfaces defined

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core pipeline infrastructure that MUST be complete before ANY user story

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T003 Implement PipelineContext model in `src/rag_service/pipeline/context.py` with fields: original_query, session_id, trace_id, request_context, top_k, stream, processed_query, chunks, reasoning_result, answer, hallucination_status, quality_meta, should_abort, abort_prompt, timing. Include `from_request()` factory method
- [x] T004 [P] Implement PipelinePolicy model in `src/rag_service/pipeline/policy.py` with fields mapped from QueryConfig (enable_extraction, enable_rewrite, enable_reasoning, enable_verification, enable_execution, rewrite_depth, max_regen_attempts, hallucination_threshold, extraction_mode, retrieval_backend, verification_method, prompt template IDs). Include `from_config()` factory and `_should_run(step)` method
- [x] T005 Implement PipelineRunner in `src/rag_service/pipeline/runner.py` with: step list iteration, policy-based `_should_run()` check, per-step timing via `context.timing[step.name]`, `should_abort` check after each step, core error propagation (RetrievalError, GenerationError), non-core error graceful degradation, `get_health()` aggregation from all steps
- [x] T006 Update `src/rag_service/pipeline/__init__.py` to export PipelineRunner, PipelineContext, PipelinePolicy, StepCapability, MemoryCapability

**Checkpoint**: Foundation ready — pipeline infrastructure can execute steps with context flow

---

## Phase 3: User Story 1 — Basic Query Pipeline (Priority: P1) MVP

**Goal**: Decompose QueryCapability into 7 atomic steps orchestrated by PipelineRunner. Service produces identical responses to existing API.

**Independent Test**: Send `POST /api/v1/query` with `{"query": "What is RAG?"}` and receive a correct answer with sources and per-step timing metadata.

### Implementation for User Story 1

- [x] T007 [P] [US1] Implement ExtractionStep in `src/rag_service/pipeline/steps/extraction.py` — delegates to BasicQuality strategy (pass-through for basic mode), reads `original_query` and `session_id`, writes `processed_query` and `quality_meta`. Sets `should_abort=True` when quality strategy returns prompt_info
- [x] T008 [P] [US1] Implement RewriteStep in `src/rag_service/pipeline/steps/rewrite.py` — delegates to QueryRewriteCapability, reads `processed_query`, writes updated `processed_query`. Gracefully degrades to original query on failure
- [x] T009 [P] [US1] Implement RetrievalStep in `src/rag_service/pipeline/steps/retrieval.py` — delegates to RetrievalStrategy (Milvus or ExternalKB based on policy.retrieval_backend), reads `processed_query`, `top_k`, `request_context`, writes `chunks`. Raises RetrievalError on core failure
- [x] T010 [P] [US1] Implement ReasoningStep in `src/rag_service/pipeline/steps/reasoning.py` — Phase 1 pass-through (identity function). Reads `chunks` and `processed_query`, writes `reasoning_result=None`. ~20 lines
- [x] T011 [P] [US1] Implement GenerationStep in `src/rag_service/pipeline/steps/generation.py` — reads `processed_query`, `chunks`, `reasoning_result`, writes `answer`. Uses LiteLLMGateway.acomplete_routed() with prompt built from context (keep existing hardcoded prompt for now, P3 externalizes it). Raises GenerationError on failure
- [x] T012 [P] [US1] Implement VerificationStep in `src/rag_service/pipeline/steps/verification.py` — delegates to HallucinationDetectionCapability, reads `answer` and `chunks`, writes `hallucination_status`. Gracefully degrades (marks unchecked) on failure
- [x] T013 [P] [US1] Implement ExecutionStep in `src/rag_service/pipeline/steps/execution.py` — Phase 1: migrated from quality.post_process(). Reads `answer`, `chunks`, `hallucination_status`, writes finalized `quality_meta`. ~25 lines
- [x] T014 [US1] Update `src/rag_service/pipeline/steps/__init__.py` to export all 7 steps
- [x] T015 [US1] Rewrite QueryCapability in `src/rag_service/capabilities/query_capability.py` — replace 454-line execute() with ~30-line orchestration: build PipelineContext from request, construct PipelinePolicy from config, create step list, call PipelineRunner.run(), build QueryResponse from context. Preserve validate_input() and get_health(). Remove _rewrite_query(), _generate_answer(), _check_hallucination() private methods
- [x] T016 [US1] Verify service starts and basic query works: `uv run python -c "from rag_service.main import app; print('OK')"`. Test `POST /api/v1/query` returns identical response shape

**Checkpoint**: Basic pipeline works end-to-end. QueryCapability is ~30 lines. All existing API behavior preserved for basic quality mode.

---

## Phase 4: User Story 2 — Quality Enhancement Modes (Priority: P2)

**Goal**: Enable dimension_gather and conversational quality modes through ExtractionStep sub-strategies.

**Independent Test**: Configure `quality_mode=dimension_gather`, send a vague query, receive a follow-up prompt. Send a complete query, receive a full answer.

### Implementation for User Story 2

- [x] T017 [US2] Update ExtractionStep in `src/rag_service/pipeline/steps/extraction.py` to support all 3 quality modes: basic (pass-through), dimension_gather (delegate to DimensionGatherQuality), conversational (delegate to ConversationalQuality). Strategy selection from `context` quality_meta or policy extraction_mode
- [x] T018 [US2] Update QueryCapability response building in `src/rag_service/capabilities/query_capability.py` to handle abort flow: when `context.should_abort=True`, build prompt response with action, prompt_text, dimensions, feedback fields from context (replacing current QueryQualityPromptRequired exception handling)
- [x] T019 [US2] Update unified_routes.py error handling in `src/rag_service/api/unified_routes.py` — remove `QueryQualityPromptRequired` except handler since pipeline now uses should_abort signal. Update the unified_query endpoint to check response.action field for prompt responses

**Checkpoint**: All 3 quality modes work. Vague queries return prompts, complete queries return answers.

---

## Phase 5: User Story 3 — Prompt Externalization (Priority: P3)

**Goal**: Replace hardcoded generation prompt with PromptClient-managed template. Fix RewriteStep wiring bug.

**Independent Test**: Update prompt template in prompt service, verify new prompt is used in response.

### Implementation for User Story 3

- [x] T020 [US3] Update GenerationStep in `src/rag_service/pipeline/steps/generation.py` to load prompt template via PromptClient using policy.prompt_generation template ID. Fall back to default prompt if PromptClient unavailable. Remove hardcoded prompt string
- [x] T021 [US3] Fix RewriteStep in `src/rag_service/pipeline/steps/rewrite.py` — ensure proper LiteLLMGateway wiring so QueryRewriteCapability actually calls LLM (currently always returns original due to missing client initialization). Load rewrite prompt via PromptClient using policy.prompt_rewrite template ID

**Checkpoint**: Zero hardcoded prompts remain. All prompts managed through PromptClient with fallback defaults.

---

## Phase 6: User Story 4 — Regeneration Loop (Priority: P4)

**Goal**: Pipeline automatically retries generation when hallucination is detected, up to max_regen_attempts.

**Independent Test**: Set `max_regen_attempts=2`, send a query that initially hallucinates, observe retry and corrected answer.

### Implementation for User Story 4

- [x] T022 [US4] Add regeneration loop to PipelineRunner in `src/rag_service/pipeline/runner.py` — after GenerationStep + VerificationStep, if hallucination is detected and attempts remain, re-execute both steps with stricter prompt (use policy.prompt_generation with strict variant). Track attempt count in context.quality_meta. Return best answer if all attempts fail
- [x] T023 [US4] Add strict prompt template support to GenerationStep in `src/rag_service/pipeline/steps/generation.py` — accept a `strict` flag that switches to policy.prompt_verification template for regeneration attempts

**Checkpoint**: Regeneration loop works. Hallucinated answers are automatically retried.

---

## Phase 7: User Story 5 — Streaming Unification (Priority: P5)

**Goal**: Streaming queries use the same pipeline steps as synchronous queries.

**Independent Test**: Send streaming query, verify tokens stream in real-time while extraction, rewrite, retrieval still execute.

### Implementation for User Story 5

- [x] T024 [US5] Add streaming support to PipelineRunner in `src/rag_service/pipeline/runner.py` — add `run_stream()` method that executes all steps up to GenerationStep synchronously, then yields tokens from GenerationStep as async generator. Verification runs after stream completes
- [x] T025 [US5] Add streaming support to GenerationStep in `src/rag_service/pipeline/steps/generation.py` — add `execute_stream()` method that returns AsyncGenerator[str, None] using gateway streaming APIs
- [x] T026 [US5] Update stream_execute() in `src/rag_service/capabilities/query_capability.py` to use PipelineRunner.run_stream() instead of duplicated pipeline logic

**Checkpoint**: Streaming queries share step implementations with synchronous queries. No duplicated pipeline logic.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and cleanup

- [x] T027 Verify all 3 quality modes work end-to-end: basic, dimension_gather, conversational via `POST /api/v1/query`
- [x] T028 Verify streaming works via `POST /api/v1/query/stream` for all quality modes
- [x] T029 Run `uv run python -c "from rag_service.main import app; print('OK')"` to confirm service starts with zero regression
- [x] T030 Verify QueryCapability is under 50 lines by checking `src/rag_service/capabilities/query_capability.py` line count

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - US1 (P1): Must complete first — foundation for all other stories
  - US2 (P2): Depends on US1 (extends ExtractionStep)
  - US3 (P3): Depends on US1 (modifies GenerationStep, RewriteStep)
  - US4 (P4): Depends on US1 + US3 (uses GenerationStep + VerificationStep)
  - US5 (P5): Depends on US1 (adds streaming to PipelineRunner + GenerationStep)
- **Polish (Phase 8)**: Depends on all user stories

### User Story Dependencies

```
Phase 1 (Setup)
    ↓
Phase 2 (Foundational)
    ↓
Phase 3 (US1: Basic Pipeline) ← MVP
    ↓
    ├─→ Phase 4 (US2: Quality Modes)
    ├─→ Phase 5 (US3: Prompts)
    │       ↓
    │   Phase 6 (US4: Regeneration)
    └─→ Phase 7 (US5: Streaming)
    ↓
Phase 8 (Polish)
```

### Within Each User Story

- Models/protocols before implementations
- Steps before QueryCapability rewrite
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- T001 and T002 can run in parallel (different files)
- T003 and T004 can run in parallel (different files)
- T007-T013 can ALL run in parallel (7 step files, no dependencies on each other)
- T020 and T021 can run in parallel (different step files)
- T022 and T023 must run sequentially (runner depends on step update)

---

## Parallel Example: User Story 1

```bash
# After Phase 2 complete, launch all 7 steps in parallel:
Task: "ExtractionStep in src/rag_service/pipeline/steps/extraction.py"
Task: "RewriteStep in src/rag_service/pipeline/steps/rewrite.py"
Task: "RetrievalStep in src/rag_service/pipeline/steps/retrieval.py"
Task: "ReasoningStep in src/rag_service/pipeline/steps/reasoning.py"
Task: "GenerationStep in src/rag_service/pipeline/steps/generation.py"
Task: "VerificationStep in src/rag_service/pipeline/steps/verification.py"
Task: "ExecutionStep in src/rag_service/pipeline/steps/execution.py"

# Then sequentially:
Task: "Update steps/__init__.py exports"
Task: "Rewrite QueryCapability"
Task: "Verify service starts"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (2 tasks)
2. Complete Phase 2: Foundational (4 tasks)
3. Complete Phase 3: US1 Basic Pipeline (10 tasks)
4. **STOP and VALIDATE**: Test basic query pipeline independently
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready (6 tasks)
2. Add US1 Basic Pipeline → Test → MVP complete (10 tasks)
3. Add US2 Quality Modes → Test → All quality modes work (3 tasks)
4. Add US3 Prompt Externalization → Test → Zero hardcoded prompts (2 tasks)
5. Add US4 Regeneration Loop → Test → Auto-retry works (2 tasks)
6. Add US5 Streaming → Test → Unified streaming (3 tasks)
7. Polish → Final validation (4 tasks)

**Total: 30 tasks**

---

## Notes

- [P] tasks = different files, no dependencies
- [US] labels map tasks to user stories for traceability
- Steps delegate to existing strategies/capabilities — no reimplementation
- Reasoning and Execution start as pass-through — Protocol defined, logic added later
- PipelinePolicy reads from existing QueryConfig — no new env vars
- Should_abort replaces QueryQualityPromptRequired exception for control flow
- All timing handled by PipelineRunner — steps MUST NOT record their own timing
