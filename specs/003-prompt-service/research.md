# Research: Prompt Management Service

**Feature**: 003-prompt-service | **Date**: 2026-03-23
**Status**: Phase 0 - Technical Decisions

## Overview

This document captures all technical research and decisions made during the planning phase for the Prompt Management Service. Each decision includes the chosen approach, rationale, and alternatives considered.

---

## Decision 1: Web Framework Selection

**Decision**: Use FastAPI with uvicorn ASGI server

**Rationale**:
- Native async/await support for high-concurrency prompt retrieval
- Automatic OpenAPI documentation for API contracts
- Pydantic integration for request/response validation
- Built-in dependency injection for Langfuse client
- Excellent performance (comparable to Go Node.js frameworks)

**Alternatives Considered**:
| Alternative | Rejected Because |
|-------------|------------------|
| Flask | No native async, requires additional extensions for OpenAPI |
| Django | Too heavy for a focused middleware service |
| Tornado | Less active community, fewer modern features |

**Implementation Notes**:
- Use lifespan context manager for Langfuse client lifecycle
- Register routes with `/api/v1` prefix for versioning
- Enable CORS for cross-origin requests from management UI

---

## Decision 2: Langfuse Integration Pattern

**Decision**: Wrap Langfuse SDK in a service layer, not direct usage in routes

**Rationale**:
- Maintains separation between HTTP layer and external dependencies
- Enables graceful degradation when Langfuse is unavailable
- Facilitates testing with mock Langfuse responses
- Allows swapping observability platforms in the future

**Architecture**:

```
┌─────────────────┐
│  FastAPI Routes │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────┐
│  LangfuseClientService       │
│  - get_prompt()              │
│  - create_prompt()           │
│  - log_trace()               │
│  - + fallback cache          │
└────────┬────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│  Langfuse SDK                │
└─────────────────────────────┘
```

**Alternatives Considered**:
| Alternative | Rejected Because |
|-------------|------------------|
| Direct SDK usage in routes | Tight coupling, no graceful degradation |
| Custom observability platform | Rebuilding existing functionality |

---

## Decision 3: A/B Testing Implementation

**Decision**: Deterministic hash-based routing with consistent user assignment

**Rationale**:
- Users consistently see the same variant across sessions
- No database lookup per request (O(1) routing)
- Easy to adjust traffic percentages without re-assignment
- Supports gradual rollout (0% → 100%)

**Algorithm**:
```python
import hashlib

def get_variant(user_id: str, test_id: str, variants: List[Variant]) -> str:
    """Deterministically select variant based on user_id and test_id"""
    hash_input = f"{user_id}:{test_id}"
    hash_value = int(hashlib.sha256(hash_input.encode()).hexdigest(), 16)
    bucket = hash_value % 100

    cumulative = 0
    for variant in variants:
        cumulative += variant.traffic_percentage
        if bucket < cumulative:
            return variant.id

    return variants[-1].id  # Fallback to last variant
```

**Alternatives Considered**:
| Alternative | Rejected Because |
|-------------|------------------|
| Random selection per request | Users see different variants, confusing experience |
| Database lookup per request | Adds latency, single point of failure |
| Cookie-based assignment | Doesn't work for API-only clients |

**Metrics Tracking**:
- Count impressions per variant
- Track success rate (user-defined or automated)
- Measure latency p50, p95, p99
- Record user feedback when available

---

## Decision 4: Prompt Variable Interpolation

**Decision**: Use Jinja2 templates with strict undefined handling

**Rationale**:
- Industry-standard templating with comprehensive features
- Supports complex expressions (loops, conditionals) if needed
- Strict undefined handling catches missing variables early
- Excellent performance for template rendering
- Sandbox mode for security

**Template Syntax**:
```python
from jinja2 import Environment, StrictUndefined

env = Environment(undefined=StrictUndefined)

# Structured prompt template
template = """[角色]
{{ role }}

[任务]
{{ task }}

[约束]
{% for constraint in constraints %}
- {{ constraint }}
{% endfor %}

[输入]
{% for key, value in inputs.items() %}
{{ key }}: {{ value }}
{% endfor %}

[输出格式]
{{ output_format }}

{% if context %}
[上下文]
{{ context }}
{% endif %}

{% if retrieved_docs %}
[检索文档]
{% for doc in retrieved_docs %}
- {{ doc.content }}
{% endfor %}
{% endif %}"""
```

**Alternatives Considered**:
| Alternative | Rejected Because |
|-------------|------------------|
| Python f-strings | No conditional logic, requires Python code evaluation |
| String.Template | Too limited, no loops or conditionals |
| Custom interpolation | Rebuilding existing functionality |

**Error Handling**:
- `StrictUndefined` raises error for missing variables
- Provide default values with `{{ variable|default('value') }}`
- Log interpolation failures for debugging

---

## Decision 5: Caching Strategy

**Decision**: Two-tier caching with in-memory L1 and optional Redis L2

**Rationale**:
- L1 (in-memory): Sub-microsecond access for active prompts
- L2 (Redis optional): Shared cache across service instances
- Cache invalidation on prompt publish via event broadcast
- TTL-based fallback for stale cache resilience

**Cache Key Design**:
```python
# L1 cache key
cache_key = f"prompt:{template_id}:{version_id}"

# With A/B test consideration
cache_key = f"prompt:{template_id}:ab_test:{ab_test_id}:{variant_id}"
```

**Cache Layers**:

```
┌─────────────────────────────────────────────────────┐
│                   Request                           │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │  L1: In-Memory Cache │  ← 1000+ prompts, <1µs access
          │  (cachetools LRU)    │
          └──────────┬───────────┘
                     │ MISS
                     ▼
          ┌──────────────────────┐
          │  L2: Redis (optional)│  ← Shared across instances
          └──────────┬───────────┘
                     │ MISS
                     ▼
          ┌──────────────────────┐
          │  Langfuse API        │
          └──────────────────────┘
```

**Cache Invalidation**:
- Invalidate L1 on prompt publish (local event)
- Publish to Redis channel for L2 invalidation (multi-instance)
- TTL of 5 minutes as fallback

**Alternatives Considered**:
| Alternative | Rejected Because |
|-------------|------------------|
| No caching | Adds 50-100ms latency per prompt retrieval |
| Database cache | Overkill, slower than in-memory |
| CDN cache | Not suitable for dynamic prompt content |

---

## Decision 6: Error Handling and Graceful Degradation

**Decision**: Fail-open with fallback defaults and comprehensive logging

**Rationale**:
- Prompt retrieval failures should not block business operations
- Fallback to cached prompts or default templates
- All errors logged with trace_id for debugging
- Health endpoint reports degraded state when Langfuse unavailable

**Degradation Modes**:

| Scenario | Behavior |
|----------|----------|
| Langfuse API timeout | Return cached prompt if available, log error |
| Langfuse API error | Return last known good version, log error |
| Network partition | Serve from L1 cache, health = degraded |
| Cache miss + API failure | Return error with clear message |

**Error Response Format**:
```python
{
    "error": "PROMPT_UNAVAILABLE",
    "message": "Unable to retrieve prompt template",
    "fallback_provided": True,
    "fallback_content": "...",
    "trace_id": "abc123",
    "retry_after": 60  # seconds
}
```

**Alternatives Considered**:
| Alternative | Rejected Because |
|-------------|------------------|
| Fail-closed (raise exception) | Blocks all operations on observability failure |
| Silent failures | No visibility into degradation |

---

## Decision 7: Trace Data Aggregation

**Decision**: Aggregate in-memory with periodic persistence to Langfuse

**Rationale**:
- Batch trace uploads reduce API calls
- In-memory aggregation enables real-time queries
- Periodic persistence (every 30s) balances freshness and load
- Use Langfuse's built-in aggregation for heavy analytics

**Aggregation Levels**:
```python
# Real-time (in-memory)
- Last 1000 traces per prompt
- Metrics for current session

# Short-term (Langfuse queries)
- Last 24 hours detailed traces
- Per-variant A/B test metrics

# Long-term (Langfuse analytics)
- Historical trends
- Anomaly detection
```

**Alternatives Considered**:
| Alternative | Rejected Because |
|-------------|------------------|
| Send every trace immediately | Too many API calls, rate limiting |
| Store in database first | Adds storage and maintenance overhead |
| No aggregation, query Langfuse | Slow queries, no real-time insights |

---

## Decision 8: Management UI Architecture

**Decision**: Separate React SPA with FastAPI backend

**Rationale**:
- Clear separation of concerns (UI vs service)
- Can be deployed independently
- Enables different authentication mechanisms
- React ecosystem for data visualization

**UI Components**:
```
┌──────────────────────────────────────────────┐
│              Prompt Management UI             │
├──────────────────────────────────────────────┤
│                                              │
│  ┌────────────────┐  ┌────────────────┐     │
│  │ Prompt Editor  │  │ Version History│     │
│  │ - Live preview │  │ - Diff view    │     │
│  │ - Validation   │  │ - Rollback     │     │
│  └────────────────┘  └────────────────┘     │
│                                              │
│  ┌────────────────┐  ┌────────────────┐     │
│  │ A/B Test Config│  │ Trace Analysis │     │
│  │ - Traffic split│  │ - Metrics      │     │
│  │ - Winner pick  │  │ - Patterns     │     │
│  └────────────────┘  └────────────────┘     │
│                                              │
└──────────────────────────────────────────────┘
```

**Alternatives Considered**:
| Alternative | Rejected Because |
|-------------|------------------|
| Server-rendered templates (Jinja2) | Poor UX for dynamic interfaces |
| Desktop app (Electron) | Overkill for occasional management use |
| CLI only | Not suitable for product managers |

---

## Decision 9: Structured Prompt Format

**Decision**: Enforce section-based format with flexible schema

**Rationale**:
- Balances structure with flexibility
- Sections are validated but content is free-form
- Supports the recommended [角色], [任务], [约束], [输入], [输出格式] format
- Allows custom sections for domain-specific needs

**Section Schema**:
```python
class StructuredSection(BaseModel):
    name: str  # e.g., "角色", "任务", "约束"
    content: str
    is_required: bool = True
    order: int

class PromptTemplate(BaseModel):
    template_id: str
    sections: List[StructuredSection]
    variables: Dict[str, str]  # variable name -> description
    version: int
    metadata: Dict[str, Any]
```

**Rendering Order**:
1. Required sections in order (角色, 任务, 约束, 输出格式)
2. Dynamic input section with variables
3. Optional context section (if provided)
4. Optional retrieved_docs section (if provided)

**Alternatives Considered**:
| Alternative | Rejected Because |
|-------------|------------------|
| Free-form text only | No structure, hard to validate |
| Fixed schema only | Too rigid for domain-specific needs |

---

## Decision 10: Python SDK Design

**Decision**: Simple synchronous client with async optional

**Rationale**:
- Most business code is synchronous
- Async version available for high-performance scenarios
- Singleton client for connection pooling
- Automatic retry on transient failures

**SDK API**:
```python
from prompt_service import PromptClient

# Initialize
client = PromptClient(
    base_url="http://localhost:8000",
    api_key="optional-key"
)

# Get prompt
response = client.get_prompt(
    template_id="financial_analysis",
    variables={"input": "Analyze AAPL stock"},
    context={"user_id": "123"},
    retrieved_docs=[...]
)

# Access rendered prompt
print(response.content)  # Fully assembled prompt
print(response.version_id)  # For trace linking
print(response.variant_id)  # If A/B test
```

**Alternatives Considered**:
| Alternative | Rejected Because |
|-------------|------------------|
| gRPC/protobuf | Overkill for simple retrieval |
| Direct HTTP (no SDK) | More code for users, no retry logic |

---

## Call Flow Diagrams

### Flow 1: Prompt Retrieval (No A/B Test)

```
┌─────────────────┐
│  Business Code  │
└────────┬────────┘
         │ get_prompt(template_id, variables)
         ▼
┌─────────────────────────────────────────┐
│  PromptClient (SDK)                      │
│  1. Build HTTP request                  │
│  2. Add trace_id for tracking           │
└────────┬────────────────────────────────┘
         │ POST /api/v1/prompts/{template_id}/retrieve
         ▼
┌─────────────────────────────────────────┐
│  FastAPI Route Handler                  │
│  @router.post("/prompts/{id}/retrieve") │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  PromptRetrievalService.execute()       │
│  1. Check L1 cache                     │
│  2. Check for active A/B tests         │
│  3. Load template from Langfuse        │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  PromptAssemblyService.assemble()       │
│  1. Render structured sections         │
│  2. Inject context section             │
│  3. Format retrieved_docs              │
│  4. Interpolate variables (Jinja2)     │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  Trace Logging                          │
│  Log retrieval with version, variant    │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  Response                               │
│  { rendered_prompt, version_id, ... }   │
└─────────────────────────────────────────┘
```

### Flow 2: Prompt Retrieval with A/B Test

```
┌─────────────────┐
│  Business Code  │
└────────┬────────┘
         │ get_prompt(template_id, user_id)
         ▼
┌─────────────────────────────────────────┐
│  PromptRetrievalService                 │
│  1. Check cache                        │
│  2. Query active A/B tests             │
│  3. Calculate hash-based variant       │
│     hash(user_id + test_id) % 100      │
│  4. Select variant based on traffic    │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  ABTestingService.assign_variant()      │
│  - Deterministic selection             │
│  - Record impression                   │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  PromptAssemblyService                 │
│  Assemble prompt using selected variant│
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  Response with variant_id              │
│  { rendered_prompt, version_id,        │
│    variant_id: "variant_a" }           │
└─────────────────────────────────────────┘
```

### Flow 3: Prompt Edit and Publish

```
┌─────────────────┐
│  Product Manager│
│  (Management UI)│
└────────┬────────┘
         │ Edit prompt template
         ▼
┌─────────────────────────────────────────┐
│  FastAPI Route                          │
│  @router.put("/prompts/{id}")           │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  PromptManagementService.update()       │
│  1. Validate new content               │
│  2. Create new version in Langfuse     │
│  3. Update version history             │
│  4. Invalidate L1 cache (local)        │
│  5. Publish cache invalidation event   │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  Event Bus (Redis or in-memory)         │
│  Publish: prompt.updated.{template_id}  │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  All Service Instances                  │
│  - Invalidate L1 cache for template_id  │
│  - Next retrieval fetches new version  │
└─────────────────────────────────────────┘
```

### Flow 4: Trace Analysis

```
┌─────────────────┐
│  Analyst        │
│  (Management UI)│
└────────┬────────┘
         │ Request trace analysis
         ▼
┌─────────────────────────────────────────┐
│  FastAPI Route                          │
│  @router.get("/analytics/{prompt_id}")  │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  TraceAnalysisService.get_insights()    │
│  1. Query in-memory aggregated traces   │
│  2. Query Langfuse for detailed history│
│  3. Calculate metrics                  │
│     - Usage count                       │
│     - Error rate                        │
│     - Latency percentiles               │
│     - Variant comparison (if A/B test)  │
└────────┬────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  Response                               │
│  {                                      │
│    total_usage: 10000,                  │
│    error_rate: 0.02,                    │
│    latency_p95: 85ms,                   │
│    variants: [                          │
│      { id: "a", success_rate: 0.85 },   │
│      { id: "b", success_rate: 0.89 }    │
│    ]                                    │
│  }                                      │
└─────────────────────────────────────────┘
```

---

## API Reference Mapping

| API Endpoint | Service Method | File Location |
|--------------|----------------|---------------|
| POST /api/v1/prompts/{id}/retrieve | PromptRetrievalService.execute() | src/prompt_service/services/prompt_retrieval.py |
| GET /api/v1/prompts | PromptManagementService.list() | src/prompt_service/services/prompt_management.py |
| PUT /api/v1/prompts/{id} | PromptManagementService.update() | src/prompt_service/services/prompt_management.py |
| POST /api/v1/prompts | PromptManagementService.create() | src/prompt_service/services/prompt_management.py |
| DELETE /api/v1/prompts/{id} | PromptManagementService.delete() | src/prompt_service/services/prompt_management.py |
| GET /api/v1/prompts/{id}/versions | VersionControlService.get_history() | src/prompt_service/services/version_control.py |
| POST /api/v1/prompts/{id}/rollback | VersionControlService.rollback() | src/prompt_service/services/version_control.py |
| POST /api/v1/ab-tests | ABTestService.create_test() | src/prompt_service/services/ab_testing.py |
| GET /api/v1/ab-tests/{id} | ABTestService.get_results() | src/prompt_service/services/ab_testing.py |
| POST /api/v1/ab-tests/{id}/winner | ABTestService.select_winner() | src/prompt_service/services/ab_testing.py |
| GET /api/v1/analytics/{prompt_id} | TraceAnalysisService.get_insights() | src/prompt_service/services/trace_analysis.py |
| GET /health | HealthCheckCapability.execute() | src/prompt_service/capabilities/health_check.py |

---

## Dependencies Summary

| Package | Version | Purpose |
|---------|---------|---------|
| fastapi | ^0.109.0 | Web framework |
| uvicorn | ^0.27.0 | ASGI server |
| pydantic | ^2.5.0 | Data validation |
| pydantic-settings | ^2.1.0 | Configuration management |
| langfuse | ^2.0.0 | Observability platform SDK |
| jinja2 | ^3.1.0 | Template rendering |
| cachetools | ^5.3.0 | In-memory caching |
| redis | ^5.0.0 | Optional L2 cache |
| httpx | ^0.26.0 | Async HTTP client for SDK |
| python-json-logger | ^2.0.0 | Structured logging |

---

## Open Questions / Risks

1. **Langfuse API Rate Limits**: Need to test behavior under high load. Mitigation: aggressive caching.

2. **Multi-Instance Cache Invalidation**: Redis channel reliability. Mitigation: TTL fallback.

3. **A/B Test Statistical Significance**: Not calculating automatically. Mitigation: provide metrics, let users decide.

4. **Prompt Size Limits**: Langfuse may have size limits. Mitigation: validate before publishing, document limits.

---

**Document Version**: 1.0 | **Last Updated**: 2026-03-23
