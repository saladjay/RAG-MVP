# Implementation Plan: RAG Service MVP - AI Component Validation Platform

**Branch**: `001-rag-service-mvp` | **Date**: 2026-03-20 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-rag-service-mvp/spec.md`

**Additional Requirement**: User specified detailed test engineering with complete unit tests for each node implementation.

**Unified Tracing Architecture**: Three-layer observability stack with unified trace_id propagation:
- LLM Layer (LiteLLM): Model invocation gateway + billing + strategy control
- Agent Layer (Phidata): AI task execution behavior observation and orchestration
- Prompt Layer (Langfuse): Prompt template management and trace correlation

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Build a minimal viable RAG (Retrieval-Augmented Generation) service as an HTTP API to validate multiple AI development components. The service will demonstrate end-to-end RAG functionality including knowledge base queries via Milvus, multi-model inference through LiteLLM gateway, and comprehensive three-layer observability (LiteLLM → Phidata → Langfuse) for complete request-to-cost-to-quality optimization. The MVP focuses on component validation rather than production deployment.

**Technical Approach**: Python-based web service using FastAPI, with Phidata for agent orchestration, LiteLLM for unified model gateway access, Milvus for vector knowledge storage, and Langfuse for prompt management. A **unified capability interface layer** sits between HTTP endpoints and underlying components, ensuring components (Phidata, LiteLLM, Milvus, Langfuse) are never directly exposed to the API layer. A unified `trace_id` propagates across all layers (Phidata → CrewAI → LiteLLM) enabling complete observability. All components will be tested with real implementations (minimal mocks per constitution) using pytest with uv for environment management.

**Core Architecture Principle**: The capability interface layer is the **CORE** of the service design. HTTP routes ONLY interact with capability interfaces, not with component implementations directly. This enables:
- Component swapping without API changes
- Clean abstraction boundaries
- Testable interfaces with real or mocked implementations
- Clear separation between external API contract and internal implementation

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI, Phidata, LiteLLM, Langfuse SDK, pymilvus
**Storage**: Milvus vector database for knowledge chunks
**Testing**: pytest with pytest-asyncio for async testing, pytest-cov for coverage
**Target Platform**: Linux/macOS/Windows (development environment)
**Project Type**: web-service (REST API)
**Performance Goals**: <10 seconds end-to-end query response time (p95)
**Constraints**:
  - Non-blocking observability (tracing failures must not halt requests)
  - Support local and cloud model providers via single gateway
  - Must use uv for Python dependency management
**Scale/Scope**:
  - 3-5 model providers for validation
  - Support 10 concurrent requests
  - Knowledge base size: ~1000 documents for MVP validation

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Documentation Standards (Principle I & II)
- [x] All files will include header with content and API brief description
- [x] Documentation headers will be updated immediately on content changes
- [x] Call flow diagrams will be generated at `.specify/specs/001-rag-service-mvp/research.md`
- [x] Architecture documentation will reference all APIs (document location → function name)

### Testing Standards (Principle III & IV)
- [x] Tests will use real implementations (minimal mocks)
  - Only external services (cloud APIs) may use mocks when test environments unavailable
  - Local components (Milvus, LiteLLM local models) will use real instances in tests
- [x] Server tests will include server startup scripts
- [x] Python execution will use `uv`-managed virtual environment
- [x] Blocking points for real test implementation will be documented

### Component Governance (Principle V)
- [x] New base components have not been created without approval
  - This project uses existing components: FastAPI, Phidata, LiteLLM, Langfuse, Milvus
- [x] Existing base components are documented
  - Will document usage patterns in research.md
- [x] Package management uses `uv` for Python dependencies

### Additional Test Coverage Requirement (User Specified)
- [x] Each node/implementation will have a complete set of unit tests
  - Test structure: tests/unit/{module}/test_{component}.py
  - Target coverage: 80%+ per constitution
  - Integration tests for API endpoints
  - Contract tests for external service integrations

## Project Structure

### Documentation (this feature)

```text
specs/001-rag-service-mvp/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   ├── api-contract.md      # HTTP API contract
│   └── integration-contract.md  # External service integrations
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/
├── rag_service/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry point
│   ├── config.py               # Configuration management
│   ├── capabilities/           # Unified capability interface layer (CORE ARCHITECTURE)
│   │   ├── __init__.py
│   │   ├── base.py            # Base Capability abstract class
│   │   ├── knowledge_query.py # KnowledgeQueryCapability (wraps Milvus)
│   │   ├── model_inference.py # ModelInferenceCapability (wraps LiteLLM)
│   │   ├── trace_observation.py # TraceObservationCapability (wraps Langfuse/Phidata)
│   │   ├── document_management.py # DocumentManagementCapability (wraps Milvus)
│   │   ├── model_discovery.py # ModelDiscoveryCapability (wraps LiteLLM)
│   │   └── health_check.py    # HealthCheckCapability (checks all components)
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py           # API route definitions (ONLY uses capabilities)
│   │   └── schemas.py          # Pydantic models for request/response
│   ├── core/
│   │   ├── __init__.py
│   │   ├── agent.py            # Phidata agent orchestration
│   │   ├── tracing.py          # Langfuse trace management
│   │   └── exceptions.py       # Custom exception definitions
│   ├── retrieval/
│   │   ├── __init__.py
│   │   ├── knowledge_base.py   # Milvus knowledge base interface (internal component)
│   │   └── embeddings.py       # Embedding generation
│   ├── inference/
│   │   ├── __init__.py
│   │   ├── gateway.py          # LiteLLM gateway interface (internal component)
│   │   └── models.py           # Model provider configurations
│   └── observability/
│       ├── __init__.py
│       ├── langfuse_client.py  # Langfuse SDK wrapper (Prompt Layer)
│       ├── litellm_observer.py # LiteLLM metrics capture (LLM Layer)
│       ├── phidata_observer.py  # Phidata behavior tracking (Agent Layer)
│       ├── trace_manager.py     # Unified trace_id propagation
│       └── metrics.py          # Cross-layer metrics aggregation

tests/
├── __init__.py
├── conftest.py                 # pytest fixtures and configuration
├── unit/
│   ├── test_config.py
│   ├── test_agent.py
│   ├── test_tracing.py
│   ├── test_knowledge_base.py
│   ├── test_gateway.py
│   ├── test_observability.py
│   ├── test_litellm_observer.py  # LiteLLM layer tests
│   ├── test_phidata_observer.py   # Phidata layer tests
│   └── test_unified_trace.py      # Cross-layer trace tests
├── integration/
│   ├── test_api_endpoints.py   # Full API integration tests
│   ├── test_e2e_flow.py        # End-to-end RAG flow tests
│   └── test_trace_correlation.py # Multi-layer trace correlation
└── contract/
    ├── test_milvus_contract.py # Milvus integration contract
    ├── test_litellm_contract.py # LiteLLM integration contract
    └── test_langfuse_contract.py # Langfuse integration contract

pyproject.toml                  # uv-managed dependencies
uv.lock                         # uv lock file
README.md                        # Project documentation
docker-compose.yml              # Local development environment (optional)
```

**Structure Decision**: Single project (Option 1) with modular package structure. The `src/rag_service/` directory contains all application code organized by responsibility (api, core, retrieval, inference, observability). Tests mirror the source structure with unit/, integration/, and contract/ directories. Using uv for dependency management satisfies constitution Principle VI.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | No constitution violations identified | All principles (I-VI) are addressed in plan |

## Phase 0: Research & Decisions

**Status**: COMPLETE

### Research Tasks Completed

1. **Python version selection**: ✅ Python 3.11 selected
2. **Phidata integration patterns**: ✅ Agent-based with tool retrieval pattern
3. **Milvus Python SDK**: ✅ pymilvus 2.3+ with connection pooling
4. **LiteLLM configuration**: ✅ Centralized YAML config with environment variables
5. **Langfuse async integration**: ✅ Async SDK with non-blocking flush
6. **FastAPI testing**: ✅ pytest with TestClient and server fixtures
7. **Vector embedding model**: ✅ OpenAI text-embedding-3-small
8. **Unified tracing architecture**: ✅ Three-layer observability (LiteLLM/Phidata/Langfuse) with unified trace_id
9. **Cross-layer correlation**: ✅ Trace chain: Phidata → CrewAI → LiteLLM with cost-to-quality optimization loop

**Output**: See [research.md](./research.md) for decisions and rationale.

## Phase 1: Design Artifacts

**Status**: COMPLETE

### Data Model

**Status**: COMPLETE
**Output**: See [data-model.md](./data-model.md) for entity definitions and relationships.

- 7 core entities defined (QueryRequest, QueryResponse, RetrievedChunk, TraceRecord, TraceSpan, ModelProvider, Document)
- Entity relationships diagram
- State machines for request and trace lifecycles
- Storage mapping to Milvus and Langfuse

### API Contracts

**Status**: COMPLETE
**Output**: See [contracts/](./contracts/) directory for interface specifications.

- **[api-contract.md](./contracts/api-contract.md)**: HTTP API endpoints, request/response schemas, error codes
- **[integration-contract.md](./contracts/integration-contract.md)**: External service integration contracts (Milvus, LiteLLM, Langfuse, OpenAI)

### Quickstart Guide

**Status**: COMPLETE
**Output**: See [quickstart.md](./quickstart.md) for setup and run instructions.

- Prerequisites and installation steps
- External service setup (Docker Compose, manual)
- Environment configuration
- First query example
- Testing and troubleshooting guide

## Phase 2: Implementation Tasks

**Status**: PENDING (requires `/speckit.tasks` command)
**Output**: Tasks will be generated by `/speckit.tasks` command.

## Implementation Phases Summary

| Phase | Deliverables | Status |
|-------|--------------|--------|
| 0 | research.md with all technical decisions | COMPLETE |
| 1 | data-model.md, contracts/, quickstart.md | COMPLETE |
| 2 | tasks.md with implementation tasks | PENDING |
