# Implementation Plan: Query Quality Enhancement Module

**Branch**: `006-query-quality-enhancement` | **Date**: 2026-04-09 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/006-query-quality-enhancement/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

This feature adds a query quality enhancement module to the RAG service that analyzes user queries against required document dimensions (company_id, file_type, document_type, organization, year/number, subject/content) and guides users through multi-turn conversations to provide missing information before executing searches.

**Technical Approach**:
- Create a new `QueryQualityCapability` that analyzes query dimensions using LLM
- Implement session state management using Redis (15-minute TTL, 10-turn max)
- Add dimension prompting logic with multi-turn conversation support
- Integrate with existing QA Pipeline (feature 005) as a pre-processing step
- Use Prompt Service (feature 003) for dimension analysis prompts
- Support dual knowledge base search when file_type (发文/收文) cannot be determined

**2025 Document Analysis Updates** (2026-04-09):
Based on analysis of 38 documents from the 2025 directory, the following enhancements have been incorporated:
- **会议纪要** (Meeting Minutes) is now recognized as a distinct document type from general 纪要
- New meeting types: 职工代表大会, 工会会员代表大会, 工作会议, 启动会
- Extended organization entities: 专业委员会 (审计委员会, 产品技术委员会), 领导小组
- Enhanced subject categories with hierarchical structure for 党建工作, 工会工作, 信息化建设
- Colloquial expression mapping for better user query understanding (e.g., "会议记录" → 会议纪要, "职代会" → 职工代表大会)

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI, LiteLLM, Pydantic, Prompt Service SDK, Redis (aioredis)
**Storage**: Redis for session state (TTL-based expiration)
**Testing**: pytest with pytest-asyncio, real implementations (minimal mocks per constitution)
**Target Platform**: Linux server (FastAPI/uvicorn)
**Project Type**: Web service capability extension
**Performance Goals**: <3 seconds p95 for query processing including dimension prompts
**Constraints**:
  - Single-instance deployment with simple failure recovery (99.5% availability target)
  - Must propagate trace_id across all service calls
  - Structured JSON logging for all operations
**Scale/Scope**:
  - Session timeout: 15 minutes inactivity
  - Max conversation turns: 10 per session
  - Session state storage: Redis with automatic TTL expiration

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
specs/006-query-quality-enhancement/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   └── query_quality_api.md
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/rag_service/
├── capabilities/
│   ├── base.py                    # Existing: Capability base class
│   ├── query_quality.py           # NEW: Query quality analysis capability
│   └── ...
├── models/
│   └── query_quality.py           # NEW: Query quality data models
├── services/
│   └── session_store.py           # NEW: Redis session state store
├── api/
│   └── qa_schemas.py              # MODIFY: Add query quality schemas
└── config.py                      # MODIFY: Add query quality settings

tests/
├── unit/
│   └── test_query_quality.py      # NEW: Unit tests for query quality
├── integration/
│   └── test_query_quality_e2e.py  # NEW: Integration tests
└── contract/
    └── test_query_quality_api.py  # NEW: API contract tests
```

**Structure Decision**: Single project structure (Option 1). The query quality enhancement is a capability module within the existing RAG service, following the established Capability Interface Layer pattern. It extends the service without requiring a new project or separate deployment unit.

## Complexity Tracking

> **No violations to report** - This feature extends the existing architecture without violating any constitution principles.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | N/A | N/A |
