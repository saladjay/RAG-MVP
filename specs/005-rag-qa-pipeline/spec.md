# Feature Specification: RAG QA Pipeline

**Feature Branch**: `005-rag-qa-pipeline`
**Created**: 2026-04-01
**Status**: Draft
**Input**: User description: "我需要一个新的spec，在原有的基础上构建一个接受query，进行query改写，调用外部知识库，根据检索内容生成答案，最后返回结果的rag"

**Updates**:
- 外部知识库返回异常或者空，试用默认术语返回
- 新增一个幻觉检测环节在大模型generation后，对比生成答案和retrievals
- 暂时不考虑跨多个文档
- 暂时不考虑超过上下文
- 暂时不考虑同一个用户并发

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Basic QA with External Knowledge (Priority: P1)

A user submits a natural language question about a company document or policy. The system retrieves relevant content from the external knowledge base and generates a comprehensive answer based on the retrieved information.

**Why this priority**: This is the core value proposition - users need accurate answers based on their enterprise documents. Without this, there is no product.

**Independent Test**: Can be fully tested by submitting a query and verifying the answer is based on retrieved content from the external KB. Delivers immediate value by providing document-based answers.

**Acceptance Scenarios**:

1. **Given** a user submits a question about company policy, **When** the question is submitted, **Then** the system retrieves relevant documents and returns an answer that cites the sources
2. **Given** the external knowledge base returns empty results or an error, **When** a query is submitted, **Then** the system responds with a default fallback message using predefined terminology
3. **Given** a query returns no relevant documents, **When** the search completes, **Then** the system responds with a default message indicating no specific information was found in the knowledge base

---

### User Story 2 - Query Rewriting for Improved Retrieval (Priority: P2)

A user submits an ambiguous or poorly phrased question. The system analyzes and rewrites the query to improve retrieval accuracy, then fetches relevant content and generates an answer.

**Why this priority**: Query rewriting significantly improves answer quality but requires additional LLM calls. It's valuable but not required for basic functionality.

**Independent Test**: Can be tested by submitting ambiguous queries and verifying the rewritten version yields better results than the original. Delivers value through improved answer relevance.

**Acceptance Scenarios**:

1. **Given** a user submits a vague question like "holiday schedule", **When** processed, **Then** the system rewrites it to include context like "2025 company holiday schedule" and retrieves more relevant results
2. **Given** a user uses colloquial language, **When** the query is rewritten, **Then** formal terminology is used for retrieval while the answer uses user-friendly language
3. **Given** query rewriting fails, **When** an error occurs, **Then** the system falls back to using the original query for retrieval

---

### User Story 3 - Hallucination Detection (Priority: P1)

After generating an answer, the system verifies that the response is based on the retrieved content rather than fabricated information. This protects users from incorrect or misleading answers.

**Why this priority**: Critical for trust and safety. Hallucinations can provide incorrect information that may mislead users. This is a core quality requirement.

**Independent Test**: Can be tested by submitting queries and deliberately checking if answers contain information not present in retrieved content. System should flag or reject hallucinated answers.

**Acceptance Scenarios**:

1. **Given** an answer is generated, **When** the content is compared to retrieved documents, **Then** the system verifies all factual claims are supported by the retrieval results
2. **Given** the generated answer contains information not found in retrieved content, **When** hallucination is detected, **Then** the system either regenerates the answer with stricter constraints or returns a response indicating uncertainty
3. **Given** hallucination detection fails or times out, **When** the check cannot complete, **Then** the system logs the incident and returns the answer with a warning that verification was not performed

---

### User Story 4 - Streaming Response for Real-time Feedback (Priority: P3)

A user submits a complex question that requires a detailed answer. The system streams the response token-by-token so the user sees the answer being generated in real-time, reducing perceived wait time.

**Why this priority**: Improves user experience for long responses but doesn't affect answer quality. Nice-to-have for better UX.

**Independent Test**: Can be tested by submitting a query and observing tokens arrive incrementally rather than waiting for the complete response.

**Acceptance Scenarios**:

1. **Given** a user submits a complex query, **When** the answer is generated, **Then** tokens are streamed to the client as they are produced
2. **Given** a streaming response is interrupted, **When** the connection drops, **Then** the system logs the partial response for debugging
3. **Given** the client doesn't support streaming, **When** a query is submitted, **Then** the system falls back to returning the complete response

---

### Edge Cases

- What happens when the external KB returns malformed or partially incomplete content?
- How does the system handle queries in languages other than Chinese?
- What happens when hallucination detection produces false positives (flagging correct answers)?
- How does the system handle queries that are completely unrelated to the knowledge base domain?
- What happens when the query rewriting produces a semantically incorrect rewrite?
- What happens when the default terminology response is triggered frequently?

### Out of Scope (for this feature)

The following are explicitly out of scope and will be addressed in future features:

- **Cross-document synthesis**: Queries that require combining information from multiple documents are not supported. Each answer is based on a single retrieval set.
- **Context window management**: The system assumes retrieved content fits within the LLM context window. Chunking, truncation, or summarization for large contexts is not handled.
- **User concurrency**: Single-user focus only. Rate limiting, request queuing, or user session management for concurrent queries is not implemented.
- **Multi-language support**: Primary focus is Chinese queries and documents. Other languages are not optimized.
- **Conversation history**: Each query is processed independently. No context from previous queries is maintained.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept natural language queries via HTTP POST endpoint
- **FR-002**: System MUST rewrite input queries to optimize retrieval accuracy using an LLM
- **FR-003**: System MUST query the external knowledge base with the rewritten query
- **FR-004**: System MUST generate answers based on retrieved content using an LLM
- **FR-005**: System MUST include source citations in generated answers
- **FR-006**: System MUST return responses in structured format including answer, sources, and metadata
- **FR-007**: System MUST respond with default terminology when external KB returns empty results or errors
- **FR-008**: System MUST perform hallucination detection by comparing generated answers against retrieved content
- **FR-009**: System MUST regenerate or flag answers when hallucination is detected
- **FR-010**: System MUST fall back to original query if query rewriting fails
- **FR-011**: System MUST validate query input is not empty and within length limits
- **FR-012**: System MUST log all queries, retrievals, hallucination checks, and generations for observability

### Key Entities

- **Query Request**: User's original question with optional context (company ID, document type filters)
- **Rewritten Query**: Optimized query for retrieval, may include expanded terms and context
- **Retrieval Result**: Set of relevant document chunks with metadata (source, score, position)
- **Generated Answer**: LLM-produced response with inline citations to source chunks
- **Hallucination Check**: Verification result comparing answer content against retrieved sources, includes confidence score and flagged claims
- **Default Fallback Response**: Predefined response message used when KB returns empty or error results
- **QA Response**: Complete output including answer, sources list, hallucination status, timing metadata, and trace ID

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: End-to-end query processing (rewrite → retrieve → generate → verify) completes in under 10 seconds for 95% of queries
- **SC-002**: Query rewriting improves retrieval relevance (measured by chunk relevance scores) by at least 20%
- **SC-003**: Generated answers include accurate source citations in 90% of responses
- **SC-004**: 95% of users receive helpful answers based on retrieved content (measured by feedback or manual review)
- **SC-005**: Hallucination detection correctly identifies unsupported claims with 90% precision (minimizing false positives)
- **SC-006**: Default fallback responses are provided within 2 seconds when KB is unavailable or returns empty results
- **SC-007**: API has 99.5% uptime excluding external dependencies (KB, LLM)

## Assumptions

- External knowledge base endpoint is already configured (from Spec 001)
- LiteLLM gateway is available for model inference (from Spec 001)
- Query rewriting will use the same LLM as answer generation and hallucination detection
- Source documents contain Chinese text and queries will primarily be in Chinese
- Context window is sufficient for typical retrieval sizes (5-10 chunks) - overflow handling is out of scope
- Users expect real-time responses, not batch processing
- Default terminology fallback messages will be provided by the business/product team
- Hallucination detection will use similarity-based comparison between answer and retrieved content
- Single query processing only - no concurrent user session management required

## Dependencies

- **Spec 001 (RAG Service MVP)**: External KB client, LiteLLM gateway integration
- **Spec 003 (Prompt Service)**: Optional - for prompt template management for query rewriting and answer generation
- External Knowledge Base: HTTP endpoint must be accessible and return document chunks
- LiteLLM Gateway: Must support the configured models for Chinese text
