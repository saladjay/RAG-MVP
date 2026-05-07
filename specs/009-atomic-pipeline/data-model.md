# Data Model: Atomic Pipeline Refactor

**Feature**: 009-atomic-pipeline
**Date**: 2026-05-07

## Entities

### 1. PipelineContext

Shared state object flowing through all pipeline steps.

| Field | Type | Default | Produced by | Consumed by |
|-------|------|---------|-------------|-------------|
| `original_query` | `str` | (required) | Input | Extraction, Response |
| `session_id` | `str` | `""` | Input | Extraction, Memory |
| `trace_id` | `str` | `""` | Input | All steps (logging) |
| `request_context` | `Optional[QueryContext]` | `None` | Input | Retrieval |
| `top_k` | `int` | `10` | Input | Retrieval |
| `stream` | `bool` | `False` | Input | Generation, Runner |
| `processed_query` | `str` | `""` | Extraction, Rewrite | Rewrite, Retrieval, Generation |
| `chunks` | `list[dict]` | `[]` | Retrieval | Reasoning, Generation, Verification, Execution |
| `reasoning_result` | `Optional[dict]` | `None` | Reasoning | Generation, Execution |
| `answer` | `str` | `""` | Generation | Verification, Execution, Response |
| `hallucination_status` | `Optional[HallucinationStatus]` | `None` | Verification | Execution, Response |
| `quality_meta` | `dict` | `{}` | Extraction, Execution | Response |
| `should_abort` | `bool` | `False` | Extraction (or any step) | Runner |
| `abort_prompt` | `Optional[str]` | `None` | Extraction (or any step) | Response |
| `timing` | `dict[str, float]` | `{}` | Runner (auto) | Response |

### 2. PipelinePolicy

Execution control parameters. Constructed from existing `QueryConfig`.

| Field | Type | Default | Maps from QueryConfig |
|-------|------|---------|-----------------------|
| `enable_extraction` | `bool` | `True` | Always on |
| `enable_rewrite` | `bool` | `True` | `enable_query_rewrite` |
| `enable_reasoning` | `bool` | `False` | New (Phase 1 always off) |
| `enable_verification` | `bool` | `True` | `enable_hallucination_check` |
| `enable_execution` | `bool` | `True` | Always on |
| `rewrite_depth` | `int` | `1` | New (Phase 1 = 1) |
| `max_regen_attempts` | `int` | `0` | `max_regen_attempts` |
| `hallucination_threshold` | `float` | `0.7` | `hallucination_threshold` |
| `extraction_mode` | `str` | `"basic"` | `quality_mode` |
| `retrieval_backend` | `str` | `"external_kb"` | `retrieval_backend` |
| `verification_method` | `str` | `"similarity"` | `hallucination_method` |
| `prompt_extraction` | `str` | `"query_dimension_analysis"` | `dimension_analysis_template` |
| `prompt_rewrite` | `str` | `"qa_query_rewrite"` | `prompt_query_rewrite` |
| `prompt_reasoning` | `str` | `"qa_reasoning"` | New (unused Phase 1) |
| `prompt_generation` | `str` | `"qa_answer_generate"` | `prompt_answer_generate` |
| `prompt_verification` | `str` | `"qa_hallucination_detection"` | (hardcoded in capability) |

### 3. StepCapability (Protocol)

```python
@runtime_checkable
class StepCapability(Protocol):
    @property
    def name(self) -> str: ...

    async def execute(self, context: PipelineContext) -> PipelineContext: ...

    async def get_health(self) -> dict[str, Any]: ...
```

### 4. MemoryCapability (Protocol)

```python
@runtime_checkable
class MemoryCapability(Protocol):
    async def get_session(self, session_id: str) -> Optional[dict]: ...
    async def save_session(self, session_id: str, data: dict, ttl: int = 900) -> None: ...
    async def get_belief_state(self, session_id: str) -> Optional[dict]: ...
    async def save_belief_state(self, session_id: str, data: dict, ttl: int = 900) -> None: ...
```

## Entity Relationships

```
PipelinePolicy ──────controls──────▶ PipelineRunner
                                        │
                                        │ executes
                                        ▼
PipelineContext ◄──────read/write────── StepCapability (×8)
     │                                      │
     │                                      │ delegates to
     │                                      ▼
     │                               Existing strategies/
     │                               capabilities (unchanged)
     │
     └───persisted via────▶ MemoryCapability ◀──▶ Redis
```

## Data Flow by Step

```
Input Request
     │
     ▼
PipelineContext(original_query, session_id, trace_id, request_context, top_k)
     │
     ├─ ExtractionStep ──▶ context.processed_query, context.quality_meta, context.should_abort?
     │
     ├─ RewriteStep ────▶ context.processed_query (updated)
     │
     ├─ RetrievalStep ──▶ context.chunks
     │
     ├─ ReasoningStep ──▶ context.reasoning_result (Phase 1: None)
     │
     ├─ GenerationStep ─▶ context.answer
     │
     ├─ VerificationStep ▶ context.hallucination_status
     │
     └─ ExecutionStep ──▶ context.quality_meta (finalized)
     │
     ▼
QueryResponse built from context
```
