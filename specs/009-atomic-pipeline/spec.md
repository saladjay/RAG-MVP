# Feature Specification: Atomic Pipeline Refactor

**Feature Branch**: `009-atomic-pipeline`
**Created**: 2026-05-07
**Status**: Draft
**Input**: Decompose QueryCapability (454-line god object) into atomic capabilities with a lightweight pipeline orchestrator. Reference: `phase1-atomic-capability-spec.md`

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Basic Query Pipeline (Priority: P1)

As a service operator, I want queries to flow through a configurable pipeline of atomic steps, so that each step can be independently enabled, disabled, or swapped without touching other steps.

**Why this priority**: This is the foundation — without a working pipeline runner and at least the core steps (retrieval + generation), nothing else matters. This is the MVP.

**Independent Test**: Send a basic query (`{"query": "What is RAG?"}`) through the unified API endpoint and receive a correct answer with source citations. All pipeline steps execute in order, and timing metadata is returned.

**Acceptance Scenarios**:

1. **Given** a running service with default configuration, **When** a user sends `POST /api/v1/query` with `{"query": "What is RAG?"}`, **Then** the response contains an answer, sources, and metadata with per-step timing
2. **Given** a pipeline with rewrite disabled, **When** the same query is sent, **Then** the answer is still generated but timing metadata shows rewrite was skipped
3. **Given** a pipeline step fails (e.g., hallucination check), **When** the query is processed, **Then** the service returns a valid answer with a degraded quality indicator rather than an error

---

### User Story 2 - Quality Enhancement Modes (Priority: P2)

As a service operator, I want to switch between different query enhancement modes (basic, dimension gathering, conversational) by changing configuration, so that the pipeline adapts its extraction step without code changes.

**Why this priority**: Multi-turn quality enhancement is a key differentiator. After the basic pipeline works, this enables the existing quality strategies to work through the new architecture.

**Independent Test**: Configure `quality_mode=dimension_gather`, send a vague query, receive a follow-up prompt asking for missing dimensions (e.g., year, document type). Then send a complete query and receive a full answer.

**Acceptance Scenarios**:

1. **Given** `quality_mode=dimension_gather` and a vague query like "show me the policy", **When** the query is processed, **Then** the service returns a prompt asking for missing dimensions instead of an answer
2. **Given** `quality_mode=conversational` and a query with colloquial terms, **When** the query is processed, **Then** the service maps colloquial terms to formal ones and retrieves relevant results
3. **Given** `quality_mode=basic`, **When** any query is processed, **Then** the extraction step is a pass-through with zero overhead

---

### User Story 3 - Prompt Externalization (Priority: P3)

As a service operator, I want all pipeline prompts to be managed through the prompt management service, so that I can update prompts without redeploying the service and A/B test different prompt versions.

**Why this priority**: Currently the generation step has a hardcoded prompt while other steps use the prompt service. Fixing this inconsistency improves operational flexibility.

**Independent Test**: Update the answer generation prompt template in the prompt service, send a query, and verify the new prompt is used in the response.

**Acceptance Scenarios**:

1. **Given** the prompt service has template `qa_answer_generate` configured, **When** a query is processed, **Then** the generation step uses that template instead of a hardcoded prompt
2. **Given** the prompt service is unavailable, **When** a query is processed, **Then** the generation step falls back to the default prompt and still produces an answer

---

### User Story 4 - Regeneration Loop (Priority: P4)

As a service operator, I want the pipeline to automatically retry answer generation when hallucination is detected, so that low-quality answers are corrected without manual intervention.

**Why this priority**: This uses the previously-unused `max_regen_attempts` config and adds intelligence to the pipeline. It depends on both verification and generation working correctly first.

**Independent Test**: Set `max_regen_attempts=2`, send a query that initially produces a hallucinated answer, observe the pipeline regenerates until a clean answer is produced or attempts are exhausted.

**Acceptance Scenarios**:

1. **Given** `max_regen_attempts=1` and hallucination is detected on first generation, **When** the pipeline runs, **Then** a second generation attempt is made with a stricter prompt
2. **Given** `max_regen_attempts=0`, **When** hallucination is detected, **Then** the answer is returned as-is with a warning
3. **Given** `max_regen_attempts=2` and all attempts fail verification, **Then** the best answer is returned with a quality warning

---

### User Story 5 - Streaming Unification (Priority: P5)

As a service operator, I want streaming queries to use the same pipeline steps as synchronous queries, so that feature parity is maintained without code duplication.

**Why this priority**: Currently `stream_execute()` duplicates the pipeline logic. Unifying it reduces maintenance burden but requires the pipeline runner to support async generators.

**Independent Test**: Send a streaming query and verify tokens are yielded in real-time while still benefiting from extraction, rewrite, and retrieval steps.

**Acceptance Scenarios**:

1. **Given** a streaming request, **When** the pipeline runs, **Then** tokens are streamed to the client as they are generated
2. **Given** a streaming request with `quality_mode=dimension_gather` and a vague query, **When** the extraction step determines more info is needed, **Then** a prompt message is streamed back instead of an answer

---

### Edge Cases

- What happens when a pipeline step sets `should_abort` after retrieval has already populated chunks? The pipeline stops, and the abort prompt is returned; intermediate data is discarded.
- What happens when the memory capability (Redis) is unavailable but `quality_mode=basic`? The pipeline proceeds normally since basic mode does not use memory.
- What happens when two steps both try to modify `processed_query`? The last executed step wins, and the pipeline context tracks the full history for observability.
- What happens when `max_regen_attempts > 0` but verification is disabled? The regeneration loop is skipped since there is no verification result to trigger it.
- What happens when a custom step is added to the pipeline that raises an unexpected exception? The runner catches the exception, logs a warning, applies fallback behavior, and continues to the next step.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST decompose the query processing pipeline into discrete, independently executable atomic steps
- **FR-002**: Each atomic step MUST read from and write to a shared, typed context object that flows through the entire pipeline
- **FR-003**: The system MUST provide a pipeline runner that executes a configurable list of steps in sequence
- **FR-004**: The pipeline runner MUST support per-step skip control based on policy configuration (enable/disable flags)
- **FR-005**: The pipeline runner MUST record per-step execution timing automatically without individual steps implementing their own timers
- **FR-006**: Any pipeline step MUST be able to signal a pipeline abort (stop processing and return a prompt to the user) without throwing an exception
- **FR-007**: The pipeline runner MUST distinguish between core errors (retrieval failure, generation failure) that halt the pipeline and non-core errors that allow graceful degradation
- **FR-008**: The system MUST fix the existing query rewrite wiring bug where the rewrite capability returns the original query due to missing LLM client initialization
- **FR-009**: The system MUST externalize all pipeline prompts through the prompt management service, eliminating hardcoded prompt strings
- **FR-010**: The system MUST support a regeneration loop: when hallucination is detected, the pipeline can re-execute generation and verification up to a configurable number of attempts
- **FR-011**: The system MUST support streaming queries through the same pipeline steps as synchronous queries, avoiding code duplication
- **FR-012**: The system MUST preserve all existing API endpoints and response formats — callers experience zero breaking changes
- **FR-013**: The system MUST support the three existing quality modes (basic, dimension_gather, conversational) as extraction step sub-strategies
- **FR-014**: The system MUST support the two existing retrieval backends (milvus, external_kb) as retrieval step sub-strategies
- **FR-015**: Pipeline policy configuration MUST be derived from existing configuration sources — no new environment variables or configuration files
- **FR-016**: The system MUST define Protocol interfaces for all 8 atomic capability types (planning, reasoning, retrieval, rewrite, memory, extraction, generation, execution), even if some start as pass-through implementations
- **FR-017**: The reasoning capability MUST be a separate pipeline step between retrieval and generation, initially implemented as pass-through, with a defined interface for future chain-of-thought and evidence synthesis
- **FR-018**: The execution capability MUST be a separate pipeline step after verification, initially implementing the current quality.post_process() logic, with a defined interface for future tool calling and workflow execution

### Key Entities

- **Pipeline Context**: The shared state object flowing through the pipeline. Contains the original query, processed query, retrieved chunks, reasoning results, generated answer, verification results, quality metadata, control signals (abort), and timing data
- **Pipeline Policy**: Execution control parameters — step enable/disable flags, quality mode, retrieval backend, reasoning toggle, hallucination threshold, max regeneration attempts, prompt template identifiers
- **Pipeline Step (Atomic Capability)**: A single, focused operation in the pipeline. 8 types: planning, reasoning, retrieval, rewrite, memory, extraction, generation, execution. Each step reads and writes the pipeline context
- **Memory Store**: Session and belief state persistence. Manages multi-turn conversation state for quality enhancement modes
- **Pipeline Runner**: The orchestrator that executes the step list, applies policy controls, handles errors uniformly, and records timing. Also serves as the "Planning" capability — deciding which steps to run and in what order

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All existing API endpoints produce identical responses before and after the refactor (zero regression)
- **SC-002**: The query capability implementation is reduced from 454 lines to under 50 lines (orchestration only), with business logic distributed across atomic step files
- **SC-003**: Each atomic step is independently testable with a mock pipeline context — no step requires the full pipeline to verify correctness
- **SC-004**: Adding a new pipeline step requires creating a single new file and adding one line to the step list — no changes to the runner, context, or other steps. Reasoning and Execution steps follow this pattern (Protocol defined, initially pass-through)
- **SC-005**: All prompts used in the pipeline are managed through the prompt service — zero hardcoded prompt strings remain in step implementations
- **SC-006**: The regeneration loop (`max_regen_attempts > 0`) correctly re-executes generation and verification when hallucination is detected
- **SC-007**: Streaming and synchronous queries share the same step implementations — no duplicated pipeline logic
- **SC-008**: No new external dependencies are introduced — all abstractions use standard library and existing project dependencies
- **SC-009**: The service starts correctly with minimal configuration and all three quality modes (basic, dimension_gather, conversational) work as expected

## Assumptions

- The existing `strategies/` directory (RetrievalStrategy, QualityStrategy) will be retained and used by the new atomic steps via delegation
- The existing legacy capabilities (QueryQualityCapability, ConversationalQueryCapability, etc.) will be retained as internal implementations delegated to by the new steps
- The `ManagementCapability` and `TraceCapability` are not affected by this refactor
- The API layer (`unified_routes.py`, `unified_schemas.py`) is not modified
- The configuration system (`config.py`) is not modified — `PipelinePolicy` is constructed from existing `QueryConfig` values
- Redis-backed session stores remain the memory backend for quality enhancement modes
- The streaming architecture may initially duplicate some logic, with full unification as a stretch goal
