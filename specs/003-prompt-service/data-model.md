# Data Model: Prompt Management Service

**Feature**: 003-prompt-service | **Date**: 2026-03-23
**Status**: Phase 1 - Entity Definitions

## Overview

This document defines all entities in the Prompt Management Service, their relationships, validation rules, and state transitions.

---

## Entity Definitions

### 1. PromptTemplate

The core entity representing a reusable prompt definition with structured sections.

```python
@dataclass
class PromptTemplate:
    """A reusable prompt definition with structured sections.

    Stored in: Langfuse prompt management
    Access via: template_id (unique identifier)
    """

    # Identity
    template_id: str              # Unique identifier (e.g., "financial_analysis")
    name: str                     # Human-readable name
    description: str              # Purpose and usage notes
    version: int                  # Monotonically increasing version number
    created_at: datetime          # Creation timestamp
    updated_at: datetime          # Last modification timestamp
    created_by: str               # User who created the prompt
    tags: List[str]               # For categorization and filtering

    # Content
    sections: List[StructuredSection]  # Ordered prompt sections
    variables: Dict[str, VariableDef]  # Variable definitions

    # Status
    is_active: bool               # Whether this version is the active one
    is_published: bool            # Whether published (visible to retrieval)

    # Metadata
    metadata: Dict[str, Any]      # Custom metadata
```

**Validation Rules**:
- `template_id` must match pattern `^[a-z][a-z0-9_]*$` (2-50 chars)
- `name` cannot be empty, max 200 chars
- `version` starts at 1, increments on each change
- At minimum, must have sections: [角色], [任务], [约束], [输出格式]
- `is_active` can only be True for one version per template_id

**State Transitions**:
```
[DRAFT] → [PUBLISHED] → [ACTIVE] → [SUPERSEDED]
   │          │            │              │
   └──────────┴────────────┴──────────────┘
        (can rollback to any previous version)
```

---

### 2. StructuredSection

A labeled component of a prompt template.

```python
@dataclass
class StructuredSection:
    """A labeled component of a prompt template.

    Sections are assembled in order to create the final prompt.
    """

    name: str                     # Section label (e.g., "角色", "任务")
    content: str                  # Section content template
    is_required: bool = True      # Whether section must have content
    order: int = 0                # Display/assembly order
    variables: List[str] = field(default_factory=list)  # Variables used in content

    # Rendering options
    render_if_empty: bool = False  # Whether to render section if content is empty
    separator_before: str = ""     # Content to insert before section
    separator_after: str = ""      # Content to insert after section
```

**Standard Sections**:
| Name | Required | Description |
|------|----------|-------------|
| 角色 | Yes | AI role definition |
| 任务 | Yes | Task description |
| 约束 | Yes | Constraints and rules |
| 输入 | Yes | Input variables (dynamically populated) |
| 输出格式 | Yes | Expected output format |

**Dynamic Sections** (added at runtime):
| Name | Added By | Description |
|------|----------|-------------|
| 上下文 | Service | Conversation history, session data |
| 检索文档 | Service | Retrieved chunks from knowledge base |

**Validation Rules**:
- `name` cannot be empty, max 50 chars
- Standard sections cannot be deleted
- Duplicate `name` values not allowed within a template
- `order` must be unique within a template

---

### 3. VariableDef

Definition of a variable used in prompt templates.

```python
@dataclass
class VariableDef:
    """Definition of a template variable.

    Variables are interpolated during prompt assembly.
    """

    name: str                     # Variable name (e.g., "user_input")
    description: str              # What this variable represents
    type: VariableType            # STRING, NUMBER, LIST, DICT
    default_value: Any = None     # Default if not provided
    is_required: bool = True      # Whether value must be provided
    validation: Optional[str] = None  # Validation regex or rule

    # For nested structures
    schema: Optional[Dict[str, Any]] = None  # Schema for complex types
```

**Variable Types**:
```python
class VariableType(Enum):
    STRING = "string"
    NUMBER = "number"
    LIST = "list"
    DICT = "dict"
    BOOLEAN = "boolean"
```

**Validation Rules**:
- `name` must match `^[a-z][a-z0-9_]*$`
- Required variables must have values provided at retrieval time
- Type coercion attempted for mismatched types
- Validation regex applied if provided

---

### 4. PromptVariant

A specific version of a prompt used in A/B testing.

```python
@dataclass
class PromptVariant:
    """A variant of a prompt template for A/B testing.

    References a specific version of a PromptTemplate.
    """

    variant_id: str               # Unique variant ID (e.g., "variant_a")
    test_id: str                  # Parent A/B test ID
    template_id: str              # Source template ID
    template_version: int         # Specific version to use

    # Configuration
    traffic_percentage: float     # Traffic to receive (0-100)
    is_control: bool = False      # Whether this is the control (baseline)

    # Metrics
    impressions: int = 0          # Number of times shown
    successes: int = 0            # Number of successful outcomes
    total_latency_ms: float = 0   # Cumulative latency for averaging

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
```

**Validation Rules**:
- `variant_id` must be unique within a test
- `traffic_percentage` for all variants in a test must sum to 100
- At least one variant must be marked as `is_control = True`

---

### 5. ABTest

Configuration for comparing two or more prompt variants.

```python
@dataclass
class ABTest:
    """A/B test configuration for comparing prompt variants.

    Routes traffic to different variants and tracks performance.
    """

    test_id: str                  # Unique test ID
    template_id: str              # Prompt being tested
    name: str                     # Human-readable name
    description: str              # Test hypothesis and goals

    # Configuration
    variants: List[PromptVariant] # Competing variants
    status: ABTestStatus          # RUNNING, PAUSED, COMPLETED

    # Success criteria
    success_metric: str           # Metric to optimize (success_rate, latency)
    min_sample_size: int          # Minimum samples per variant for significance
    target_improvement: float = 0.05  # Target improvement (5%)

    # Timestamps
    created_at: datetime
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    winner_variant_id: Optional[str] = None

    # Results
    results: Dict[str, Any] = field(default_factory=dict)
```

**ABTestStatus**:
```python
class ABTestStatus(Enum):
    DRAFT = "draft"           # Configured, not started
    RUNNING = "running"       # Active, routing traffic
    PAUSED = "paused"         # Temporarily stopped
    COMPLETED = "completed"   # Finished, winner selected
    ARCHIVED = "archived"     # No longer relevant
```

**State Transitions**:
```
[DRAFT] → [RUNNING] → [PAUSED] → [RUNNING]
   │          │           │
   └──────────┴───────────→ [COMPLETED] → [ARCHIVED]
```

**Validation Rules**:
- Must have 2-5 variants
- All variant traffic percentages must sum to 100
- Exactly one variant should be marked as control
- `winner_variant_id` must match one of the variant IDs

---

### 6. TraceRecord

Execution data linking prompt usage to outcomes.

```python
@dataclass
class TraceRecord:
    """A single prompt execution trace.

    Links prompt version to input, output, and metrics.
    """

    trace_id: str                # Unique trace identifier
    template_id: str             # Prompt template used
    template_version: int        # Specific version
    variant_id: Optional[str] = None  # Variant if A/B test

    # Request
    input_variables: Dict[str, Any]    # Variables provided
    context: Dict[str, Any] = field(default_factory=dict)
    retrieved_docs: List[Dict] = field(default_factory=list)

    # Response
    rendered_prompt: str        # Final assembled prompt
    model_output: Optional[str] = None  # LLM response (if provided)
    output_metadata: Dict[str, Any] = field(default_factory=dict)

    # Metrics
    latency_ms: float = 0       # Prompt retrieval latency
    total_latency_ms: float = 0  # End-to-end latency (if available)
    success: bool = True        # Whether outcome was successful

    # Feedback
    user_feedback: Optional[str] = None
    user_rating: Optional[int] = None  # 1-5 scale

    # Timestamps
    timestamp: datetime = field(default_factory=datetime.utcnow)
```

**Validation Rules**:
- `trace_id` must be unique (generated as UUID)
- `template_version` must reference an existing version
- If `variant_id` is provided, must match an active A/B test variant

---

### 7. VersionHistory

Chronological record of prompt changes.

```python
@dataclass
class VersionHistory:
    """A single version in a prompt's history.

    Tracks who changed what and when.
    """

    template_id: str             # Parent template
    version: int                 # Version number
    change_description: str      # Human-readable change summary
    changed_by: str              # User who made the change

    # Content snapshot
    content_snapshot: Dict[str, Any]  # Full prompt state at this version

    # Diff from previous version
    diff: Optional[str] = None   # Unified diff format

    # Timestamps
    created_at: datetime

    # Rollback info
    can_rollback: bool = True    # Whether this version can be restored
    rollback_count: int = 0      # Number of times rolled back to this
```

**Validation Rules**:
- `version` numbers are monotonically increasing
- `change_description` cannot be empty
- Only published versions appear in history

---

## Entity Relationships

```
┌─────────────────┐       ┌─────────────────┐
│ PromptTemplate  │──1:N──│ StructuredSection│
└────────┬────────┘       └─────────────────┘
         │
         │1:1
         ▼
┌─────────────────┐       ┌─────────────────┐
│ VariableDef     │       │ VersionHistory  │
└─────────────────┘       └─────────────────┘
         │                         ▲
         │                         │
         └───────────1:N────────────┘
                     │
                     │1:N
                     ▼
┌─────────────────┐       ┌─────────────────┐
│    ABTest       │──1:N──│ PromptVariant   │
└─────────────────┘       └────────┬────────┘
                                   │
                                   │references
                                   ▼
                         ┌─────────────────┐
                         │ PromptTemplate  │
                         │ (specific ver)  │
                         └─────────────────┘

┌─────────────────┐
│  TraceRecord    │
└────────┬────────┘
         │
         │references
         ▼
┌─────────────────────────────────┐
│ PromptTemplate + version        │
│ PromptVariant (if A/B test)     │
└─────────────────────────────────┘
```

---

## Indexes and Queries

### Primary Lookups
- `PromptTemplate` by: `template_id`, `template_id + version`, `tags`
- `ABTest` by: `test_id`, `template_id + status`
- `TraceRecord` by: `trace_id`, `template_id + timestamp range`, `variant_id`
- `VersionHistory` by: `template_id`, `template_id + version`

### Common Query Patterns

1. **Get active prompt**:
   ```python
   SELECT * FROM prompts
   WHERE template_id = ? AND is_active = TRUE
   ```

2. **Get active A/B test for prompt**:
   ```python
   SELECT * FROM ab_tests
   WHERE template_id = ? AND status = 'RUNNING'
   ```

3. **Get recent traces for analytics**:
   ```python
   SELECT * FROM traces
   WHERE template_id = ?
   AND timestamp > ?
   ORDER BY timestamp DESC
   LIMIT 1000
   ```

4. **Get version history**:
   ```python
   SELECT * FROM version_history
   WHERE template_id = ?
   ORDER BY version DESC
   ```

---

## Storage Mapping

| Entity | Storage | Notes |
|--------|---------|-------|
| PromptTemplate | Langfuse prompts | Native prompt management |
| StructuredSection | Langfuse prompts | Stored as template content |
| VariableDef | Langfuse prompts | Stored as template metadata |
| ABTest | Langfuse experiments | Native experiment tracking |
| PromptVariant | Langfuse experiments | Variant definitions |
| TraceRecord | Langfuse traces | Native trace functionality |
| VersionHistory | Langfuse prompt versions | Native versioning |

---

**Document Version**: 1.0 | **Last Updated**: 2026-03-23
