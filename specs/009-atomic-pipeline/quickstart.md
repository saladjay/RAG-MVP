# Quickstart: Atomic Pipeline Refactor

**Feature**: 009-atomic-pipeline
**Date**: 2026-05-07

## Before/After Comparison

### Before: God Object

```python
# query_capability.py — 454 lines
class QueryCapability(Capability[UnifiedQueryRequest, QueryResponse]):
    async def execute(self, input_data):
        # Step 1: quality.pre_process (hardcoded)
        query, prompt_info = await self._quality.pre_process(...)
        if prompt_info:
            raise QueryQualityPromptRequired(...)  # exception for control flow

        # Step 2: rewrite (BUG: always returns original)
        rewritten = await self._rewrite_query(query, trace_id)

        # Step 3: retrieve
        chunks = await self._retrieval.retrieve(...)

        # Step 4: generate (HARDCODED PROMPT)
        answer = await self._generate_answer(query, chunks, trace_id)

        # Step 5: hallucination check
        status = await self._check_hallucination(answer, chunks, trace_id)

        # Step 6: quality.post_process (trivial)
        meta = await self._quality.post_process(answer, chunks, session_id)

        return QueryResponse(answer=answer, ...)
```

### After: Declarative Pipeline

```python
# query_capability.py — ~30 lines
class QueryCapability(Capability[UnifiedQueryRequest, QueryResponse]):
    def __init__(self):
        self._runner = PipelineRunner(
            steps=[
                ExtractionStep(),
                RewriteStep(),
                RetrievalStep(),
                ReasoningStep(),      # Phase 1: pass-through
                GenerationStep(),
                VerificationStep(),
                ExecutionStep(),      # Phase 1: pass-through
            ],
            policy=PipelinePolicy.from_config(get_settings().query),
        )

    async def execute(self, input_data):
        context = PipelineContext.from_request(input_data)
        context = await self._runner.run(context)

        if context.should_abort:
            return _build_prompt_response(context)
        return _build_query_response(context)
```

## Migration Guide

### Step 1: Verify current tests pass

```bash
uv run pytest tests/ -x -q
```

### Step 2: Pipeline infrastructure (no existing files touched)

New files created:
- `src/rag_service/pipeline/__init__.py`
- `src/rag_service/pipeline/context.py`
- `src/rag_service/pipeline/policy.py`
- `src/rag_service/pipeline/runner.py`

### Step 3: Atomic step implementations

Each step delegates to existing code:
- `pipeline/steps/memory.py` → wraps `SessionStoreService` + `BeliefStateStoreService`
- `pipeline/steps/retrieval.py` → delegates to `strategies/retrieval.py`
- `pipeline/steps/rewrite.py` → delegates to `QueryRewriteCapability` (bug fixed)
- `pipeline/steps/reasoning.py` → pass-through (20 lines)
- `pipeline/steps/generation.py` → prompt externalized via PromptClient
- `pipeline/steps/verification.py` → delegates to `HallucinationDetectionCapability`
- `pipeline/steps/extraction.py` → delegates to `QualityStrategy`
- `pipeline/steps/execution.py` → migrated from quality.post_process (20 lines)

### Step 4: Rewrite QueryCapability

Replace 454-line execute() with ~30-line orchestration.

### Step 5: Verify zero regression

```bash
uv run python -c "from rag_service.main import app; print('OK')"
uv run pytest tests/ -x -q
```

## Developer Guide

### Adding a New Step

1. Create `pipeline/steps/my_step.py`:

```python
from rag_service.pipeline.context import PipelineContext

class MyStep:
    @property
    def name(self) -> str:
        return "my_step"

    async def execute(self, context: PipelineContext) -> PipelineContext:
        # Read from context, do work, write back to context
        context.quality_meta["my_data"] = "value"
        return context
```

2. Add to step list in `query_capability.py`:

```python
steps=[
    ExtractionStep(),
    RewriteStep(),
    RetrievalStep(),
    ReasoningStep(),
    MyStep(),              # ← Add here
    GenerationStep(),
    VerificationStep(),
    ExecutionStep(),
],
```

3. Add enable flag to `PipelinePolicy` if needed.

### Swapping a Step Implementation

Replace the step class in the step list. No changes to runner, context, or other steps.

```python
# Before
steps=[..., RewriteStep(), ...]

# After (custom rewrite logic)
steps=[..., CustomRewriteStep(), ...]
```
