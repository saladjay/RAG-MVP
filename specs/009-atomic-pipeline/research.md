# Research: Atomic Pipeline Refactor

**Feature**: 009-atomic-pipeline
**Date**: 2026-05-07

## Call Flow Diagrams

### Current Flow (before refactor)

```
POST /api/v1/query {"query": "What is RAG?"}
  │
  ▼
unified_routes.py:unified_query()                    [src/rag_service/api/unified_routes.py:62]
  │ registry.get("QueryCapability")
  ▼
query_capability.py:QueryCapability.execute()        [src/rag_service/capabilities/query_capability.py:117]
  │ 454 lines, hardcoded 6-step pipeline
  │
  ├─① quality.pre_process(query, session_id, config) → (query, prompt_info)
  │    └─ DimensionGatherQuality → query_quality.py:QueryQualityCapability.execute()
  │       └─ session_store.py:SessionStoreService     [Redis r/w]
  │       └─ prompt_client.py:PromptClient.get_prompt() [Langfuse HTTP]
  │       └─ LiteLLMGateway.acomplete()               [LLM call]
  │    └─ ConversationalQuality → conversational_query.py:ConversationalQueryCapability.execute()
  │       └─ belief_state_store.py:BeliefStateStoreService [Redis r/w]
  │       └─ colloquial_mapper.py:ColloquialMapperService  [in-memory]
  │       └─ prompt_client.py:PromptClient.get_prompt()    [×2 LLM calls]
  │
  ├─② _rewrite_query(query, trace_id) → rewritten_query
  │    └─ query_rewrite.py:QueryRewriteCapability     [BUG: no litellm_client, always returns original]
  │       └─ prompt_client.py:PromptClient.get_prompt()
  │       └─ LiteLLMGateway.acomplete()               [NEVER REACHED due to bug]
  │
  ├─③ retrieval.retrieve(query, top_k, context, trace_id) → chunks
  │    └─ MilvusRetrieval → milvus_kb_client.py       [Milvus DB]
  │    └─ ExternalKBRetrieval → external_kb_client.py  [HTTP POST]
  │
  ├─④ _generate_answer(query, chunks, trace_id) → answer
  │    └─ HARDCODED PROMPT (line 306-313)             [Not via PromptClient]
  │    └─ gateway.py:LiteLLMGateway.acomplete_routed() [LLM call]
  │
  ├─⑤ _check_hallucination(answer, chunks, trace_id) → HallucinationStatus
  │    └─ hallucination_detection.py:HallucinationDetectionCapability
  │       └─ sentence-transformers (similarity) or LLM (llm method)
  │
  └─⑥ quality.post_process(answer, chunks, session_id) → dict
       └─ All implementations: return empty dict      [Trivial]
```

### Target Flow (after refactor)

```
POST /api/v1/query {"query": "What is RAG?"}
  │
  ▼
unified_routes.py:unified_query()                    [UNCHANGED]
  │ registry.get("QueryCapability")
  ▼
query_capability.py:QueryCapability.execute()        [~30 lines, orchestration only]
  │ 1. Build PipelineContext from request
  │ 2. Build PipelinePolicy from config
  │ 3. Build step list
  │ 4. PipelineRunner.run(context)
  │ 5. Build QueryResponse from context
  ▼
runner.py:PipelineRunner.run(context)                [NEW: Planning capability]
  │ for step in steps:
  │   if context.should_abort: break
  │   if not policy._should_run(step): continue
  │   context = await step.execute(context)
  │   context.timing[step.name] = elapsed_ms
  │
  ├─① ExtractionStep.execute(context)                [pipeline/steps/extraction.py]
  │    context: original_query → processed_query, quality_meta, should_abort?
  │    └─ delegates to QualityStrategy (existing strategies/quality.py)
  │       └─ delegates to QueryQualityCapability or ConversationalQueryCapability
  │
  ├─② RewriteStep.execute(context)                   [pipeline/steps/rewrite.py]
  │    context: processed_query → processed_query (updated)
  │    └─ delegates to QueryRewriteCapability [FIXED: proper gateway wiring]
  │
  ├─③ RetrievalStep.execute(context)                 [pipeline/steps/retrieval.py]
  │    context: processed_query, top_k, request_context → chunks
  │    └─ delegates to RetrievalStrategy (existing strategies/retrieval.py)
  │
  ├─④ ReasoningStep.execute(context)                 [pipeline/steps/reasoning.py]
  │    context: chunks, processed_query → reasoning_result
  │    └─ Phase 1: pass-through (identity function)
  │
  ├─⑤ GenerationStep.execute(context)                [pipeline/steps/generation.py]
  │    context: processed_query, chunks, reasoning_result → answer
  │    └─ prompt via PromptClient (EXTERNALIZED, no more hardcoded string)
  │    └─ gateway.py:LiteLLMGateway.acomplete_routed()
  │
  ├─⑥ VerificationStep.execute(context)              [pipeline/steps/verification.py]
  │    context: answer, chunks → hallucination_status
  │    └─ delegates to HallucinationDetectionCapability
  │
  └─⑦ ExecutionStep.execute(context)                 [pipeline/steps/execution.py]
       context: answer, chunks, hallucination_status → quality_meta
       └─ Phase 1: migrated from quality.post_process()
```

## Design Decisions

### Decision 1: PipelineContext as Pydantic BaseModel

**Decision**: Use a single Pydantic model as the shared state object.

**Rationale**:
- All pipeline steps share the same data through a typed model
- Pydantic provides validation, serialization, and IDE auto-complete
- No implicit state passing through function parameters
- Easy to snapshot for debugging/observability

**Alternatives considered**:
- `dataclass` — simpler but no validation, no JSON schema
- `dict` passing — no type safety, easy to misspell keys
- Separate input/output types per step — defeats the purpose of shared context

### Decision 2: StepCapability as typing.Protocol (not ABC)

**Decision**: Use `typing.Protocol` with `@runtime_checkable` for step interface.

**Rationale**:
- Structural subtyping — no inheritance required
- Zero dependency overhead (stdlib only)
- Consistent with existing `RetrievalStrategy` and `QualityStrategy` patterns
- Easy to create ad-hoc steps (lambda/functional style)

**Alternatives considered**:
- Abstract base class (`ABC`) — requires inheritance, tighter coupling
- Callable type hint — too loose, no `name` property
- Dataclass with `__call__` — unconventional for async methods

### Decision 3: PipelineRunner as Planning implementation

**Decision**: PipelineRunner IS the Planning capability. Not a separate step.

**Rationale**:
- Planning decides "what to do" — which steps to run, in what order
- PipelineRunner already makes these decisions via policy
- Making Planning a step that runs inside the pipeline creates a paradox (Planning plans itself?)
- Cleaner separation: Runner = Planning, Steps = other 7 capabilities

**Alternatives considered**:
- Planning as first step in pipeline — recursive, adds complexity
- Separate PlanningService — over-engineering for current needs

### Decision 4: Reasoning and Execution as pass-through (Phase 1)

**Decision**: ReasoningStep and ExecutionStep start as identity functions.

**Rationale**:
- Protocol interface is defined, implementations can be swapped later
- Phase 1 focus is on decomposing the existing pipeline, not adding new functionality
- Pass-through adds ~20 lines each, minimal overhead
- Future: Reasoning can inject CoT, Execution can inject tool calling

**Alternatives considered**:
- Skip these steps entirely — harder to add later, missing from step list
- Implement full reasoning now — scope creep, no clear requirement yet

### Decision 5: Delegation to existing strategies/capabilities (Phase 1)

**Decision**: Steps delegate to existing implementations rather than inlining logic.

**Rationale**:
- Minimizes risk — existing tested code is reused
- Migration can be done incrementally (delegate now, inline later)
- Reduces PR size and review complexity
- Existing `strategies/` and `capabilities/` remain valid

**Alternatives considered**:
- Inline all logic into steps — huge PR, high risk of regression
- Rewrite strategies — unnecessary churn, they work fine

### Decision 6: should_abort signal (not exception for control flow)

**Decision**: Steps set `context.should_abort = True` instead of raising exceptions.

**Rationale**:
- Exceptions are for errors, not normal control flow
- `should_abort` is a pipeline-level signal that any step can set
- PipelineRunner checks it uniformly after each step
- Cleaner than try/except chains for flow control

**Alternatives considered**:
- Raise `QueryQualityPromptRequired` — current approach, mixes error and control flow
- Return tuple `(context, should_abort)` — more complex step interface
- Special `AbortPipeline` exception — still exception-based control flow

## File Inventory

### New Files (8)

| File | Purpose | Approx Lines |
|------|---------|-------------|
| `pipeline/__init__.py` | Package exports | ~15 |
| `pipeline/context.py` | PipelineContext model | ~60 |
| `pipeline/policy.py` | PipelinePolicy model | ~50 |
| `pipeline/runner.py` | PipelineRunner (Planning) | ~80 |
| `pipeline/steps/__init__.py` | Step exports | ~15 |
| `pipeline/steps/extraction.py` | ExtractionStep | ~80 |
| `pipeline/steps/rewrite.py` | RewriteStep | ~50 |
| `pipeline/steps/retrieval.py` | RetrievalStep | ~40 |
| `pipeline/steps/reasoning.py` | ReasoningStep (pass-through) | ~20 |
| `pipeline/steps/generation.py` | GenerationStep | ~60 |
| `pipeline/steps/verification.py` | VerificationStep | ~50 |
| `pipeline/steps/execution.py` | ExecutionStep (pass-through) | ~25 |
| `pipeline/steps/memory.py` | MemoryCapability Protocol | ~40 |

### Modified Files (1)

| File | Change |
|------|--------|
| `capabilities/query_capability.py` | Rewrite execute() from 454 → ~30 lines |

### Unchanged Files

- `api/unified_routes.py` — no changes
- `api/unified_schemas.py` — no changes
- `config.py` — no changes (PipelinePolicy constructed from QueryConfig)
- `strategies/*` — no changes (steps delegate to them)
- `capabilities/management_capability.py` — no changes
- `capabilities/trace_capability.py` — no changes
