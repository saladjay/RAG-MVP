# Feature Specification: Prompt Management Service

**Feature Branch**: `003-prompt-service`
**Created**: 2026-03-20
**Status**: Draft
**Input**: User description: "langfuse不能仅仅做日志，还需要进行prompt管理，prompt在线修改，A/B测试，trace分析功能，业务代码不能直接读取langfuse, 业务代码和langfuse中间需要用一层get_prompt中转"

**Additional Input**: Structured prompt format specification with multi-stakeholder requirements:
- Prompt structure: 模板 + 变量 + 版本 + 评估 + 监控
- Recommended format: [角色], [任务], [约束], [输入], [输出格式]
- Multi-stakeholder needs: AI engineers (debuggable/traceable), backend engineers (simple interface), product managers (can optimize), testers (regression testing)
- Dynamic prompt adjustment with context and retrieved_docs integration

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Prompt Retrieval Middleware (Priority: P1)

A developer needs to fetch prompts for use in business logic without directly accessing the observability platform. The developer calls a simple interface to get the active prompt for a specific use case, and the system returns the appropriate prompt template.

**Why this priority**: This is the core abstraction - without this middleware, business code has direct dependencies on the observability platform, violating separation of concerns.

**Independent Test**: Can be tested by calling the prompt retrieval interface with a use case identifier and verifying the returned prompt content matches the expected active version.

**Acceptance Scenarios**:

1. **Given** a prompt use case has been configured, **When** business code requests the prompt via the middleware, **Then** the system returns the active prompt template
2. **Given** multiple versions of a prompt exist, **When** business code requests the prompt, **Then** the system returns only the active version
3. **Given** a requested use case does not exist, **When** business code requests the prompt, **Then** the system returns a clear error with available use cases

---

### User Story 2 - Online Prompt Editing (Priority: P1)

A product manager needs to update prompt templates without deploying code changes. The manager accesses a management interface, modifies a prompt template, and publishes the changes. The new prompt becomes active immediately for subsequent requests.

**Why this priority**: The ability to iterate on prompts without deployment is a primary value driver for prompt management systems.

**Independent Test**: Can be tested by retrieving a prompt, editing it through the management interface, then retrieving it again and verifying the new content is returned.

**Acceptance Scenarios**:

1. **Given** a prompt template exists, **When** a user edits and publishes the prompt, **Then** subsequent retrievals return the new content
2. **Given** a prompt is being edited, **When** another user edits the same prompt, **Then** the system handles concurrent edits with appropriate conflict resolution
3. **Given** an edited prompt is published, **When** a user views the prompt history, **Then** previous versions are preserved and accessible

---

### User Story 3 - A/B Testing for Prompts (Priority: P2)

A data scientist wants to compare two versions of a prompt to determine which performs better. The scientist configures an A/B test with traffic split, and the system routes requests to different prompt variants while tracking performance metrics.

**Why this priority**: A/B testing enables data-driven prompt optimization but requires additional infrastructure beyond basic prompt management.

**Independent Test**: Can be tested by creating an A/B test with two prompt variants, making multiple requests, and verifying traffic is distributed and metrics are captured for each variant.

**Acceptance Scenarios**:

1. **Given** an A/B test is configured with two prompt variants, **When** requests are made, **Then** traffic is distributed according to the configured split percentage
2. **Given** an A/B test is running, **When** results are viewed, **Then** metrics (success rate, user satisfaction, latency) are displayed for each variant
3. **Given** an A/B test is complete, **When** a winner is selected, **Then** the winning variant becomes the new active prompt and the test is archived

---

### User Story 4 - Trace Analysis and Insights (Priority: P3)

A product analyst wants to understand how prompts perform in production by analyzing trace data. The analyst views aggregate metrics, identifies patterns in failures, and discovers opportunities for prompt improvement.

**Why this priority**: Trace analysis provides insights for prompt optimization but is a secondary concern compared to prompt delivery and testing.

**Independent Test**: Can be tested by executing prompts with known outcomes, then viewing the trace analysis dashboard and verifying metrics and patterns are correctly displayed.

**Acceptance Scenarios**:

1. **Given** prompts have been executed, **When** viewing trace analysis, **Then** aggregate metrics (usage count, error rate, latency percentiles) are displayed
2. **Given** a prompt has failures, **When** viewing trace analysis, **Then** common failure patterns and contributing factors are highlighted
3. **Given** an A/B test has completed, **When** viewing trace analysis, **Then** comparative performance between variants is visualized

---

### User Story 5 - Prompt Versioning and Rollback (Priority: P4)

A developer accidentally publishes a problematic prompt and needs to quickly revert to the previous version. The developer accesses the version history and restores the previous prompt, which immediately becomes active.

**Why this priority**: Versioning and rollback are important safety features but are not required for initial prompt management functionality.

**Independent Test**: Can be tested by creating multiple prompt versions, then rolling back to a previous version and verifying the old content is returned.

**Acceptance Scenarios**:

1. **Given** a prompt has multiple versions, **When** a user views version history, **Then** all versions are displayed with timestamps and authors
2. **Given** an active prompt needs to be reverted, **When** a user restores a previous version, **Then** that version becomes immediately active
3. **Given** a version has been restored, **When** viewing the audit log, **Then** the rollback action is recorded with user and timestamp

---

### Edge Cases

- What happens when the middleware cannot connect to the underlying observability platform?
- How does the system handle prompts with variable interpolation when variables are missing?
- What happens when an A/B test is configured but one variant has insufficient data?
- How does the system handle concurrent edits to the same prompt template?
- What happens when a prompt template exceeds size limits?
- How does the system handle special characters or encoding issues in prompt content?
- What happens when a user without permissions attempts to edit or publish prompts?
- How does the system behave when a prompt is deleted while actively being used?

---

### Stakeholder Requirements

The prompt management system serves multiple user roles with distinct needs:

| Role | Needs | Interface Requirements |
|------|-------|----------------------|
| **AI Engineers** | Debuggable and traceable prompts | Detailed prompt version history, change tracking, trace-to-prompt linking |
| **Backend Engineers** | Simple interface, abstraction from details | Single function call, no need to understand prompt structure |
| **Product Managers** | Participate in prompt optimization | User-friendly editor, preview functionality, performance metrics |
| **Testers** | Regression testing support | Prompt version pinning, test data fixtures, baseline comparisons |

---

### Prompt Structure Specification

The system supports structured prompt templates with the following components:

#### Core Components

1. **模板 (Template)**: The base prompt structure with sections for role, task, constraints, and output format
2. **变量 (Variables)**: Dynamic placeholders that are replaced at runtime (e.g., user input, retrieved documents)
3. **版本 (Version)**: Version identifier for tracking changes and enabling rollback
4. **评估 (Evaluation)**: Metrics and criteria for measuring prompt performance
5. **监控 (Monitoring)**: Real-time tracking of prompt execution and outcomes

#### Recommended Structure Format

```
[角色]
{role_definition}

[任务]
{task_description}

[约束]
- {constraint_1}
- {constraint_2}
- ...

[输入]
{input_variable_1}: {value_1}
{input_variable_2}: {value_2}
...

[输出格式]
{output_format_specification}
```

#### Example: Financial Analysis Prompt

```
[角色]
你是一个金融分析专家

[任务]
分析用户输入

[约束]
- 必须基于数据
- 不允许编造

[输入]
{input}

[输出格式]
JSON
```

#### Dynamic Context Integration

The system must support dynamic adjustment of prompts by combining:

1. **Base Template**: The structured prompt template defined above
2. **Context**: Additional runtime context (user session, conversation history)
3. **Retrieved Documents**: Relevant chunks from the knowledge base

The final rendered prompt combines these elements in a structured way:

```
[Final Prompt] = [Base Template] + [Context Section] + [Retrieved Docs Section]
```

Where:
- `[Base Template]`: The structured template with role, task, constraints
- `[Context Section]`: Dynamic context inserted at runtime
- `[Retrieved Docs Section]`: Retrieved knowledge chunks formatted for inclusion

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a prompt retrieval interface (`get_prompt`) that business code calls to obtain prompt templates
- **FR-002**: System MUST decouple business code from the underlying observability platform (no direct access)
- **FR-003**: System MUST support online editing of prompt templates without requiring code deployment
- **FR-004**: System MUST support A/B testing with configurable traffic split between prompt variants
- **FR-005**: System MUST capture and analyze trace data for prompt performance evaluation
- **FR-006**: System MUST maintain version history for all prompt changes
- **FR-007**: System MUST support rollback to previous prompt versions
- **FR-008**: System MUST provide a management interface for prompt editing and configuration
- **FR-009**: System MUST track metrics for A/B test variants (usage, success rate, performance)
- **FR-010**: System MUST support variable interpolation in prompt templates
- **FR-011**: System MUST validate prompt content before publishing
- **FR-012**: System MUST maintain audit logs for all prompt modifications
- **FR-013**: System MUST support structured prompt format with sections: [角色], [任务], [约束], [输入], [输出格式]
- **FR-014**: System MUST allow multiple prompt structures (flexible section configuration)
- **FR-015**: System MUST support dynamic prompt adjustment by combining: template + context + retrieved_documents
- **FR-016**: System MUST provide debug interface for AI engineers to trace prompt-to-output relationships
- **FR-017**: System MUST support prompt version pinning for regression testing
- **FR-018**: System MUST link each trace to the specific prompt version and variables used

### Key Entities

- **Prompt Template**: A reusable prompt definition containing: template ID, version, structured sections ([角色], [任务], [约束], [输入], [输出格式]), variable placeholders, metadata
- **Structured Section**: A labeled component of a prompt template (e.g., [角色], [任务], [约束], [输入], [输出格式]) with associated content
- **Prompt Variant**: A specific version of a prompt template used in A/B testing
- **A/B Test**: A configuration comparing two or more prompt variants with: test ID, variants, traffic split, success criteria, status
- **Trace Record**: Execution data linking prompt usage to: prompt version, input variables, context, retrieved_documents, model response, performance metrics, user feedback
- **Prompt Retrieval Request**: A business code request containing: template ID, variable values, context, retrieved_documents (optional)
- **Prompt Retrieval Response**: The middleware response containing: rendered prompt content (template + context + retrieved_docs), variant ID (if A/B test), version metadata
- **Version History**: Chronological record of prompt changes with: version number, timestamp, author, change description, content diff
- **Evaluation Metrics**: Quantitative measures for prompt performance: success rate, output quality score, latency, user satisfaction
- **Monitoring Data**: Real-time tracking of prompt execution: request count, error rate, A/B test assignment, resource usage

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Business code retrieves prompts through middleware without any direct dependency on observability platform
- **SC-002**: Prompt changes published through management interface become active within 5 seconds
- **SC-003**: A/B tests distribute traffic according to configured split with ±5% accuracy
- **SC-004**: Trace data is captured and available for analysis within 30 seconds of prompt execution
- **SC-005**: Prompt rollbacks restore previous version and make it active within 5 seconds
- **SC-006**: Management interface displays prompt metrics with less than 3-second page load time
- **SC-007**: Variable interpolation renders prompts correctly with 100% accuracy for valid inputs
- **SC-008**: AI engineers can trace any output back to the exact prompt version and variables used
- **SC-009**: Backend engineers can retrieve prompts using a single function call without understanding prompt structure
- **SC-010**: Product managers can edit and preview prompts through a user-friendly interface
- **SC-011**: Testers can pin specific prompt versions for regression testing
- **SC-012**: Dynamic prompt assembly (template + context + retrieved_docs) completes within 100ms

## Assumptions

1. **Observability platform integration**: An underlying observability platform (such as Langfuse) is available for storing prompts and traces
2. **User authentication**: The management interface has access to user identity for audit logging
3. **Variable schema**: Prompt templates use a predefined variable syntax (e.g., `{{variable_name}}`) that business code agrees upon
4. **Traffic for A/B tests**: Sufficient request volume exists to achieve statistical significance in A/B tests
5. **Prompt complexity**: Prompts are text-based templates without complex logic or conditional rendering
6. **Real-time requirements**: Prompt changes should propagate quickly but eventual consistency is acceptable

## Out of Scope

The following features are explicitly out of scope for this feature:

- Automatic prompt optimization or AI-generated suggestions
- Multi-language or internationalization support in prompt templates
- Complex conditional logic or branching within prompt templates
- Prompt sharing across different organizations or teams
- Built-in evaluation metrics or automated scoring
- Integration with external A/B testing platforms
- Real-time collaboration features (multiple users editing simultaneously)

## Architecture Overview

The prompt management service introduces a middleware layer between business code and the observability platform:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Prompt Management Architecture                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐                                                            │
│  │ Business    │  Calls: get_prompt(template_id, variables, context,       │
│  │ Code        │              retrieved_docs)                               │
│  └─────────────┘──────────────┘                                              │
│                                │                                              │
│                                ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    Prompt Middleware Layer                          │    │
│  │                                                                     │    │
│  │  ┌──────────────────────────────────────────────────────────────┐   │    │
│  │  │  Dynamic Prompt Assembly                                     │   │    │
│  │  │    ┌─────────────────────────────────────────────────────┐   │   │    │
│  │  │    │ 1. Retrieve base template (structured sections)     │   │   │    │
│  │  │    │ 2. Check for active A/B tests → select variant       │   │   │    │
│  │  │    │ 3. Inject context section                            │   │   │    │
│  │  │    │ 4. Format retrieved_docs section                     │   │   │    │
│  │  │    │ 5. Perform variable interpolation                    │   │   │    │
│  │  │    │ 6. Return assembled prompt + version metadata        │   │   │    │
│  │  │    └─────────────────────────────────────────────────────┘   │   │    │
│  │  └──────────────────────────────────────────────────────────────┘   │    │
│  │                                                                     │    │
│  │  ┌──────────────────────────────────────────────────────────────┐   │    │
│  │  │  Stakeholder Interfaces                                     │   │    │
│  │  │  - AI Engineers: Debug UI with trace-to-prompt linking       │   │    │
│  │  │  - Backend Engineers: Simple get_prompt() function          │   │    │
│  │  │  - Product Managers: Visual prompt editor with preview      │   │    │
│  │  │  - Testers: Version pinning interface for regressions       │   │    │
│  │  └──────────────────────────────────────────────────────────────┘   │    │
│  │                                                                     │    │
│  │  ┌──────────────────────────────────────────────────────────────┐   │    │
│  │  │  Management API - Edit, publish, A/B test configuration      │   │    │
│  │  └──────────────────────────────────────────────────────────────┘   │    │
│  │                                                                     │    │
│  │  ┌──────────────────────────────────────────────────────────────┐   │    │
│  │  │  Analysis Service - Trace aggregation and insights           │   │    │
│  │  └──────────────────────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                │                                              │
│                                ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                  Observability Platform (e.g., Langfuse)            │    │
│  │  - Prompt template storage and versioning                          │    │
│  │  - Structured section storage                                       │    │
│  │  - Trace data storage (linked to prompt versions)                  │    │
│  │  - A/B test configuration and metrics                               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Dynamic Prompt Assembly Flow

```
Request: get_prompt(template_id, variables, context, retrieved_docs)
                        │
                        ▼
            ┌───────────────────────────┐
            │ 1. Load Template         │
            │    - Get active version   │
            │    - Check A/B tests      │
            └───────────┬───────────────┘
                        │
                        ▼
            ┌───────────────────────────┐
            │ 2. Assemble Sections     │
            │    - [角色] (fixed)       │
            │    - [任务] (fixed)       │
            │    - [约束] (fixed)       │
            │    - [输入] + variables   │
            │    - [输出格式] (fixed)   │
            │    - + [Context Section]  │
            │    - + [Retrieved Docs]   │
            └───────────┬───────────────┘
                        │
                        ▼
            ┌───────────────────────────┐
            │ 3. Interpolate Variables │
            │    - Replace {input}     │
            │    - Replace {context}   │
            │    - Insert retrieved    │
            └───────────┬───────────────┘
                        │
                        ▼
            ┌───────────────────────────┐
            │ 4. Return Response       │
            │    {                     │
            │      rendered_prompt,    │
            │      version_id,         │
            │      variant_id?,        │
            │      metadata            │
            │    }                     │
            └───────────────────────────┘
```

### Key Design Principles

1. **Separation of Concerns**: Business code should not know about the observability platform implementation
2. **Interface Stability**: The `get_prompt` interface remains stable even if the underlying platform changes
3. **Performance**: Prompt retrieval should add minimal latency (<50ms) to request processing
4. **Reliability**: Middleware should gracefully handle observability platform failures
5. **Observability**: All prompt retrievals and A/B test assignments are themselves traced
