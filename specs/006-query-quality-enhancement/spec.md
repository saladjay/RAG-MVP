# Feature Specification: Query Quality Enhancement Module

**Feature Branch**: `006-query-quality-enhancement`
**Created**: 2026-04-09
**Status**: Draft
**Input**: User description: "目前的rag-service缺少一个query改写，我需要在前面新增一个query（llm模块）判断输入的query是否符合文档检索的query维度，你可以读取文档路径获得公文检索的所需的必要维度和建议维度。当用户输入query时，通过query改写模块进行改写或者判断让用户新增信息，通过这样提高query质量，从而提高检索成功率"

## Clarifications

### Session 2026-04-09

- Q: Multi-turn conversation session timeout duration? → A: 15 minutes with 10-turn limit per session
- Q: System availability target? → A: 99.5% (standard enterprise application, single-instance with simple failure recovery)
- Q: Observability requirements? → A: Full tracing (structured JSON logging + trace_id propagation + Langfuse integration)
- Q: Session state storage mechanism? → A: Redis for fast access with automatic TTL expiration

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Query Dimension Analysis (Priority: P1)

A user submits a search query for official documents. The system analyzes the query against the required and suggested dimensions for document retrieval (document type, organization, year/number, subject matter). If the query lacks essential dimensions, the system prompts the user to provide the missing information before proceeding with the search.

**Why this priority**: This is the foundation of the feature - without proper dimension analysis, subsequent query improvements cannot be effective. Ensuring users provide sufficient context directly improves retrieval success rates.

**Independent Test**: Can be fully tested by submitting various query types (complete vs. incomplete) and verifying that the system correctly identifies missing dimensions and prompts appropriately.

**Acceptance Scenarios**:

1. **Given** a user submits "关于安全管理的通知" (about safety management notifications), **When** the system analyzes the query, **Then** it should identify missing year dimension and prompt "请问您需要查找哪一年的安全管理通知？"
2. **Given** a user submits "2024年的工会文件" (union documents from 2024), **When** the system analyzes the query, **Then** it should identify missing subject dimension and prompt "请问您需要查找工会方面的什么内容？"
3. **Given** a user submits "关于印发《安全生产管理办法》的通知——粤东科〔2024〕33号" (complete document reference), **When** the system analyzes the query, **Then** it should recognize all dimensions are present and proceed with search

---

### User Story 2 - Query Dimension Completion (Priority: P1)

After the system identifies missing dimensions, the user provides the additional information. The system incorporates this information into an enhanced query that includes all necessary dimensions for optimal document retrieval.

**Why this priority**: This completes the user interaction loop for dimension gathering, ensuring that users can easily provide the information needed for successful retrieval.

**Independent Test**: Can be tested by providing the requested information after a dimension prompt and verifying that the enhanced query includes all provided dimensions.

**Acceptance Scenarios**:

1. **Given** the system prompts for year dimension, **When** the user responds "2024年", **Then** the enhanced query should include "2024年" context
2. **Given** the system prompts for organization dimension, **When** the user responds "党总支", **Then** the enhanced query should include organization context "粤东科党总支"
3. **Given** the system prompts for multiple dimensions, **When** the user provides all requested information, **Then** the enhanced query should incorporate all dimensions in the appropriate format

---

### User Story 3 - Automatic Query Enrichment (Priority: P2)

When a user submits a query that contains partial dimensions, the system automatically enriches the query by inferring reasonable defaults or adding contextual information without requiring user input. For example, if no year is specified and the current year is 2024, the system may add "2024年" context to prioritize recent documents.

**Why this priority**: This improves user experience by reducing the number of prompts while still improving query quality. It's lower priority than explicit user confirmation but provides significant UX benefits.

**Independent Test**: Can be tested by submitting queries with partial dimensions and verifying that the system appropriately enriches them with inferred context.

**Acceptance Scenarios**:

1. **Given** a user submits "关于安全生产的通知" without specifying year, **When** the current year is 2024, **Then** the system should enrich the query to prioritize 2024 documents while still searching other years
2. **Given** a user submits "工会管理办法" without specifying document type, **When** the system processes the query, **Then** it should add context about "办法" (regulation) document type
3. **Given** a user submits a query about general company matters, **When** no organization is specified, **Then** the system should add context for the main company organization "粤东科"

---

### User Story 4 - Query Quality Feedback (Priority: P2)

After a search is completed, the system provides feedback to the user about the query quality and how it affected the search results. This includes information about which dimensions were present, which were missing, and suggestions for improving future queries.

**Why this priority**: This educates users about how to formulate better queries over time, leading to improved search success rates and user satisfaction.

**Independent Test**: Can be tested by performing searches and verifying that appropriate quality feedback is displayed with results.

**Acceptance Scenarios**:

1. **Given** a user completes a search with a high-quality query, **When** results are displayed, **Then** the system should indicate "您的查询非常完整，包含了所有关键维度"
2. **Given** a user completes a search with a low-quality query, **When** results are displayed, **Then** the system should indicate "您的查询缺少以下维度：[年份]，建议添加年份以获得更精确的结果"
3. **Given** a user completes a search with partial dimensions, **When** results are displayed, **Then** the system should show which dimensions were used and which could improve the search

---

### Edge Cases

- What happens when a user provides inconsistent or conflicting information (e.g., year 2023 in the query but manually says 2024 when prompted)?
- How does the system handle queries in completely different formats or structures than expected?
- What happens when a user refuses to provide requested dimension information?
- How does the system handle queries that reference specific document numbers but contain typos?
- What happens when the LLM cannot determine whether a dimension is present or missing?
- How does the system handle queries that are too short or too long?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST analyze user queries against the required document dimensions (document type, organization, year/number, subject matter)
- **FR-002**: System MUST identify which required dimensions are missing from the user's query
- **FR-003**: System MUST prompt users to provide missing critical dimensions before proceeding with search
- **FR-004**: System MUST support the following document dimensions:
  - **Company ID** (公司标识): Provided by external system, used to identify the company context
  - **File Category** (文件类别): PublicDocDispatch (发文/outgoing documents), PublicDocReceive (收文/incoming documents)
  - **Document Type** (公文类型): 通知、通报、报告、请示、纪要、公示、方案、办法、细则、规则、规划、要点
  - **Organization** (发文单位): 粤东科、粤东科党总支、粤东科工会、各党支部
  - **Year/Number** (年份文号): Year (2024, 2023, etc.) and document number format 〔2024〕XX号
  - **Subject/Content** (主题内容): 党建相关、人事相关、安全生产、行政管理、制度建设等
- **FR-004A**: When file category (发文/收文) cannot be determined from the query, system MUST search both knowledge bases simultaneously to ensure comprehensive results
- **FR-005**: System MUST incorporate user-provided dimension information into enhanced queries
- **FR-006**: System MUST automatically enrich queries with reasonable defaults when appropriate (e.g., current year when not specified)
- **FR-007**: System MUST provide query quality feedback after search completion
- **FR-008**: System MUST handle user refusal to provide optional dimensions without blocking the search
- **FR-009**: System MUST validate that dimension information provided by users is in the correct format
- **FR-010**: System MUST maintain a conversation context to track multiple dimension prompts and user responses
- **FR-011**: System MUST enforce a session timeout of 15 minutes of inactivity
- **FR-012**: System MUST enforce a maximum of 10 conversation turns per session, after which users are prompted to summarize or start a new session
- **FR-013**: System MUST store session state in Redis with automatic TTL expiration
- **FR-014**: System MUST propagate trace_id across all service calls for end-to-end request tracking
- **FR-015**: System MUST emit structured JSON logs for all operations

### Key Entities

- **Query Dimension Analysis**: Represents the analysis of a user query against required dimensions, including which dimensions are present, missing, or need clarification

- **Dimension Prompt**: Represents a request to the user for specific missing dimension information, including the dimension type, format requirements, and example values

- **Enhanced Query**: Represents the final query after dimension completion and enrichment, containing all available dimension information

- **Query Quality Score**: Represents a quantitative assessment of query completeness based on the number and importance of dimensions present

- **Knowledge Base Route**: Represents the target knowledge base determined from company_id and file_type:
  - Format: `{company_id}_{file_type}` (e.g., `N000002_PublicDocDispatch` for company N000002's outgoing documents)
  - PublicDocDispatch: 发文 knowledge base
  - PublicDocReceive: 收文 knowledge base

## Non-Functional Requirements

### Performance
- Query processing time remains under 3 seconds including dimension analysis and any necessary prompts (measured at p95)

### Reliability
- System availability target: 99.5% (approximately 3.6 hours of downtime per month)
- Single-instance deployment with simple failure recovery mechanism

### Observability
- Structured JSON logging for all operations
- Trace ID propagation across all service calls (consistent with existing architecture using Langfuse)
- Session state stored in Redis with TTL-based expiration

### Scalability
- Session state managed via Redis to support potential future horizontal scaling
- Maximum 10 conversation turns per session to prevent resource exhaustion

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Query completeness rate increases by 40% (measured by the percentage of queries that include all key dimensions after the enhancement process)
- **SC-002**: Document retrieval success rate improves by 30% (measured by the percentage of searches that return relevant results)
- **SC-003**: Average number of user prompts per search decreases by 50% over time as users learn to provide better queries (measured over a 30-day period)
- **SC-004**: 90% of users report satisfaction with query guidance (measured through user feedback surveys)
- **SC-005**: Query processing time remains under 3 seconds including dimension analysis and any necessary prompts (measured at p95)
- **SC-006**: 80% of searches with complete dimension queries return the correct document in the top 3 results
- **SC-007**: User search refinement rate decreases by 35% (measured by the percentage of searches that require subsequent refinement queries)

## Assumptions

- Users are primarily searching for Chinese official documents in the established format
- The document naming convention follows the pattern analyzed from the 2024 document directory
- Users have basic knowledge of the document types and organizations but may not remember all details
- The LLM can accurately analyze Chinese queries and identify dimension presence/absence
- Users are willing to provide additional information when prompted if it improves their search results
- The current query rewrite capability (feature 005) remains in place and works in conjunction with this enhancement

## Dependencies

- Feature 005 (RAG QA Pipeline) must be completed as this enhancement builds upon the existing query infrastructure
- LiteLLM gateway for LLM access (from feature 001)
- Prompt Service for query analysis templates (from feature 003)

## Out of Scope

- Multi-language support (assumes Chinese queries only)
- Document content analysis (focuses on query dimensions, not document content)
- Automatic document indexing or tagging (assumes documents are already properly indexed)
- User account management or personalization (query enhancement applies to all users equally)
- Historical query analysis or learning from user behavior over time
