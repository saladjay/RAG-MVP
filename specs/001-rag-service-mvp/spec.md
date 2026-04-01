# Feature Specification: RAG Service MVP - AI Component Validation Platform

**Feature Branch**: `001-rag-service-mvp`
**Created**: 2026-03-20
**Status**: Draft
**Input**: User description: "我需要创建一个最小可用程序，目的是构建一个RAG服务，是一个http服务，我需要验证多个AI开发组件的开发潜力。使用uv管理环境；Phidata制作agent；使用一个http post接口调用知识库；LiteLLM当作模型网关，代理所有模型推理（包括但不限于本地Ollama, vllm, sglang, 云端不同平台的openai和Claude API协议）；langfuse跟踪记录prompt, 检索耗时，记录prompt模板，模型id, latency， token等；"

**Additional Context**: System flow diagram provided showing interaction patterns between user, AI service, model gateway, knowledge base, and observability platform. Additional detail provided on unified tracing architecture with three-layer observability: LLM Layer (LiteLLM), Agent Layer (Phidata), and Prompt Layer (Langfuse).

## System Flow Overview

The service follows a request-response flow where:

1. **Request Entry**: User submits queries through an agent endpoint (`/ai/agent`)
2. **Trace Initiation**: Each request generates a unique trace ID for observability tracking
3. **Knowledge Retrieval**: System queries the knowledge base for relevant context
4. **Model Inference**: Retrieved context and user query are sent to AI models via a unified gateway
5. **Response Generation**: System synthesizes and returns the final answer
6. **Observability Capture**: At each step, metrics (timing, tokens, templates, model IDs) are captured for analysis

---

## Unified Tracing Architecture

The service implements a three-layer observability stack for complete end-to-end tracing from request to reasoning to cost to quality:

### Observability Layers

| Layer | Tool | Responsibility | Monitoring Dimensions |
|-------|------|----------------|------------------------|
| **LLM Layer** | LiteLLM | Model invocation gateway + billing + strategy control | Cost (tokens, per-request cost, user/scenario cost), Model Performance (response time, success/fail rate, fallback), Routing Decisions (request → model selection → fallback → outcome) |
| **Agent Layer** | Phidata | AI task execution behavior observation and orchestration | Execution steps, tools called, reasoning paths, tool call chains, input/output, task success rate |
| **Prompt Layer** | Langfuse | Prompt template management and trace correlation | Prompt versions, templates used, variable interpolation, retrieval integration |

### Complete Trace Chain

All layers share a unified `trace_id` for complete request correlation:

```
trace_id
    ↓
Phidata (records task execution)
    ↓
CrewAI (records reasoning steps)
    ↓
LiteLLM (records model invocation)
```

### Layer Responsibilities

#### LiteLLM: LLM Invocation Layer

**Purpose**: Unified observation and control of model calls

**Capabilities**:
- Gateway: Single entry point for all model providers
- Billing: Token counting, per-request cost calculation, user/scenario cost aggregation
- Strategy Control: Model selection, load balancing, fallback management

**Monitoring Dimensions**:

| Dimension | Metrics |
|-----------|---------|
| **Cost** | Token count (input/output), per-request cost, cost per user, cost per scenario, cumulative cost over time |
| **Model Performance** | Response time (p50/p95/p99), success rate, failure rate, timeout rate, fallback trigger rate |
| **Routing Decisions** | Request → model selected, fallback occurred (yes/no), alternative models tried, final outcome |

#### Phidata: Agent Execution Layer

**Purpose**: AI task execution behavior observation and orchestration

**Capabilities**:
- Task decomposition and step tracking
- Tool call orchestration and monitoring
- Reasoning path visualization

**Monitoring Dimensions**:

| Dimension | Metrics |
|-----------|---------|
| **Execution** | Steps executed, step duration, step order, parallel vs sequential execution |
| **Tools** | Tools called, call frequency, tool success rate, tool latency, tool call chains |
| **Reasoning** | Reasoning path length, decision points, branches taken, backtracking events |
| **Task Outcome** | Task success rate, failure reasons, completion percentage, output quality score |

#### Langfuse: Prompt Management Layer

**Purpose**: Prompt template versioning, variable interpolation, and correlation

**Capabilities**:
- Prompt template storage and versioning
- Variable interpolation tracking
- A/B testing support
- Trace-to-prompt linking

**Monitoring Dimensions**:

| Dimension | Metrics |
|-----------|---------|
| **Template** | Template version used, variable values provided, interpolation success rate |
| **Performance** | Template effectiveness, template comparison (A/B test), variant performance |
| **Integration** | Retrieved docs injected, context added, final prompt length |

### Cross-Layer Correlation

The unified `trace_id` enables:

1. **Request → Cost**: Track total cost per request across all model calls
2. **Request → Quality**: Correlate task success with specific prompt versions and model choices
3. **Cost → Quality**: Analyze which prompt/model combinations provide best cost-performance ratio
4. **Optimization Loop**: Use trace data to optimize prompts, model selection, and routing strategies

### Trace Flow Example

```
User Request: "What is RAG?"
     │
     ▼ Generate trace_id: "trace_abc123"
     │
     ├─▶ Phidata Layer
     │   - Record task start
     │   - Determine execution plan
     │   - Select tools: [knowledge_base, llm]
     │   │
     │   ├─▶ Knowledge Retrieval
     │   │   - Query Milvus
     │   │   - Return 3 chunks
     │   │
     │   └─▶ CrewAI/Reasoning
     │       - Decide to call LLM with context
     │       │
     │       └─▶ LiteLLM Layer
     │           - Route to: ollama/llama3
     │           - Record: 150 input tokens, 85 output tokens
     │           - Cost: $0.000 (local model)
     │           - Latency: 1.2s
     │
     ├─▶ Langfuse Layer
     │   - Record prompt version: "v1.2"
     │   - Variables: {question: "What is RAG?", context: [...]}
     │   - Retrieved docs: [chunk_1, chunk_2, chunk_3]
     │
     └─▶ Complete Trace Record
        - trace_id: "trace_abc123"
        - Phidata data: steps, tools, reasoning
        - LiteLLM data: costs, performance, routing
        - Langfuse data: prompts, variables, versions
```

### Optimization Closed Loop

The three layers together enable a complete optimization cycle:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Optimization Closed Loop                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐     Trace Data     ┌──────────────────────────────────┐    │
│  │   Request   │───────────────────▶│    Unified Observability          │    │
│  │             │                    │    ├─ LiteLLM (Costs)            │    │
│  └─────────────┘                    │    ├─ Phidata (Behavior)        │    │
│                                      │    └─ Langfuse (Prompts)       │    │
│                                      └──────────────┬─────────────────┘    │
│                                                     │                       │
│                                                     ▼                       │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     Analysis & Insights                            │    │
│  │  - Which prompts produce best results?                             │    │
│  │  - Which models provide best cost-performance ratio?               │    │
│  │  - Which agent paths lead to successful outcomes?                  │    │
│  │  - Where are failures occurring?                                   │    │
│  └────────────────────────────┬───────────────────────────────────────┘    │
│                               │                                             │
│                               ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     Optimizations                                   │    │
│  │  - A/B test new prompt versions (Langfuse)                         │    │
│  │  - Adjust model routing strategies (LiteLLM)                        │    │
│  │  - Refine agent orchestration (Phidata)                             │    │
│  └────────────────────────────┬───────────────────────────────────────┘    │
│                               │                                             │
└───────────────────────────────┼─────────────────────────────────────────────┘
                                │
                                ▼
                      ┌─────────────────┐
                      │  Next Request    │
                      │  (Improved)      │
                      └─────────────────┘
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Knowledge Base Query (Priority: P1)

A developer wants to query a knowledge base and receive relevant, contextually accurate answers generated by AI models. The developer sends a question via HTTP POST and receives a response that includes retrieved context and the AI-generated answer.

**Why this priority**: This is the core functionality of a RAG service - without the ability to query knowledge and get answers, the service provides no value.

**Independent Test**: Can be tested by sending a POST request with a question to the knowledge base endpoint and verifying the response contains both retrieved context and an AI-generated answer.

**Acceptance Scenarios**:

1. **Given** a knowledge base with indexed documents, **When** a user sends a POST request with a question, **Then** the system returns relevant document excerpts and an AI-generated answer
2. **Given** a knowledge base, **When** a user sends a question with no relevant documents, **Then** the system returns a response indicating no relevant context was found
3. **Given** the service is running, **When** multiple concurrent queries are submitted, **Then** each query receives an independent response without data mixing

---

### User Story 2 - Multi-Model Inference (Priority: P2)

A developer wants to validate different AI models by routing inference requests through a unified gateway. The service should support local models (Ollama, vLLM, SGLang) and cloud APIs (OpenAI, Claude) without changing client code.

**Why this priority**: This enables the core validation goal of the project - assessing multiple AI components' development potential. The gateway abstraction allows easy model switching and comparison.

**Independent Test**: Can be tested by configuring different model providers and verifying inference requests are correctly routed and responses returned from each provider.

**Acceptance Scenarios**:

1. **Given** a configured local Ollama endpoint, **When** an inference request is made, **Then** the response comes from Ollama
2. **Given** a configured OpenAI API key, **When** an inference request is made, **Then** the response comes from OpenAI
3. **Given** multiple model providers configured, **When** requests specify different models, **Then** each request routes to the appropriate provider

---

### User Story 3 - Observability and Tracing (Priority: P3)

A developer wants to analyze system performance and debug issues by reviewing detailed traces of each request. The system must capture metrics at each processing stage: request initiation (prompt, user context), knowledge retrieval (retrieval time, retrieved chunks), model inference (prompt template, model ID, latency), and completion (token consumption, calculated cost).

**Why this priority**: Observability is critical for validation and optimization but is not required for basic functionality. The service works without it, but cannot be properly evaluated.

**Independent Test**: Can be tested by making a query and then verifying that a corresponding trace record exists with all required metrics (initial prompt, retrieval time, retrieved chunks, prompt template, model ID, latency, tokens, cost).

**Acceptance Scenarios**:

1. **Given** a request is processed, **When** the request completes, **Then** a trace record is created with initial prompt, retrieval time, chunks retrieved, prompt template, model ID, latency, and token counts
2. **Given** multiple requests are made, **When** reviewing traces, **Then** each trace is uniquely identifiable and contains all metrics for each processing stage
3. **Given** a request fails, **When** reviewing traces, **Then** the failure and error details are captured
4. **Given** a trace is being recorded, **When** the observability backend is temporarily unavailable, **Then** the request still processes successfully (trace recording is non-blocking)

---

### User Story 4 - Knowledge Base Management (Priority: P4)

A developer wants to add, update, or remove documents from the knowledge base to keep the RAG system's information current.

**Why this priority**: Knowledge base management is important for production use but for initial validation, a static knowledge base is sufficient to demonstrate RAG functionality.

**Independent Test**: Can be tested by uploading new documents and verifying they are indexed and returned in subsequent queries.

**Acceptance Scenarios**:

1. **Given** a new document is uploaded, **When** indexing completes, **Then** queries related to the document return relevant excerpts from it
2. **Given** an existing document is updated, **When** re-indexing completes, **Then** queries return the updated content

---

### Edge Cases

- What happens when the configured model endpoint is unavailable or returns errors?
- How does the system handle requests exceeding size limits (very long prompts or documents)?
- What happens when multiple requests try to modify the same knowledge base document concurrently?
- How does the system handle malformed requests or invalid configuration?
- What happens when the observability backend is unavailable during request processing?
- What happens when the knowledge base returns no relevant documents for a query?
- How does the system handle timeout scenarios at each processing stage (retrieval, inference)?
- What happens when token limits are exceeded during model inference?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide an HTTP POST endpoint for agent-based queries
- **FR-002**: System MUST retrieve relevant documents from the knowledge base based on query content
- **FR-003**: System MUST generate answers using retrieved context as input to AI models
- **FR-004**: System MUST support multiple model providers through a unified gateway interface
- **FR-005**: System MUST route inference requests to appropriate model providers (local Ollama, vLLM, SGLang, cloud OpenAI/Claude)
- **FR-006**: System MUST generate a unique trace ID for each incoming request
- **FR-007**: System MUST capture and record observability metrics at each processing stage:
  - Request initiation: initial prompt, user context
  - Knowledge retrieval: retrieval time, retrieved chunks
  - Model inference: prompt template, model ID, latency
  - Completion: token consumption, calculated cost
- **FR-013**: System MUST implement unified tracing with a single `trace_id` that propagates across all layers (Phidata → CrewAI → LiteLLM)
- **FR-014**: System MUST capture LiteLLM metrics: token counts, per-request cost, user/scenario costs, response time, success/fail rates, fallback events, routing decisions
- **FR-015**: System MUST capture Phidata metrics: execution steps, tools called, reasoning paths, tool call chains, input/output, task success rate
- **FR-016**: System MUST capture Langfuse metrics: prompt version, template used, variable values, retrieved docs injected
- **FR-008**: System MUST maintain isolation between concurrent requests (no data leakage)
- **FR-009**: System MUST return appropriate error responses when requests cannot be processed
- **FR-010**: System MUST support configurable model provider endpoints and credentials
- **FR-011**: System MUST document the HTTP API interface for all endpoints
- **FR-012**: System MUST continue processing requests even when observability recording fails (non-blocking tracing)

### Key Entities

- **Query Request**: Contains user question, optional context parameters, and model selection preferences
- **Query Response**: Contains AI-generated answer, retrieved document excerpts, and metadata (model used, timing, token counts)
- **Document**: Represents a unit of knowledge content with source, content, and metadata attributes
- **Unified Trace**: A complete trace record linked by a single `trace_id` containing data from all three layers:
  - **Phidata Layer**: Task execution data, steps performed, tools called, reasoning path
  - **LiteLLM Layer**: Model invocation data, token counts, costs, routing decisions, fallback events
  - **Langfuse Layer**: Prompt template version, variables, retrieved docs integration
- **LiteLLM Trace Record**: LLM layer metrics including:
  - Cost: token counts (input/output), per-request cost, user cost, scenario cost
  - Performance: response time, success/failure rate, timeout rate
  - Routing: model selected, fallback triggered, alternative models, final outcome
- **Phidata Trace Record**: Agent layer metrics including:
  - Execution: steps executed, step duration, execution order (parallel/sequential)
  - Tools: tools called, call frequency, tool success rate, tool call chains
  - Reasoning: reasoning path length, decision points, branches taken
  - Outcome: task success rate, failure reasons, completion percentage
- **Langfuse Trace Record**: Prompt layer metrics including:
  - Template: version used, variable values, interpolation success
  - Performance: template effectiveness, A/B test variants, variant performance
  - Integration: retrieved docs injected, context added, final prompt length
- **Model Provider Configuration**: Contains endpoint URL, authentication credentials, and supported model identifiers
- **Retrieved Chunk**: A unit of knowledge returned from the knowledge base, including content, source document reference, and relevance score

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Service successfully processes at least 3 different model providers (e.g., Ollama, OpenAI, Claude)
- **SC-002**: End-to-end query response time is under 10 seconds for typical queries
- **SC-003**: All processed requests have corresponding trace records with complete metrics across all stages (request, retrieval, inference, completion)
- **SC-004**: Service handles 10 concurrent requests without failure or data leakage
- **SC-005**: Knowledge base retrieval returns relevant context for test queries (measured by manual verification)
- **SC-006**: HTTP API is fully documented with examples for each endpoint
- **SC-007**: Environment can be set up and service started within 15 minutes using provided setup instructions
- **SC-008**: Trace records include all required metrics: initial prompt, user context, retrieval time, retrieved chunks count, prompt template, model ID, latency, token counts, and cost
- **SC-009**: Unified `trace_id` propagates across all three layers (Phidata → CrewAI → LiteLLM) for complete request correlation
- **SC-010**: LiteLLM layer captures: token counts, per-request costs, user/scenario costs, response times, success/fail rates, routing decisions
- **SC-011**: Phidata layer captures: execution steps, tools called, reasoning paths, tool call chains, task success rates
- **SC-012**: Langfuse layer captures: prompt versions, template variables, retrieved docs integration, interpolation results
- **SC-013**: Cross-layer correlation enables cost-to-quality analysis for optimization (which prompts/models/paths produce best results)

## Assumptions

1. **Local model availability**: Local model servers (Ollama, vLLM, SGLang) will be installed and configured separately from this service
2. **API credentials**: Cloud API keys (OpenAI, Claude) will be provided by the user through configuration
3. **Knowledge base format**: Initial implementation assumes text-based documents; other formats may require additional processing
4. **Deployment environment**: Service is intended for development/validation use, not production deployment
5. **Network access**: Service assumes network connectivity to cloud APIs and local model endpoints
6. **Observability backend**: Langfuse instance or compatible service is accessible for trace storage
7. **Observability failure handling**: Trace recording failures should not block request processing
8. **Trace completeness**: A complete trace spans all stages from request initiation to completion with metrics captured at each boundary

## Out of Scope

The following features are explicitly out of scope for this MVP:

- User authentication and authorization
- Knowledge base document management UI (only API endpoints)
- Real-time streaming responses
- Multi-tenancy or user-isolated knowledge bases
- Advanced retrieval strategies (hybrid search, reranking, query transformation)
- Response caching
- Rate limiting
- Production deployment configurations
