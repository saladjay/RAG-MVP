# Research & Technical Decisions: RAG Service MVP

**Feature**: 001-rag-service-mvp
**Date**: 2026-03-20
**Status**: Complete

## Overview

This document consolidates research findings for the RAG Service MVP implementation. Each technical decision includes rationale and alternatives considered.

## Unified Tracing Architecture

The service implements a three-layer observability stack for complete end-to-end tracing:

### Layer Responsibilities

| Layer | Tool | Purpose | Monitoring Dimensions |
|-------|------|---------|----------------------|
| **LLM Layer** | LiteLLM | Model invocation gateway + billing + strategy control | Cost (tokens, per-request, user/scenario), Performance (response time, success/fail, fallback), Routing (model selection, decisions) |
| **Agent Layer** | Phidata | AI task execution behavior observation and orchestration | Execution steps, tools called, reasoning paths, tool call chains, task success rate |
| **Prompt Layer** | Langfuse | Prompt template management and trace correlation | Prompt versions, templates, variable interpolation, retrieved docs integration |

### Trace Chain

```
trace_id
    ↓
Phidata (records task execution)
    ↓
CrewAI (records reasoning steps)
    ↓
LiteLLM (records model invocation)
```

### Optimization Closed Loop

The three layers enable: Request → Trace Data → Analysis (which prompts/models/paths work best) → Optimizations (A/B tests, routing adjustments, orchestration refinements) → Improved Next Request

## Call Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           RAG Service Request Flow (with Capability Layer)        │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  ┌─────────┐     ┌──────────────┐     ┌─────────────────────────────────────┐     │
│  │  User   │────▶│   FastAPI    │────▶│      Capability Interface Layer     │     │
│  │Client   │POST │   /ai/agent  │     │   (abstracts all components)        │     │
│  └─────────┘     └──────────────┘     └──────────────┬──────────────────────┘     │
│                                                       │                           │
│                       ┌───────────────────────────────┼───────────────────────┐    │
│                       │                               │                       │    │
│                       ▼                               ▼                       ▼    │
│            ┌──────────────────┐          ┌──────────────────┐    ┌─────────────────┐  │
│            │KnowledgeQuery    │          │ModelInference    │    │TraceObservation│  │
│            │Capability        │          │Capability        │    │Capability      │  │
│            └────────┬─────────┘          └────────┬─────────┘    └────────┬────────┘  │
│                     │                            │                       │           │
└─────────────────────┼────────────────────────────┼───────────────────────┼───────────┘
                      │                            │                       │
                      ▼                            ▼                       ▼           │
┌─────────────────────────────────────────────────────────────────────────────────────┤
│                         Component Implementation Layer                             │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  ┌──────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────┐      │
│  │   Milvus KB  │     │   LiteLLM    │     │   Phidata   │────▶│ Langfuse │      │
│  │(pymilvus)    │     │  Gateway     │     │   Agent     │     │  Trace   │      │
│  └──────────────┘     └──────────────┘     └─────────────┘     └──────────┘      │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘

API Mapping:
├── src/rag_service/main.py → FastAPI app initialization, capability registration
├── src/rag_service/api/routes.py → /ai/agent endpoint (uses capabilities ONLY)
├── src/rag_service/capabilities/knowledge_query.py → KnowledgeQueryCapability interface
├── src/rag_service/capabilities/model_inference.py → ModelInferenceCapability interface
├── src/rag_service/capabilities/trace_observation.py → TraceObservationCapability interface
├── src/rag_service/core/agent.py → Phidata orchestration (internal)
├── src/rag_service/core/tracing.py → Langfuse trace management (internal)
├── src/rag_service/retrieval/knowledge_base.py → Milvus query interface (internal component)
├── src/rag_service/inference/gateway.py → LiteLLM provider routing (internal component)
└── src/rag_service/observability/langfuse_client.py → Langfuse SDK wrapper (internal component)

**Critical Rule**: API routes → Capabilities → Components (no direct Component access from API)
```

## Technical Decisions

### 0. Unified Capability Interface Layer (CORE ARCHITECTURE)

**Decision**: Implement a unified capability interface layer between HTTP endpoints and underlying components.

**Rationale**:
- **Abstraction**: Components (Phidata, LiteLLM, Milvus, Langfuse) are implementation details that should not leak to HTTP layer
- **Flexibility**: Can swap underlying components without changing API contracts
- **Testability**: Can mock capability layer for testing without real component dependencies
- **Evolution**: Future component changes only affect capability layer, not entire codebase
- **Boundary Definition**: Clear separation between "external interface" and "internal implementation"

**Architecture Pattern**:
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Capability Interface Layer                          │
│                        (src/rag_service/capabilities/)                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐         │
│  │ KnowledgeQuery   │  │ ModelInference   │  │ TraceObservation │         │
│  │    Capability    │  │    Capability    │  │    Capability    │         │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘         │
│           │                     │                     │                    │
└───────────┼─────────────────────┼─────────────────────┼────────────────────┘
            │                     │                     │
            ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Component Implementation Layer                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐         │
│  │   Milvus KB      │  │    LiteLLM       │  │    Langfuse      │         │
│  │   (pymilvus)     │  │    Gateway       │  │    SDK           │         │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘         │
│                                                                              │
│  ┌──────────────────┐                                                       │
│  │    Phidata       │                                                       │
│  │    Agent         │                                                       │
│  └──────────────────┘                                                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Capability Interface Definition**:
```python
# src/rag_service/capabilities/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List

class Capability(ABC):
    """Base class for all capability interfaces."""

    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the capability with given context."""
        pass

    @abstractmethod
    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """Validate input before execution."""
        pass

# src/rag_service/capabilities/knowledge_query.py
class KnowledgeQueryCapability(Capability):
    """
    Capability: Query knowledge base and retrieve relevant context.

    Implementation: Delegates to Milvus knowledge base client.
    External API should NOT know about Milvus specifics.
    """

    def __init__(self, knowledge_base_client):
        self._kb_client = knowledge_base_client  # Internal component

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        query = context.get("query")
        top_k = context.get("top_k", 5)

        # Delegate to internal Milvus client
        results = await self._kb_client.search(query, top_k)

        # Transform to capability-specific response format
        return {
            "chunks": [
                {
                    "chunk_id": r.id,
                    "content": r.content,
                    "score": r.score,
                    "source_doc": r.source
                }
                for r in results
            ]
        }

# src/rag_service/capabilities/model_inference.py
class ModelInferenceCapability(Capability):
    """
    Capability: Execute AI model inference with unified interface.

    Implementation: Delegates to LiteLLM gateway for provider routing.
    External API should NOT know about LiteLLM specifics.
    """

    def __init__(self, litellm_gateway):
        self._gateway = litellm_gateway  # Internal component

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = context.get("prompt")
        model_hint = context.get("model_hint")

        # Delegate to internal LiteLLM gateway
        response = await self._gateway.complete(prompt, model_hint)

        # Transform to capability-specific response format
        return {
            "answer": response.text,
            "model_used": response.model,
            "tokens": {
                "input": response.input_tokens,
                "output": response.output_tokens
            },
            "cost": response.cost
        }

# src/rag_service/capabilities/trace_observation.py
class TraceObservationCapability(Capability):
    """
    Capability: Record and retrieve trace data for observability.

    Implementation: Delegates to Langfuse client + internal trace managers.
    External API should NOT know about Langfuse specifics.
    """

    def __init__(self, trace_manager):
        self._trace_manager = trace_manager  # Internal component

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        action = context.get("action")  # "create", "retrieve", "update"

        if action == "create":
            trace_id = await self._trace_manager.create_trace(context)
            return {"trace_id": trace_id}
        elif action == "retrieve":
            trace_data = await self._trace_manager.get_trace(context["trace_id"])
            return trace_data
```

**API Layer Usage**:
```python
# src/rag_service/api/routes.py
from rag_service.capabilities.knowledge_query import KnowledgeQueryCapability
from rag_service.capabilities.model_inference import ModelInferenceCapability

# HTTP routes ONLY interact with capabilities, NOT components directly
@router.post("/ai/agent")
async def query_agent(request: QueryRequest):
    # Use capabilities - don't know about Milvus, LiteLLM, etc.
    kb_capability = app.capabilities["knowledge_query"]
    inference_capability = app.capabilities["model_inference"]

    # Execute capabilities
    kb_result = await kb_capability.execute({"query": request.question, "top_k": 5})

    # Build prompt with retrieved context
    prompt = build_prompt(request.question, kb_result["chunks"])

    inference_result = await inference_capability.execute({
        "prompt": prompt,
        "model_hint": request.model_hint
    })

    return {
        "answer": inference_result["answer"],
        "chunks": kb_result["chunks"],
        "metadata": {
            "model_used": inference_result["model_used"],
            "tokens": inference_result["tokens"]
        }
    }
```

**Component Registration**:
```python
# src/rag_service/main.py
from rag_service.capabilities import (
    KnowledgeQueryCapability,
    ModelInferenceCapability,
    TraceObservationCapability
)
from rag_service.retrieval.knowledge_base import MilvusKnowledgeBase
from rag_service.inference.gateway import LiteLLMGateway

# Initialize components (internal)
kb_client = MilvusKnowledgeBase(host=config.milvus_host)
litellm_gateway = LiteLLMGateway(config_path="litellm_config.yaml")

# Register capabilities (external interface)
app.capabilities = {
    "knowledge_query": KnowledgeQueryCapability(kb_client),
    "model_inference": ModelInferenceCapability(litellm_gateway),
    "trace_observation": TraceObservationCapability(trace_manager)
}
```

**Benefits**:
1. **Loose Coupling**: HTTP layer depends on capability interfaces, not concrete components
2. **Swappable Components**: Replace Milvus with Pinecone without changing API routes
3. **Testing**: Mock capabilities for unit tests instead of real component dependencies
4. **Versioning**: Change component implementations without breaking API contracts
5. **Documentation**: Capability interfaces serve as clear boundaries for architecture documentation

**Capability Catalog**:

| Capability | Purpose | Internal Component | External API Endpoint |
|------------|---------|-------------------|----------------------|
| KnowledgeQuery | Query knowledge base | Milvus client | POST /ai/agent (uses internally) |
| ModelInference | Execute AI model inference | LiteLLM gateway | POST /ai/agent (uses internally) |
| TraceObservation | Create/retrieve traces | Langfuse + Phidata | GET /traces/{id} |
| DocumentManagement | Add/remove documents | Milvus client | POST /documents, DELETE /documents/{id} |
| ModelDiscovery | List available models | LiteLLM gateway | GET /models |
| HealthCheck | Check component health | All components | GET /health |

**Alternatives Considered**:
| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| Unified Capability Layer | Clean abstraction, swappable, testable | More upfront design | **SELECTED** |
| Direct Component Usage | Less code, simpler initially | Tight coupling, hard to change | Rejected |
| Service Layer Pattern | Good separation | Still may expose component details | Capability layer more explicit |
| Facade Pattern | Simple wrapper | May become complex God object | Capability per concern |

### 1. Python Version Selection

**Decision**: Python 3.11

**Rationale**:
- Stable and widely adopted (released Oct 2022)
- Full async/await support with improved error messages
- All primary dependencies (FastAPI, Phidata, LiteLLM, pymilvus) support 3.11+
- Better performance for async operations vs 3.10
- 3.12 is newer but 3.11 has better ecosystem maturity

**Alternatives Considered**:
| Version | Pros | Cons | Decision |
|---------|------|------|----------|
| 3.11 | Stable, mature ecosystem, great async support | Slightly older | **SELECTED** |
| 3.12 | Latest features, improved speed | Some dependencies may have compatibility issues | Deferred |
| 3.10 | Widely compatible | Older async patterns, less performant | Rejected |

### 2. Phidata Integration Patterns

**Decision**: Use Phidata Agent with tool-based retrieval

**Rationale**:
- Phidata provides built-in RAG patterns with agent abstraction
- Tools pattern allows clean separation of retrieval and inference
- Native support for tracing/observation hooks
- Python-first API with good async support

**Integration Pattern**:
```python
# src/rag_service/core/agent.py
from phi.agent import Agent
from phi.tools import Toolkit

# Create agent with RAG tools
agent = Agent(
    name="rag-agent",
    tools=[retrieval_tool, inference_tool],
    instructions="Use retrieved context to answer user questions",
    show_tool_calls=True  # For trace visibility
)
```

**Best Practices**:
- Register tools with clear names and descriptions
- Use callback hooks for trace stage transitions
- Implement timeout handling for tool calls
- Validate tool outputs before agent consumption

**Alternatives Considered**:
| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| Phidata Agent | Built-in RAG, clean API | Learning curve for DSL | **SELECTED** |
| LangChain | Mature, widely used | Heavier, more complex | Rejected |
| Custom orchestration | Full control | More code to maintain | Rejected |

### 3. Milvus Python SDK

**Decision**: pymilvus 2.3+ with connection pooling

**Rationale**:
- Official Python SDK with active maintenance
- Built-in connection pooling and retry logic
- Supports both standalone and cluster modes
- Good async patterns for query operations

**Integration Pattern**:
```python
# src/rag_service/retrieval/knowledge_base.py
from pymilvus import connections, Collection

class KnowledgeBase:
    def __init__(self, host="localhost", port="19530"):
        connections.connect(
            alias="default",
            host=host,
            port=port,
            pool_size=10
        )
        self.collection = Collection("documents")

    async def search(self, query_vector: List[float], top_k: int = 5):
        return self.collection.search(
            data=[query_vector],
            anns_field="embedding",
            param={"metric_type": "COSINE", "params": {"nprobe": 10}},
            limit=top_k
        )
```

**Best Practices**:
- Use connection pooling (default pool_size=10)
- Implement retry logic for transient failures
- Validate collection schema before queries
- Log search latency for observability

**Alternatives Considered**:
| Library | Pros | Cons | Decision |
|---------|------|------|----------|
| pymilvus | Official, full-featured | Python-native blocking I/O | **SELECTED** with async wrapper |
| milvus-lite | Lightweight, embedded | Limited features, early stage | Rejected |
| REST API | Language-agnostic | Higher latency | Rejected |

### 4. LiteLLM Configuration

**Decision**: Centralized configuration with environment-based provider selection

**Rationale**:
- Single configuration file for all providers
- Environment variables for secrets (API keys)
- Runtime provider switching via request parameters
- Built-in retry and fallback support

**Configuration Pattern**:
```python
# litellm_config.yaml
model_list:
  - model_name: ollama/llama3
    litellm_params:
      api_base: http://localhost:11434
  - model_name: openai/gpt-4
    litellm_params:
      api_key: ${OPENAI_API_KEY}
  - model_name: claude-3-opus
    litellm_params:
      api_key: ${ANTHROPIC_API_KEY}
```

**Best Practices**:
- Use environment variables for all credentials
- Set appropriate timeouts per provider
- Enable request/response logging for debugging
- Implement fallback chains for critical requests

**Provider Support Matrix**:
| Provider | Type | Status | Notes |
|----------|------|--------|-------|
| Ollama | Local | Supported | vLLM/SGLang compatible |
| OpenAI | Cloud | Supported | GPT-4, GPT-3.5 |
| Claude | Cloud | Supported | Anthropic API |
| vLLM | Local | Supported | OpenAI-compatible endpoint |
| SGLang | Local | Supported | OpenAI-compatible endpoint |

**Alternatives Considered**:
| Gateway | Pros | Cons | Decision |
|---------|------|------|----------|
| LiteLLM | Multi-provider, unified API | Additional dependency | **SELECTED** |
| Direct SDK calls | No abstraction overhead | Provider lock-in | Rejected |
| Custom gateway | Full control | Maintenance burden | Rejected |

### 5. Langfuse Async Integration

**Decision**: Langfuse Python SDK with async trace capture

**Rationale**:
- Official SDK with async support
- Non-blocking trace flush (buffered writes)
- Automatic trace ID generation
- Built-in span management for nested operations

**Integration Pattern**:
```python
# src/rag_service/observability/langfuse_client.py
from langfuse import Langfuse
from langfuse.async_client import AsyncLangfuse

class ObservabilityClient:
    def __init__(self):
        self.client = AsyncLangfuse()

    async def create_trace(self, trace_id: str, prompt: str, context: dict):
        await self.client.trace(
            id=trace_id,
            name="rag-query",
            input={"prompt": prompt, "context": context}
        )

    async def flush(self):
        # Non-blocking flush
        await self.client.flush_async()
```

**Non-Blocking Strategy**:
- Use async client for all operations
- Wrap trace calls in try/except to prevent request failures
- Implement background task for trace flush
- Set reasonable timeout for trace operations

**Span Structure**:
```
Trace: rag-query (unique ID)
├── Span: retrieval (Milvus query)
│   ├── latency_ms
│   ├── chunks_count
│   └── chunk_ids
├── Span: inference (LLM call)
│   ├── model_id
│   ├── latency_ms
│   ├── prompt_tokens
│   └── completion_tokens
└── Span: completion (response generation)
    ├── total_tokens
    └── estimated_cost
```

**Alternatives Considered**:
| Tool | Pros | Cons | Decision |
|------|------|------|----------|
| Langfuse | Purpose-built for LLM apps | Newer ecosystem | **SELECTED** |
| Arize Phoenix | More mature | Heavier setup | Rejected |
| Weights & Biases | ML-focused | Less LLM-specific | Rejected |
| Custom tracing | Full control | Maintenance burden | Rejected |

### 6. Unified Tracing Architecture

**Decision**: Three-layer observability stack with unified trace_id propagation

**Rationale**:
- Enables complete request-to-cost-to-quality optimization loop
- Each layer has distinct responsibilities that combine for full observability
- Unified trace_id allows cross-layer correlation for debugging and optimization
- Industry best practice for multi-component AI systems

**Layer Integration**:
```python
# src/rag_service/observability/trace_manager.py
class UnifiedTraceManager:
    def __init__(self):
        self.litellm_observer = LiteLLMObserver()   # LLM Layer
        self.phidata_observer = PhidataObserver()   # Agent Layer
        self.langfuse_client = LangfuseClient()     # Prompt Layer

    async def create_trace(self, request_id: str) -> str:
        trace_id = f"{request_id}_{uuid.uuid4().hex[:8]}"

        # Initialize across all layers
        await self.phidata_observer.task_start(trace_id, request_id)
        await self.langfuse_client.create_trace(trace_id)

        return trace_id

    async def link_inference(self, trace_id: str, model: str, tokens: dict):
        # Link Phidata reasoning → LiteLLM invocation
        await self.phidata_observer.record_llm_call(trace_id, model)
        await self.litellm_observer.capture_inference(trace_id, model, tokens)
```

**Cross-Layer Metrics**:
- **Cost**: LiteLLM captures token counts, calculates costs per user/scenario
- **Quality**: Phidata captures task success, reasoning paths, tool effectiveness
- **Performance**: All layers capture latency, enabling bottleneck identification
- **Optimization**: Correlate prompt versions (Langfuse) + model choices (LiteLLM) + agent paths (Phidata)

**Alternatives Considered**:
| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| Unified 3-layer | Complete observability, optimization loop | More complex integration | **SELECTED** |
| Single-layer tracing | Simpler implementation | Blind spots in optimization | Rejected |
| No unified trace_id | Easier implementation | Cannot correlate across layers | Rejected |

### 7. FastAPI Testing Patterns

**Decision**: pytest with TestClient and async fixtures

**Rationale**:
- FastAPI provides TestClient for endpoint testing
- pytest-asyncio for async test functions
- Fixture-based server lifecycle management
- Native support for dependency injection overrides

**Testing Pattern**:
```python
# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from rag_service.main import app

@pytest.fixture
async def client():
    # Setup: Start server with test config
    async with LifespanManager(app):
        yield TestClient(app)

# tests/integration/test_api_endpoints.py
async def test_agent_query_with_context(client):
    response = client.post(
        "/ai/agent",
        json={"question": "What is RAG?"}
    )
    assert response.status_code == 200
    assert "answer" in response.json()
```

**Server Startup Requirements** (Constitution Principle IV):
- Tests must start real server (not just mock routes)
- Use test configuration (separate from production)
- Clean up resources in fixture teardown
- Verify server health before running tests

**Alternatives Considered**:
| Framework | Pros | Cons | Decision |
|-----------|------|------|----------|
| pytest + TestClient | FastAPI native, async support | None | **SELECTED** |
| httpx.AsyncClient | More realistic | More setup | Rejected |
| unittest.mock | Built-in | Violates constitution (real-first) | Rejected |

### 8. Vector Embedding Model

**Decision**: OpenAI text-embedding-3-small for MVP

**Rationale**:
- High quality embeddings (1536 dimensions)
- Cost-effective for MVP validation
- Well-documented and stable
- Works with Milvus cosine similarity

**Embedding Service Pattern**:
```python
# src/rag_service/retrieval/embeddings.py
from openai import OpenAI

class EmbeddingService:
    def __init__(self):
        self.client = OpenAI()

    async def embed_text(self, text: str) -> List[float]:
        response = await self.client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
            dimensions=1536
        )
        return response.data[0].embedding
```

**Alternatives Considered**:
| Model | Pros | Cons | Decision |
|-------|------|------|----------|
| text-embedding-3-small | Quality, cost balance | Cloud API | **SELECTED** |
| sentence-transformers | Local, free | Inferior quality | Rejected |
| BGE-M3 | Open source, multilingual | Less tested | Deferred |

## Architecture Reference

### Component Responsibilities

| Layer | Component | File | Responsibility | Dependencies |
|-------|-----------|------|-----------------|--------------|
| **Capability Layer** | Base Capability | capabilities/base.py | Abstract capability interface definition | ABC |
| **Capability Layer** | KnowledgeQueryCapability | capabilities/knowledge_query.py | Query knowledge base via unified interface | Milvus (internal) |
| **Capability Layer** | ModelInferenceCapability | capabilities/model_inference.py | Execute model inference via unified interface | LiteLLM (internal) |
| **Capability Layer** | TraceObservationCapability | capabilities/trace_observation.py | Record/retrieve trace data via unified interface | Langfuse, Phidata (internal) |
| **Capability Layer** | DocumentManagementCapability | capabilities/document_management.py | Add/remove documents via unified interface | Milvus (internal) |
| **Capability Layer** | ModelDiscoveryCapability | capabilities/model_discovery.py | List available models via unified interface | LiteLLM (internal) |
| **Capability Layer** | HealthCheckCapability | capabilities/health_check.py | Check health of all components via unified interface | All components |
| **API Layer** | FastAPI App | main.py | Server initialization, capability registration | FastAPI, uvicorn |
| **API Layer** | API Routes | api/routes.py | Endpoint handlers using capabilities ONLY | Pydantic, Capabilities |
| **Component Layer** | Agent Orchestrator | core/agent.py | RAG flow coordination | Phidata |
| **Component Layer** | Unified Trace Manager | observability/trace_manager.py | trace_id propagation across layers | LiteLLM, Phidata, Langfuse |
| **Component Layer** | Phidata Observer | observability/phidata_observer.py | Agent layer metrics (steps, tools, reasoning) | Phidata |
| **Component Layer** | LiteLLM Observer | observability/litellm_observer.py | LLM layer metrics (cost, routing, performance) | LiteLLM |
| **Component Layer** | Langfuse Client | observability/langfuse_client.py | Prompt layer metrics (versions, templates) | Langfuse |
| **Component Layer** | Knowledge Base | retrieval/knowledge_base.py | Milvus query interface (INTERNAL) | pymilvus |
| **Component Layer** | Embeddings | retrieval/embeddings.py | Text vectorization | OpenAI |
| **Component Layer** | Model Gateway | inference/gateway.py | LiteLLM routing (INTERNAL) | LiteLLM |

**IMPORTANT**:
- **API Layer** MUST only use **Capability Layer** interfaces
- **API Layer** MUST NOT directly access **Component Layer**
- **Capability Layer** wraps **Component Layer** implementations
- This enables component swapping without API changes

### API Endpoints

| Method | Endpoint | Purpose | Request | Response |
|--------|----------|---------|---------|----------|
| POST | /ai/agent | Main RAG query | {question, model?} | {answer, context, trace_id} |
| GET | /health | Health check | - | {status} |
| GET | /models | List available models | - | {models: []} |

### Data Flow Summary

```
1. User POST /ai/agent {question}
2. FastAPI → routes.py → ONLY accesses capabilities
3. KnowledgeQueryCapability.execute({query}) → internally calls Milvus.search()
4. ModelInferenceCapability.execute({prompt, model_hint}) → internally calls LiteLLM.complete()
5. TraceObservationCapability.execute({action: "create"}) → internally calls Langfuse.create_trace()
6. Components (Milvus, LiteLLM, Langfuse) are NEVER accessed directly by routes.py
7. HTTP 200 {answer, context, trace_id} returned to user
```

**Critical Flow Rules**:
- API routes MUST use Capability interfaces ONLY
- Capabilities internally delegate to Components
- Components are NEVER exposed to API layer
- Swapping components requires ONLY capability implementation changes, NOT API changes

## Open Questions & Risks

### Resolved
- ✅ Python version: 3.11
- ✅ Async strategy: Native async/await with async SDKs
- ✅ Testing approach: pytest with TestClient, real implementations

### Monitoring
- ⚠️ LiteLLM fallback behavior under provider failures
- ⚠️ Milvus query performance with large collections
- ⚠️ Langfuse trace buffer overflow under high load

### Mitigations
- Implement circuit breaker for failing providers
- Set reasonable timeouts for all external calls
- Use background thread for trace flushing
- Document all blocking points in tests

## References

- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [Phidata Documentation](https://docs.phidata.com/)
- [LiteLLM Proxy](https://docs.litellm.ai/)
- [Milvus Python SDK](https://milvus.io/api-reference/pymilvus/v2.3.x/About.md)
- [Langfuse Python SDK](https://langfuse.com/docs/sdk/python)
