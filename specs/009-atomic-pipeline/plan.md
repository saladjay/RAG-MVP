# Implementation Plan: Atomic Pipeline Refactor

**Branch**: `009-atomic-pipeline` | **Date**: 2026-05-07 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/009-atomic-pipeline/spec.md`

## Summary

Decompose the monolithic QueryCapability (454-line god object with hardcoded 6-step pipeline) into 8 atomic capabilities orchestrated by a lightweight PipelineRunner. Introduces PipelineContext as a first-class state object and PipelinePolicy for execution control. Zero new dependencies — all abstractions use stdlib `typing.Protocol` + Pydantic.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI, Pydantic, Pydantic Settings, typing.Protocol (stdlib)
**Storage**: Redis (sessions/belief state), Milvus (vector search) — existing, unchanged
**Testing**: pytest, pytest-asyncio — existing
**Target Platform**: Linux/Windows server (uvicorn + FastAPI)
**Project Type**: Web service internal refactoring
**Performance Goals**: Zero regression — identical response times and payload shapes
**Constraints**: Zero new Python dependencies; zero API-level breaking changes; no modifications to ManagementCapability or TraceCapability
**Scale/Scope**: Single RAG service instance; ~10 source files affected

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Documentation Standards (Principle I & II)
- [x] All files will include header with content and API brief description
- [x] Documentation headers will be updated immediately on content changes
- [x] Call flow diagrams will be generated at `.specify/specs/009-atomic-pipeline/research.md`
- [x] Architecture documentation will reference all APIs (document location → function name)

### Testing Standards (Principle III & IV)
- [x] Tests will use real implementations (minimal mocks) — existing test suite validates no regression
- [x] Server tests will include server startup scripts — existing uvicorn setup
- [x] Python execution will use `uv`-managed virtual environment
- [x] Blocking points for real test implementation will be documented

### Component Governance (Principle V)
- [x] New base components have not been created without approval — PipelineRunner and StepCapability are internal to the pipeline module, not new base components
- [x] Existing base components are documented — Capability base class in `capabilities/base.py` unchanged
- [x] Package management uses `uv` for Python dependencies — no new packages

## Project Structure

### Documentation (this feature)

```text
specs/009-atomic-pipeline/
├── plan.md              # This file
├── research.md          # Phase 0: Call flow diagrams, design decisions
├── data-model.md        # Phase 1: Entity definitions
├── quickstart.md        # Phase 1: Migration guide
├── contracts/           # Phase 1: Step interface contracts
│   └── step-capability.md
└── tasks.md             # Phase 2: Task breakdown (/speckit.tasks)
```

### Source Code (repository root)

```text
src/rag_service/
├── pipeline/                           ← NEW: Atomic capability pipeline
│   ├── __init__.py                        Exports: PipelineRunner, PipelineContext, PipelinePolicy
│   ├── context.py                         PipelineContext model
│   ├── policy.py                          PipelinePolicy model
│   ├── runner.py                          PipelineRunner (Planning capability)
│   └── steps/                             8 atomic capabilities
│       ├── __init__.py                       Exports all steps
│       ├── extraction.py                     ExtractionStep (dimension/slot analysis)
│       ├── rewrite.py                        RewriteStep (query optimization)
│       ├── retrieval.py                      RetrievalStep (delegates to strategies/)
│       ├── reasoning.py                      ReasoningStep (Phase 1: pass-through)
│       ├── generation.py                     GenerationStep (answer generation, prompt externalized)
│       ├── verification.py                   VerificationStep (hallucination detection)
│       ├── execution.py                      ExecutionStep (Phase 1: quality.post_process)
│       └── memory.py                         MemoryCapability (Protocol, Redis adapter)
├── strategies/                         ← UNCHANGED: Retrieval/Quality strategies
├── capabilities/                       ← MODIFIED: QueryCapability rewritten
│   ├── query_capability.py              ← Rewritten: ~30 lines orchestration
│   ├── management_capability.py         ← UNCHANGED
│   └── trace_capability.py              ← UNCHANGED
└── ...

Reference: D:\github\easy-rag\phase1-atomic-capability-spec.md (detailed design)
```

**Structure Decision**: New `pipeline/` package under existing `src/rag_service/`. All 8 atomic capabilities live in `pipeline/steps/`. Existing `strategies/` and `capabilities/` directories are preserved. QueryCapability is rewritten to delegate to PipelineRunner.

## Complexity Tracking

No constitution violations. All changes are internal refactoring with no new external dependencies or base components.
