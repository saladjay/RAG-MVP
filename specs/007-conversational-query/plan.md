# Implementation Plan: Conversational Query Enhancement Module

**Branch**: `007-conversational-query` | **Date**: 2026-04-10 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/007-conversational-query/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

This feature adds a conversational query enhancement module to the RAG service that enables multi-turn dialogue for query refinement, colloquial expression recognition, and intelligent query expansion. The system maintains conversation context, maps informal language to formal terminology, and generates multiple query variations for improved retrieval.

**Technical Approach**:
- Create a new `ConversationalQueryCapability` that manages multi-turn dialogue state
- Implement belief state tracking with slot filling for query dimensions
- Build colloquial term mapping system with knowledge graph for related concepts
- Generate three independent query variations (q1, q2, q3) with must_include terms and keyword expansion
- Integrate with existing QA Pipeline (feature 005) as a pre-processing step
- Use Prompt Service (feature 003) for conversation and query generation templates
- Store conversation state in Redis with 15-minute TTL and 10-turn max limit

**2025 Document Analysis Updates** (2026-04-09):
Based on analysis of 38 documents from the 2025 directory, the following enhancements have been incorporated:
- **New meeting types**: 职工代表大会, 工会会员代表大会, 工作会议, 启动会
- **New colloquial mappings**: 会议记录→会议纪要, 职代会→职工代表大会, 三八活动→妇女节活动
- **Extended organization entities**: 专业委员会 (审计委员会, 产品技术委员会), 领导小组
- **Enhanced content categories**: 工会工作 extended with subcategories, new 专业委员会 category

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI, LiteLLM, Pydantic, Prompt Service SDK, Redis (aioredis)
**Storage**: Redis for conversation state (TTL-based expiration)
**Testing**: pytest with pytest-asyncio, real implementations (minimal mocks per constitution)
**Target Platform**: Linux server (FastAPI/uvicorn)
**Project Type**: Web service capability extension
**Performance Goals**: <3 seconds p95 for query processing including conversation turns
**Constraints**:
  - Single-instance deployment with simple failure recovery (99.5% availability target)
  - Must propagate trace_id across all service calls
  - Structured JSON logging for all operations
**Scale/Scope**:
  - Session timeout: 15 minutes inactivity
  - Max conversation turns: 10 per session
  - Conversation state storage: Redis with automatic TTL expiration
  - Support 10 business domains with domain-specific query generation

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Documentation Standards (Principle I & II)
- [x] All files will include header with content and API brief description
- [x] Documentation headers will be updated immediately on content changes
- [x] Call flow diagrams generated at `research.md` with API references
- [x] Architecture documentation references all APIs (document location → function name)

### Testing Standards (Principle III & IV)
- [x] Tests will use real implementations (minimal mocks)
- [x] Server tests will include server startup scripts
- [x] Python execution will use `uv`-managed virtual environment
- [x] Blocking points documented: Redis connection, LLM availability

### Component Governance (Principle V)
- [x] New base components have not been created without approval (extending existing Capability pattern)
- [x] Existing base components are documented (Capability base class in `rag_service/capabilities/base.py`)
- [x] Package management uses `uv` for Python dependencies

**POST-DESIGN STATUS**: All gates passed. No violations.

## Project Structure

### Documentation (this feature)

```text
specs/007-conversational-query/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   └── conversational_query_api.md
└── spec.md              # Feature specification (input)
```

### Source Code (repository root)

```text
src/rag_service/
├── capabilities/
│   ├── base.py                    # Existing: Capability base class
│   ├── conversational_query.py    # NEW: Conversational query capability
│   └── ...
├── models/
│   └── conversational_query.py    # NEW: Conversational query data models
├── services/
│   ├── belief_state_store.py      # NEW: Redis belief state store
│   └── colloquial_mapper.py       # NEW: Colloquial term mapping service
├── api/
│   └── qa_schemas.py              # MODIFY: Add conversational query schemas
└── config.py                      # MODIFY: Add conversational query settings

tests/
├── unit/
│   └── test_conversational_query.py      # NEW: Unit tests
├── integration/
│   └── test_conversational_query_e2e.py  # NEW: Integration tests
└── contract/
    └── test_conversational_query_api.py   # NEW: API contract tests
```

**Structure Decision**: Single project structure (Option 1). The conversational query enhancement is a capability module within the existing RAG service, following the established Capability Interface Layer pattern.

## Complexity Tracking

> **No violations to report** - This feature extends the existing architecture without violating any constitution principles.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | N/A | N/A |
