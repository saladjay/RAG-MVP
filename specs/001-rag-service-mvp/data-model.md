# Data Model: RAG Service MVP

**Feature**: 001-rag-service-mvp
**Date**: 2026-03-20
**Status**: Complete

## Overview

This document defines the data entities used in the RAG Service MVP. Entities are organized by domain responsibility and include field definitions, validation rules, and relationships.

## Entity Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          RAG Service Data Model                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐    uses    ┌─────────────────┐    stores    ┌────────┐│
│  │  QueryRequest   │───────────▶│  ModelProvider  │─────────────▶│ Config ││
│  │  ─────────────  │            │  ─────────────  │              │  File  ││
│  │  question       │            │  provider_id    │              └────────┘│
│  │  model_hint     │            │  endpoint       │                        │
│  │  context        │            │  credentials    │                        │
│  └────────┬────────┘            └─────────────────┘                        │
│           │                                                                  │
│           │ generates                                                         │
│           ▼                                                                  │
│  ┌─────────────────┐    contains    ┌─────────────────┐                     │
│  │  QueryResponse  │◀──────────────│ RetrievedChunk   │                     │
│  │  ─────────────  │                │ ───────────────  │                     │
│  │  answer         │                │ chunk_id         │                     │
│  │  chunks         │                │ content          │                     │
│  │  trace_id       │                │ score            │                     │
│  │  metadata       │                │ source_doc       │                     │
│  └─────────────────┘                │ timestamp        │                     │
│                                      └─────────────────┘                     │
│                                                                              │
│  ┌─────────────────┐    tracks     ┌─────────────────┐                     │
│  │   TraceRecord   │──────────────▶│  TraceSpan      │                     │
│  │  ─────────────  │                │ ───────────────  │                     │
│  │  trace_id       │                │ span_name        │                     │
│  │  request_prompt │                │ span_type        │                     │
│  │  user_context   │                │ latency_ms       │                     │
│  │  start_time     │                │ metadata         │                     │
│  │  end_time       │                │ parent_span      │                     │
│  └─────────────────┘                └─────────────────┘                     │
│                                                                              │
│  ┌─────────────────┐    indexed in  ┌─────────────────┐                     │
│  │    Document     │──────────────▶│   MilvusChunk   │                     │
│  │  ─────────────  │                │ ───────────────  │                     │
│  │  doc_id         │                │ chunk_id         │                     │
│  │  title          │                │ vector          │                     │
│  │  content        │                │ text            │                     │
│  │  source         │                │ doc_id          │                     │
│  │  metadata       │                │ index_fields    │                     │
│  └─────────────────┘                └─────────────────┘                     │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Core Entities

### QueryRequest

Represents an incoming query from a user.

| Field | Type | Required | Validation | Description |
|-------|------|----------|------------|-------------|
| question | string | Yes | Length: 1-2000 chars | User's question |
| model_hint | string | No | Valid model ID | Suggested model to use |
| context | dict | No | JSON-serializable | Additional context |
| request_id | string | No | UUID v4 format | Unique request identifier |

**Validation Rules**:
- `question` cannot be empty or only whitespace
- `model_hint` must match configured provider if provided
- `context` must be JSON-serializable

**State Transitions**: N/A (immutable request object)

### QueryResponse

Represents the response returned to the user.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| answer | string | Yes | AI-generated answer |
| chunks | list[RetrievedChunk] | Yes | Retrieved document chunks |
| trace_id | string | Yes | Associated trace ID |
| metadata | dict | No | Additional response metadata |

**Metadata Fields**:
- `model_used`: ID of model that generated answer
- `total_latency_ms`: End-to-end processing time
- `retrieval_time_ms`: Knowledge retrieval time
- `inference_time_ms`: Model inference time
- `input_tokens`: Token count for input
- `output_tokens`: Token count for output
- `estimated_cost`: Calculated cost in USD

### RetrievedChunk

Represents a single chunk of knowledge retrieved from the vector database.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| chunk_id | string | Yes | Unique chunk identifier |
| content | string | Yes | Chunk text content |
| score | float | Yes | Relevance score (0-1) |
| source_doc | string | Yes | Source document identifier |
| timestamp | datetime | Yes | When chunk was created/indexed |

**Validation Rules**:
- `score` must be between 0 and 1
- `content` must not be empty

### TraceRecord

Represents a complete trace of a request through the system.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| trace_id | string | Yes | Unique trace identifier (UUID) |
| request_prompt | string | Yes | Original user question |
| user_context | dict | No | User context from request |
| start_time | datetime | Yes | Request start timestamp |
| end_time | datetime | Yes | Request completion timestamp |
| spans | list[TraceSpan] | Yes | Individual operation spans |

**Span Types**:
- `retrieval`: Knowledge base query
- `inference`: Model inference call
- `completion`: Response generation

### TraceSpan

Represents a single operation within a trace.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| span_id | string | Yes | Unique span identifier |
| span_name | string | Yes | Human-readable span name |
| span_type | string | Yes | Type of operation |
| latency_ms | float | Yes | Operation duration |
| metadata | dict | No | Span-specific metrics |
| parent_span | string | No | Parent span ID if nested |

**Span Metadata by Type**:

**Retrieval Span**:
- `chunks_count`: Number of chunks retrieved
- `chunk_ids`: List of chunk identifiers
- `query_vector_used`: Embedding model used

**Inference Span**:
- `model_id`: Model identifier
- `prompt_template`: Template used for prompt
- `input_tokens`: Input token count
- `output_tokens`: Output token count

**Completion Span**:
- `total_tokens`: Sum of input + output tokens
- `estimated_cost`: Calculated cost

### ModelProvider

Represents a configured AI model provider.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| provider_id | string | Yes | Unique provider identifier |
| endpoint | string | Yes | Provider API endpoint |
| credentials | dict | No | Authentication credentials |
| supported_models | list[string] | Yes | List of model IDs |
| provider_type | string | Yes | local/cloud |

**Provider Types**:
- `local`: Ollama, vLLM, SGLang
- `cloud`: OpenAI, Claude

**Validation Rules**:
- `endpoint` must be valid URL
- `credentials` must include required fields for provider type

### Document

Represents a document in the knowledge base.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| doc_id | string | Yes | Unique document identifier |
| title | string | Yes | Document title |
| content | string | Yes | Full document content |
| source | string | No | Source of document |
| metadata | dict | No | Additional metadata |
| created_at | datetime | Yes | Creation timestamp |
| updated_at | datetime | Yes | Last update timestamp |

**Validation Rules**:
- `content` must not be empty
- `title` must not be empty

### MilvusChunk

Represents a vector chunk stored in Milvus.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| chunk_id | string | Yes | Unique chunk identifier |
| vector | list[float] | Yes | Embedding vector |
| text | string | Yes | Chunk text content |
| doc_id | string | Yes | Source document ID |
| index_fields | dict | No | Additional indexed fields |

**Milvus Collection Schema**:
- Field: `chunk_id` (VARCHAR, primary key)
- Field: `vector` (FLOAT_VECTOR, dim=1536)
- Field: `text` (VARCHAR)
- Field: `doc_id` (VARCHAR)
- Index: IVF_FLAT or HNSW on vector field

## Entity Relationships

```
QueryRequest (1) ──────▶ (1) QueryResponse
       │                       │
       │                       │───▶ (1..n) RetrievedChunk
       │
       └───▶ (0..1) ModelProvider

TraceRecord (1) ──────▶ (1..n) TraceSpan
       │
       └───▶ (1) QueryResponse

Document (1) ──────▶ (1..n) MilvusChunk
```

## State Machines

### QueryRequest Lifecycle

```
┌──────────┐   validate   ┌──────────┐   process   ┌───────────┐
│ Received │─────────────▶│ Validated│────────────▶│ Processing│
└──────────┘              └──────────┘             └───────────┘
                                                           │
                                                           ▼
                                                    ┌─────────────┐
                                                    │ Completed   │
                                                    └─────────────┘
```

### TraceRecord Lifecycle

```
┌──────────┐   created   ┌──────────┐   add span   ┌──────────┐
│ Created  │────────────▶│ Active   │─────────────▶│ Updating │
└──────────┘             └──────────┘               └──────────┘
                                                           │
                                                           ▼
                                                    ┌─────────────┐
                                                    │ Completed   │
                                                    └─────────────┘
```

## Validation Summary

| Entity | Key Validations | Error Handling |
|--------|-----------------|----------------|
| QueryRequest | Non-empty question, valid model hint | Return 400 Bad Request |
| ModelProvider | Valid URL, required credentials | Reject at startup |
| TraceRecord | Valid UUID, required fields | Log and continue (non-blocking) |
| RetrievedChunk | Score 0-1, non-empty content | Filter from results |

## Storage Mapping

| Entity | Storage | Index Strategy |
|--------|---------|----------------|
| QueryRequest | In-memory (request) | N/A |
| QueryResponse | HTTP response | N/A |
| RetrievedChunk | Milvus | Vector index on embedding |
| TraceRecord | Langfuse | Trace ID |
| ModelProvider | Config file | N/A |
| Document | Milvus + metadata store | Chunk ID |
| MilvusChunk | Milvus | Vector + chunk_id |
