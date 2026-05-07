# Feature Specification: RAG Service Architecture Refactoring

**Feature Branch**: `008-rag-architecture-refactor`
**Created**: 2026-05-07
**Status**: Draft
**Input**: User description: "Consolidate RAG Service architecture: merge 13+ Capabilities into 3, unify 3 parallel Gateways into 1 LiteLLM entry point, reduce 15+ API endpoints to 4-5, and simplify config from 941 lines to ~300 lines"
**Reference**: `docs/architecture-refactoring-spec.md`, `docs/compliance-check-report.md`

## Background

The RAG Service (Feature 001) was designed as an MVP with 4 API endpoints, 7 Capabilities, and 1 inference gateway. After iterations from Features 005/006/007, the codebase has drifted significantly from the original architecture:

| Metric | MVP Design | Current | Growth |
|--------|-----------|---------|--------|
| API Endpoints | 4 | 15+ | 3.7x |
| Capabilities | 7 | 13+ | 1.9x |
| Config Classes | 5 | 15+ | 3x |
| Config Lines | ~200 | 941 | 4.7x |
| Inference Gateways | 1 (LiteLLM) | 3 (exposed in parallel) | 3x |

Core problems identified through compliance review:
1. **Capability proliferation** — 5 Capabilities (KnowledgeQuery, ExternalKBQuery, QAPipeline, QueryQuality, ConversationalQuery) all do the same thing: receive a question, retrieve knowledge, generate an answer
2. **Gateway design intent violated** — LiteLLM was designed as the sole inference entry point, with HTTP Cloud and GLM as internal providers. Current code exposes all three as parallel Gateways that callers must choose between
3. **API surface bloat** — 4 separate query endpoints (`/ai/agent`, `/query`, `/external/query`, `/qa/query`) that all perform the same operation
4. **Configuration explosion** — 15+ Config classes where 5 would suffice

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Unified Query Interface (Priority: P1)

A developer wants to ask the RAG Service a question and get an answer. They should only need to know ONE endpoint regardless of whether the service uses Milvus or an external knowledge base, regardless of which LLM provider is configured, and regardless of whether query quality enhancement is enabled. The internal implementation details (retrieval backend, quality mode, LLM provider) should be invisible to the caller.

**Why this priority**: This is the core value proposition — the service answers questions. Today a caller must understand 5 different Capabilities and 4 different endpoints to ask a question. After refactoring, there is exactly one Capability and one endpoint.

**Independent Test**: Can be tested by sending the same question via the unified `POST /query` endpoint and verifying the response is identical regardless of which retrieval backend or quality mode is configured. All existing functionality (knowledge retrieval, answer generation, trace observability) must continue working.

**Acceptance Scenarios**:

1. **Given** the refactored service is running, **When** a developer sends `POST /api/v1/query` with a question, **Then** the response contains an answer, retrieved chunks, trace_id, and metadata — identical in structure to the current response
2. **Given** the service is configured with Milvus as retrieval backend, **When** the same query is sent, **Then** the answer uses Milvus-sourced context
3. **Given** the service is configured with external KB as retrieval backend, **When** the same query is sent, **Then** the answer uses external KB-sourced context — with no API changes required
4. **Given** the old endpoint `POST /api/v1/ai/agent` is called during transition period, **Then** it still works with a deprecation notice in the response headers
5. **Given** quality enhancement is enabled in configuration, **When** a query is sent, **Then** multi-turn dimension gathering or conversational slot extraction occurs transparently

---

### User Story 2 - Single Inference Gateway (Priority: P1)

A developer or operator configures the RAG Service to use different LLM providers (Ollama, OpenAI, Claude, GLM, HTTP Cloud). They should only interact with LiteLLM as the single inference entry point. HTTP Cloud and GLM should be internal provider implementations within LiteLLM, not separate Gateways that callers must choose between.

**Why this priority**: This corrects a fundamental design intent violation. The original architecture specified LiteLLM as the sole gateway; the current code incorrectly exposes three parallel gateways. Fixing this eliminates a whole class of configuration complexity.

**Independent Test**: Can be tested by configuring different providers (GLM, OpenAI, HTTP Cloud) and verifying that all inference calls go through LiteLLM without any caller-side changes. The `default_gateway` selector should be removed — callers never specify a gateway.

**Acceptance Scenarios**:

1. **Given** GLM provider is configured, **When** a query triggers inference, **Then** LiteLLM routes the call to GLM internally — the caller never specifies "glm" as a gateway
2. **Given** multiple providers are configured, **When** the operator changes the default provider in configuration, **Then** all subsequent queries use the new provider without any code changes
3. **Given** the unified LiteLLM gateway is in place, **When** a new provider needs to be added, **Then** only a configuration change is required — no new Gateway class is created

---

### User Story 3 - Simplified Configuration (Priority: P2)

An operator deploying the RAG Service wants to configure it via environment variables. They should deal with ~5 coherent configuration sections (Milvus, LiteLLM, Langfuse, Server, Query behavior) instead of 15+ scattered config classes. The configuration file should be understandable by reading it top-to-bottom once.

**Why this priority**: Configuration simplification reduces deployment errors and onboarding time. It is a direct consequence of the Capability and Gateway consolidation — fewer components mean fewer config sections.

**Independent Test**: Can be tested by deploying the service with a simplified `.env` file containing only 5 config sections and verifying all functionality works (querying, document management, tracing, health checks).

**Acceptance Scenarios**:

1. **Given** the refactored configuration, **When** an operator sets only 5 config sections (Milvus, LiteLLM, Langfuse, Server, Query), **Then** the service starts successfully with all features operational
2. **Given** the old environment variables (e.g., `CLOUD_COMPLETION_*`, `GLM_*`), **When** used during transition period, **Then** they are accepted with a deprecation warning and mapped to the new LiteLLM provider configuration
3. **Given** the configuration file, **When** a new team member reads it, **Then** they can understand the service's behavior without reading source code

---

### User Story 4 - Consistent API Surface (Priority: P2)

A developer integrating with the RAG Service wants a predictable, minimal API surface. They should find 4-5 endpoints with clear, non-overlapping responsibilities: query, manage documents, inspect traces, check health, and list models.

**Why this priority**: A clean API surface reduces integration complexity. Today's 15+ endpoints create confusion about which to use for what purpose.

**Independent Test**: Can be tested by updating the E2E test framework's RAGClient to use only the unified endpoints and verifying all existing E2E tests pass unchanged.

**Acceptance Scenarios**:

1. **Given** the refactored API, **When** a developer checks the API documentation, **Then** they see exactly 5 endpoints: `POST /query`, `GET /models`, `GET /traces/{id}`, `GET /health`, and `POST /documents`
2. **Given** the E2E test framework (Feature 002), **When** its RAGClient is updated to use `POST /query`, **Then** all existing test cases pass without modification
3. **Given** a streaming query request, **When** sent to `POST /query/stream`, **Then** the response streams correctly

---

### Edge Cases

- What happens when a caller sends a request with both `retrieval_backend="external_kb"` and `comp_id` missing?
- How does the system handle a request that specifies `quality_mode="conversational"` when Redis is not configured?
- What happens when the old `POST /ai/agent` endpoint is called after the transition period ends?
- How does the system behave when a provider configuration is invalid (wrong URL, expired API key)?
- What happens when the LiteLLM gateway needs to fall back from one provider to another?
- How does the unified QueryCapability handle the case where query_rewrite fails but the rest of the pipeline should continue?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a single query endpoint (`POST /query`) that handles all query types regardless of retrieval backend, quality mode, or LLM provider
- **FR-002**: System MUST consolidate 5 query-related Capabilities (KnowledgeQuery, ExternalKBQuery, QAPipeline, QueryQuality, ConversationalQuery) into a single QueryCapability with internal strategy switching
- **FR-003**: System MUST use LiteLLM as the sole inference entry point — HTTP Cloud and GLM MUST be internal provider implementations within LiteLLM, never exposed as separate Gateways
- **FR-004**: System MUST remove the `default_gateway` configuration selector — callers never specify which Gateway to use
- **FR-005**: System MUST consolidate DocumentManagement, MilvusKBUpload, and ModelDiscovery Capabilities into a single ManagementCapability
- **FR-006**: System MUST consolidate TraceObservation and HealthCheck Capabilities into a single TraceCapability
- **FR-007**: System MUST reduce configuration from 15+ Config classes to approximately 5 (Milvus, LiteLLM, Langfuse, Server, Query)
- **FR-008**: System MUST preserve all existing functionality — no feature regression is acceptable
- **FR-009**: System MUST maintain backward compatibility for at least one version by keeping old endpoints with deprecation notices
- **FR-010**: System MUST maintain the three-layer observability stack (LiteLLM/Phidata/Langfuse) unchanged
- **FR-011**: System MUST support configuration-driven strategy switching for retrieval (Milvus vs. External KB) without code changes
- **FR-012**: System MUST support configuration-driven strategy switching for quality enhancement (basic vs. dimension_gather vs. conversational) without code changes
- **FR-013**: System MUST update the E2E test framework's RAGClient to use the unified query endpoint
- **FR-014**: System MUST ensure the unified QueryRequest schema can express all parameters previously spread across QueryRequest, ExternalKBQueryRequest, and QAQueryRequest

### Key Entities

- **Unified QueryRequest**: A single request model consolidating question, retrieval backend selection, quality mode, session context, and common parameters (top_k, model_hint, stream, trace_id)
- **QueryResponse**: The response model containing answer, chunks, trace_id, and metadata — unchanged from current behavior
- **QueryConfig**: A single configuration section replacing QAConfig, QueryQualityConfig, ConversationalQueryConfig, ExternalKBConfig, and MilvusKBConfig — controlling retrieval backend, quality mode, and pipeline toggles
- **LiteLLM Provider Config**: Internal provider definitions within LiteLLM config, replacing CloudCompletionConfig and GLMConfig — callers never interact with these directly

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The service exposes no more than 5 API endpoints, down from 15+, while preserving all existing functionality
- **SC-002**: A developer can send a question to `POST /query` and receive a correct answer regardless of which retrieval backend or LLM provider is configured — zero code changes needed when switching backends
- **SC-003**: The configuration file is under 350 lines, down from 941, with no more than 6 configuration sections
- **SC-004**: LiteLLM is the only inference gateway exposed — no other Gateway class is importable from outside the LiteLLM module
- **SC-005**: All existing E2E tests pass after updating only the RAGClient endpoint URL — no test logic changes required
- **SC-006**: A new team member can understand the service's architecture by reading 3 Capability classes instead of 13+
- **SC-007**: The Capability Registry contains exactly 3 entries (Query, Management, Trace) instead of 13+
- **SC-008**: All old API endpoints (`/ai/agent`, `/external/query`, `/qa/query`) respond correctly during the transition period with a deprecation header
- **SC-009**: Switching between Milvus and External KB retrieval requires only a configuration change — no code modifications, no endpoint changes, no Capability selection by the caller
- **SC-010**: The three-layer observability stack continues to capture all metrics (tokens, cost, latency, steps, tools, prompt versions) unchanged

## Assumptions

1. **No feature regression**: All current functionality (query rewrite, hallucination detection, quality enhancement, conversational query, streaming) must work after refactoring
2. **Backward compatibility period**: Old endpoints will be kept for one release cycle with deprecation headers before removal
3. **Configuration migration**: Old environment variables will be accepted during transition with deprecation warnings logged
4. **Existing data models preserved**: 006/007 data models (DimensionInfo, SessionState, BeliefState, etc.) remain unchanged as they are consumed by quality strategies
5. **External services unchanged**: Prompt Service (003) and E2E Test framework (002) are not refactored — only RAGClient endpoint URL is updated in 002
6. **Phase ordering**: Gateway consolidation is done first (lowest risk), followed by Capability merging, then API endpoint consolidation, then configuration cleanup

## Out of Scope

- Refactoring Prompt Service (Feature 003) — it is an independent service
- Refactoring E2E Test framework (Feature 002) beyond updating RAGClient endpoint
- Changing the three-layer observability architecture
- Adding new features — this is purely a consolidation refactoring
- Modifying data models for Features 006/007
- Performance optimization — this refactoring is about structural clarity, not speed
- Changing the Milvus or External KB client implementations
