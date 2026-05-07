# Implementation Plan: RAG QA Pipeline

**Feature Branch**: `005-rag-qa-pipeline`
**Status**: Planning
**Created**: 2026-04-01

## Technical Context

### Architecture Overview

This feature extends the existing RAG Service (Spec 001) by adding a complete question-answering pipeline that orchestrates query rewriting, external knowledge base retrieval, answer generation, and hallucination detection.

**Existing Components**:
- `ExternalKBClient`: HTTP client for external knowledge base queries
- `LiteLLMGateway`: Multi-provider LLM inference gateway
- `ModelInferenceCapability`: LLM inference wrapper
- `ExternalKBQueryCapability`: External KB query wrapper
- `LangfuseClient`: Observability and prompt management

**New Components to Add**:
- `QAPipelineCapability`: Orchestrates the complete QA workflow
- `QueryRewriteCapability`: Rewrites user queries for better retrieval
- `HallucinationDetectionCapability`: Verifies answers against retrieved content
- `DefaultFallbackService`: Manages predefined fallback responses
- New API routes: `POST /qa/query`, `POST /qa/query/stream`

### Technology Stack

**Existing**:
- FastAPI (web framework)
- LiteLLM (model gateway)
- httpx (async HTTP client)
- Pydantic (validation)
- Langfuse (observability)

**New Additions**:
- No new framework dependencies - uses existing stack
- Similarity scoring for hallucination detection (cosine similarity via sentence-transformers)

### Integration Points

1. **External KB Client** (from Spec 001):
   - Use existing `ExternalKBClient.query()` method
   - Add query parameters for document type filters

2. **LiteLLM Gateway** (from Spec 001):
   - Use existing `LiteLLMGateway.acomplete()` for query rewriting
   - Use existing `LiteLLMGateway.acomplete()` for answer generation
   - Use existing `LiteLLMGateway.acomplete()` for hallucination detection

3. **Observability** (from Spec 001/003):
   - Use existing `LangfuseClient` for prompt templates
   - Use existing trace propagation for end-to-end tracking

### Known Unknowns (NEEDS CLARIFICATION)

1. **Hallucination Detection Algorithm**: Need to decide between:
   - Similarity-based comparison (answer embeddings vs retrieved content embeddings)
   - LLM-based verification (prompt LLM to check factual claims)
   - Hybrid approach

2. **Default Fallback Messages**: Need to determine:
   - Who provides the fallback message templates?
   - Should fallback messages be configurable per company/tenant?
   - How many fallback variations are needed?

3. **Query Rewriting Strategy**: Need to decide:
   - How aggressive should rewriting be?
   - Should rewriting be context-aware (company, document type)?
   - How to handle rewriting failures?

4. **Streaming Implementation**: Need to clarify:
   - Should hallucination detection be bypassed for streaming?
   - How to handle streaming when regeneration is needed?

5. **Answer Regeneration**: Need to determine:
   - Max retry attempts when hallucination detected?
   - Fallback strategy when regeneration fails?

### Dependencies

**Internal**:
- Spec 001: External KB client, LiteLLM gateway, capability interface pattern
- Spec 003: Optional prompt template management

**External**:
- External KB API must remain accessible
- LiteLLM gateway must support Chinese models
- Sentence-transformers for similarity scoring (if using similarity-based hallucination detection)

## Constitution Check

### I. Comprehensive Documentation (NON-NEGOTIABLE)
- [ ] All new files will include headers with content/API descriptions
- [ ] Headers updated immediately when content changes
- [ ] Call flow diagram to be created in research.md after main logic

### II. Architecture Visualization (MANDATORY)
- [ ] Compressed view call flow diagram at research.md
- [ ] Maps every API call (document location → function name)

### III. Real-First Testing (NON-NEGOTIABLE)
- [ ] Integration tests with real external KB
- [ ] Integration tests with real LiteLLM gateway
- [ ] Mock testing only for unavailable external services
- [ ] Report blocking points immediately

### IV. Environment Discipline (MANDATORY)
- [ ] Server tests start server script before execution
- [ ] Use `uv` for all Python dependency management

### V. Base Component Governance (NON-NEGOTIABLE)
- [ ] No new base components without formal approval
- [ ] Use existing capability interface pattern
- [ ] Any base component modifications require approval

### VI. Package Management Discipline (MANDATORY)
- [ ] All dependencies via `uv`
- [ ] No pip installation without explicit justification

### Gate Status
**PASS** - No constitution violations identified. All requirements can be met with existing architecture.

## Phase 0: Research & Design Decisions

### Tasks

1. **Hallucination Detection Algorithm Research**
   - Evaluate similarity-based vs LLM-based approaches
   - Determine precision/recall trade-offs
   - Document decision in research.md

2. **Query Rewriting Strategy Research**
   - Analyze rewriting patterns for Chinese queries
   - Determine context requirements (company ID, document type)
   - Document prompt templates

3. **Default Fallback Design**
   - Design fallback message structure
   - Determine configuration approach
   - Document template format

4. **Streaming Architecture Design**
   - Design streaming flow with hallucination detection
   - Determine when to bypass detection for streaming
   - Document approach

5. **API Contract Design**
   - Design request/response schemas
   - Define error response formats
   - Document streaming protocol

### Output
- `research.md` with all decisions and rationale

## Phase 1: Design & Contracts

### Tasks

1. **Data Model**
   - Define QA pipeline entities
   - Define request/response schemas
   - Define internal data structures
   - Output: `data-model.md`

2. **API Contracts**
   - Define QA query endpoint contract
   - Define streaming endpoint contract
   - Define error response formats
   - Output: `contracts/qa-api.yaml`

3. **Quick Start Guide**
   - Installation instructions
   - Configuration examples
   - Usage examples
   - Output: `quickstart.md`

4. **Agent Context Update**
   - Run `.specify/scripts/powershell/update-agent-context.ps1 -AgentType claude`

### Output
- `data-model.md`
- `contracts/qa-api.yaml`
- `quickstart.md`
- Updated agent context

## Phase 2: Implementation

### 2.1 Core Capabilities

#### Query Rewrite Capability
**File**: `src/rag_service/capabilities/query_rewrite.py`
- Rewrite user queries for better retrieval
- Use LLM with prompt templates
- Fallback to original query on failure
- Input: original query, context (company ID, document type)
- Output: rewritten query, rewrite status

#### Hallucination Detection Capability
**File**: `src/rag_service/capabilities/hallucination_detection.py`
- Compare generated answers against retrieved content
- Use similarity-based or LLM-based verification
- Return confidence score and flagged claims
- Input: generated answer, retrieved chunks
- Output: verification result, confidence, flagged sections

#### QA Pipeline Capability
**File**: `src/rag_service/capabilities/qa_pipeline.py`
- Orchestrate complete QA workflow
- Coordinate: rewrite → retrieve → generate → verify
- Handle fallback and error cases
- Input: user query, optional context
- Output: answer with sources, hallucination status

#### Default Fallback Service
**File**: `src/rag_service/services/default_fallback.py`
- Manage predefined fallback messages
- Return appropriate fallback based on error type
- Support templated responses with placeholders
- Methods: `get_fallback(error_type, context)`

### 2.2 API Routes

#### QA Query Endpoint
**File**: `src/rag_service/api/qa_routes.py`
- `POST /qa/query` - Non-streaming QA
- `POST /qa/query/stream` - Streaming QA
- Request: `{query, context?, options?}`
- Response: `{answer, sources, hallucination_status, metadata}`

#### Request/Response Schemas
**File**: `src/rag_service/api/qa_schemas.py`
- `QAQueryRequest`: Query request schema
- `QAQueryResponse`: Query response schema
- `HallucinationStatus`: Hallucination detection result
- `QASourceInfo`: Source document information

### 2.3 Configuration

**File**: `src/rag_service/config.py`
- Add `QAConfig` section:
  - `enable_query_rewrite`: bool
  - `enable_hallucination_check`: bool
  - `hallucination_threshold`: float
  - `fallback_messages`: dict
  - `max_regen_attempts`: int

### 2.4 Prompt Templates

**File**: `rag_service/prompts/qa_prompts.yaml` (or Langfuse)
- `query_rewrite`: Prompt for query rewriting
- `answer_generation`: Prompt for answer generation
- `hallucination_check`: Prompt for verification

### 2.5 Observability

- Trace ID propagation through entire pipeline
- Log each stage (rewrite, retrieve, generate, verify)
- Timing metrics for each stage
- Hallucination detection metrics

## Phase 3: Testing

### 3.1 Unit Tests

**File**: `tests/unit/test_query_rewrite.py`
- Test query rewriting logic
- Test fallback behavior
- Test error handling

**File**: `tests/unit/test_hallucination_detection.py`
- Test similarity-based detection
- Test LLM-based detection
- Test confidence scoring

**File**: `tests/unit/test_qa_pipeline.py`
- Test pipeline orchestration
- Test fallback scenarios
- Test error propagation

### 3.2 Integration Tests

**File**: `tests/integration/test_qa_pipeline_e2e.py`
- Test complete pipeline with real external KB
- Test complete pipeline with real LiteLLM
- Test default fallback scenarios
- Test hallucination detection and regeneration

**File**: `tests/integration/test_qa_api.py`
- Test QA query endpoint
- Test streaming endpoint
- Test error responses

### 3.3 Performance Tests

- End-to-end latency under 10 seconds
- Concurrent query handling
- Memory usage monitoring

## Phase 4: Documentation & Deployment

### 4.1 Documentation

**File**: `docs/qa-pipeline-architecture.md`
- Architecture overview
- Call flow diagram
- Component interactions

**File**: `docs/qa-pipeline-api.md`
- API reference
- Request/response examples
- Error codes

### 4.2 Deployment

- Update deployment configurations
- Add environment variables for new features
- Update health check endpoints

## Success Criteria Verification

- [ ] SC-001: End-to-end latency < 10s (95th percentile)
- [ ] SC-002: Query rewriting improves relevance by 20%
- [ ] SC-003: 90% of answers include accurate citations
- [ ] SC-004: 95% of answers are helpful (manual review)
- [ ] SC-005: 90% precision for hallucination detection
- [ ] SC-006: Fallback within 2 seconds
- [ ] SC-007: 99.5% uptime (excl. external deps)

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Hallucination detection produces false positives | Poor UX | Tunable threshold, user feedback |
| Query rewriting degrades quality | Poor retrieval | Fallback to original, logging |
| External KB rate limits | Slow responses | Caching, retry logic |
| LLM latency > 10s | Fails SC-001 | Async processing, timeout handling |
| High token usage | Cost overruns | Token counting, budget alerts |

## Dependencies Checklist

- [ ] External KB client from Spec 001 is functional
- [ ] LiteLLM gateway from Spec 001 is configured
- [ ] Prompt templates are defined (in Langfuse or YAML)
- [ ] Default fallback messages are provided
- [ ] Test environment with real external KB
- [ ] Test environment with real LiteLLM gateway
