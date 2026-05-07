# Data Model: Conversational Query Enhancement Module

**Feature**: 007-conversational-query
**Date**: 2026-04-10
**Status**: Phase 1 Design

## Overview

This document defines the data entities and their relationships for the Conversational Query Enhancement Module.

## Entity Definitions

### 1. ExtractedQueryElements

Represents the structured extraction results from a user query.

```python
from enum import Enum
from typing import Dict, List, Optional, Set, Any
from pydantic import BaseModel, Field

class QueryType(str, Enum):
    """Query classification types."""
    META_INFO = "meta_info"       # Queries about documents themselves
    BUSINESS_QUERY = "business_query"  # Queries about document content
    UNKNOWN = "unknown"           # Unclear intent

class BusinessDomain(str, Enum):
    """Business domain classifications."""
    FINANCE = "finance"
    HR = "hr"
    SAFETY = "safety"
    GOVERNANCE = "governance"
    IT = "it"
    PROCUREMENT = "procurement"
    ADMIN = "admin"
    PARTY = "party"
    UNION = "union"
    COMMITTEE = "committee"
    OTHER = "other"

class Confidence(str, Enum):
    """Confidence levels for extraction."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class ExtractedQueryElements(BaseModel):
    """Structured extraction results from a user query."""
    # Query classification
    query_type: QueryType = Field(..., description="Type of query")
    domain: Optional[BusinessDomain] = Field(None, description="Business domain if applicable")
    confidence: Confidence = Field(default=Confidence.MEDIUM, description="Extraction confidence")

    # Temporal elements
    year: Optional[int] = Field(None, ge=2020, le=2030)
    date: Optional[str] = Field(None, description="Full date in ISO format")
    time_range: Optional[str] = Field(None, description="Range like 近三年/去年/上半年")
    relative_time: Optional[str] = Field(None, description="Relative like 今年/本月/去年/年底")

    # Spatial elements
    organization: Optional[str] = Field(None, description="粤东科/党总支/工会/各党支部/专业委员会")
    location_type: Optional[str] = Field(None, description="公司级/部门级/多部门")
    city: Optional[str] = Field(None, description="City name for expense queries")

    # Document elements
    doc_type: Optional[str] = Field(None, description="通知/通报/报告/请示/纪要/会议纪要/公示/...")
    doc_number: Optional[str] = Field(None, description="Document number format")
    meeting_type: Optional[str] = Field(None, description="职工代表大会/工会会员代表大会/工作会议/启动会")

    # Knowledge base elements
    company_id: str = Field(..., description="Provided by external system")
    file_type: Optional[str] = Field(None, description="PublicDocDispatch/Receive")

    # Content elements
    topic_keywords: List[str] = Field(default_factory=list, description="Extracted topic keywords")
    policy_names: List[str] = Field(default_factory=list, description="Full policy names if mentioned")

    # Quantity elements
    has_count_query: bool = Field(default=False)
    numbers: List[int] = Field(default_factory=list)
    quantifiers: List[str] = Field(default_factory=list)

    # Follow-up detection
    is_followup: bool = Field(default=False, description="True if pronoun reference detected")
    referenced_slots: Set[str] = Field(default_factory=set, description="Slots referenced from history")
```

**Relationships**:
- Input: `ConversationalQueryInput` (contains original_query and context)
- Output: `BeliefState` (slots merged with existing state)

### 2. BeliefState

Represents the accumulated conversation state with slot filling.

```python
class BeliefState(BaseModel):
    """Conversation state with accumulated slots."""
    trace_id: str
    company_id: str

    # Conversation tracking
    turn_count: int = 0
    created_at: str  # ISO timestamp
    last_activity: str  # ISO timestamp

    # Accumulated slots
    slots: Dict[str, Any] = Field(
        default_factory=dict,
        description="Accumulated values for all dimensions"
    )

    # Conversation history
    query_history: List[str] = Field(default_factory=list)
    response_history: List[str] = Field(default_factory=list)
    extraction_history: List[ExtractedQueryElements] = Field(default_factory=list)

    # Query type and domain
    current_query_type: Optional[QueryType] = None
    current_domain: Optional[BusinessDomain] = None

    # Pending clarifications
    pending_slots: Set[str] = Field(
        default_factory=set,
        description="Slots that need user input"
    )

    # Session status
    status: str = Field(
        default="active",
        description="active | complete | expired"
    )

    def is_complete(self) -> bool:
        """Check if all required slots are filled."""
        return len(self.pending_slots) == 0

    def can_continue(self, max_turns: int = 10) -> bool:
        """Check if session can continue (not at turn limit)."""
        return self.turn_count < max_turns
```

**Storage**:
- Redis key: `belief_state:{trace_id}`
- TTL: 900 seconds (15 minutes)
- Serialization: JSON

**Relationships**:
- Managed by: `BeliefStateStore` service
- Used by: `ConversationalQueryCapability`
- Built from: Multiple `ExtractedQueryElements`

### 3. QueryGenerationResult

Represents the output of query generation for retrieval.

```python
class QueryGenerationResult(BaseModel):
    """Generated queries for document retrieval."""
    # Three question variations
    q1: str = Field(..., description="First question variation")
    q2: str = Field(..., description="Second question variation")
    q3: str = Field(..., description="Third question variation")

    # Core terms that must appear
    must_include: List[str] = Field(
        ...,
        min_items=3,
        max_items=6,
        description="Core anchor terms (3-6 items)"
    )

    # Expanded keywords
    keywords: List[str] = Field(
        ...,
        min_items=5,
        max_items=10,
        description="Expanded with synonyms (5-10 items)"
    )

    # Domain context
    domain_context: str = Field(
        ...,
        description="Query type and domain used for generation"
    )

    # Metadata
    used_slots: Dict[str, Any] = Field(
        default_factory=dict,
        description="Slots that were used in generation"
    )
    colloquial_mappings: Dict[str, str] = Field(
        default_factory=dict,
        description="Colloquial terms that were mapped"
    )
```

**Relationships**:
- Input: `BeliefState` with accumulated slots
- Output: Passed to QA Pipeline for retrieval

### 4. ColloquialTermMapping

Represents a mapping from colloquial to formal terminology.

```python
class ColloquialTermMapping(BaseModel):
    """Mapping from colloquial term to formal terminology."""
    colloquial: str = Field(..., description="Colloquial/informal term")
    formal: List[str] = Field(..., description="Formal equivalent(s)")
    domain: Optional[BusinessDomain] = Field(None, description="Domain if applicable")
    context: Optional[str] = Field(None, description="Usage context if needed")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "colloquial": "防火",
                    "formal": ["消防"],
                    "domain": BusinessDomain.SAFETY,
                    "context": "fire prevention → fire protection"
                },
                {
                    "colloquial": "会议记录",
                    "formal": ["会议纪要"],
                    "domain": None,
                    "context": "meeting records → meeting minutes"
                },
                {
                    "colloquial": "职代会",
                    "formal": ["职工代表大会"],
                    "domain": BusinessDomain.UNION,
                    "context": "workers' congress abbreviation"
                }
            ]
        }
```

**Storage**:
- In-memory cache with periodic Redis persistence
- Can be loaded from configuration or learned from usage

**Relationships**:
- Managed by: `ColloquialMapper` service
- Used by: `ConversationalQueryCapability` during slot extraction

### 5. ConversationalQueryInput

Input for conversational query capability.

```python
class ConversationalQueryInput(CapabilityInput):
    """Input for conversational query processing."""
    query: str = Field(..., min_length=1, max_length=500)
    context: QAContext  # Reusing from qa_schemas.py
    trace_id: str = Field(..., description="Session trace ID")

    # Options
    enable_colloquial_mapping: bool = Field(default=True)
    enable_query_expansion: bool = Field(default=True)
    max_turns: int = Field(default=10, ge=1, le=20)
```

### 6. ConversationalQueryOutput

Output from conversational query capability.

```python
class ConversationalQueryOutput(CapabilityOutput):
    """Output from conversational query processing."""

    # Action to take
    action: str = Field(
        ...,
        description="proceed | prompt | complete"
    )

    # Prompt for user (if action="prompt")
    prompt_text: Optional[str] = None

    # Query generation results (if action="proceed" or "complete")
    query_generation: Optional[QueryGenerationResult] = None

    # Session info
    belief_state: BeliefState

    # Extracted elements (current turn)
    extracted_elements: ExtractedQueryElements

    # Colloquial mappings applied
    applied_mappings: Dict[str, str] = Field(default_factory=dict)
```

## Entity Relationships

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           Entity Relationship Diagram                                │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  ┌──────────────────────────┐         ┌─────────────────────────────────────────┐  │
│  │ ConversationalQueryInput│         │           BeliefState (Redis)           │  │
│  │  ┌────────────────────┐  │         │  ┌────────────────────────────────────┐  │  │
│  │  │ query: str         │  │         │  │ trace_id: str (PK)                 │  │  │
│  │  │ context: QAContext │  │         │  │ company_id: str                    │  │  │
│  │  │ trace_id: str      │───┼────────▶│  │ slots: Dict[str, Any]              │  │  │
│  │  └────────────────────┘  │         │  │ turn_count: int                    │  │  │
│  └──────────┬───────────────┘         │  │ status: str                        │  │  │
│             │                          │  │ current_domain: BusinessDomain     │  │  │
│             │ produces                 │  └────────────────────────────────────┘  │  │
│             ▼                          └─────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────────────────┐    │        │
│  │                    ExtractedQueryElements                                 │    │        │
│  │  ┌─────────────────────────────────────────────────────────────────────┐  │    │        │
│  │  │ query_type: QueryType                                              │  │    │        │
│  │  │ domain: BusinessDomain                                             │  │    │        │
│  │  │ year, date, time_range (Temporal)                                  │  │    │        │
│  │  │ organization, location_type, city (Spatial)                        │  │    │        │
│  │  │ doc_type, doc_number, meeting_type (Document)                      │  │    │        │
│  │  │ topic_keywords, policy_names (Content)                             │  │    │        │
│  │  │ is_followup: bool                                                  │  │    │        │
│  │  └─────────────────────────────────────────────────────────────────────┘  │    │        │
│  └─────────────────────────────────────────────────────────────────────────────┘    │        │
│                                                                              │        │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │        │
│  │                    QueryGenerationResult                               │ │ │        │
│  │  ┌─────────────────────────────────────────────────────────────────┐   │ │        │
│  │  │ q1, q2, q3: str (Three question variations)                     │   │ │        │
│  │  │ must_include: List[str] (3-6 core terms)                         │   │ │        │
│  │  │ keywords: List[str] (5-10 expanded terms)                         │   │ │        │
│  │  │ domain_context: str                                              │   │ │        │
│  │  └─────────────────────────────────────────────────────────────────┘   │ │        │
│  └─────────────────────────────────────────────────────────────────────────┘ │        │
│                                                                              │        │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │        │
│  │                    ColloquialTermMapping                               │ │ │        │
│  │  ┌───────────────────────────────────────────────────────────────────┐ │ │        │
│  │  │ colloquial: str                                                   │ │ │        │
│  │  │ formal: List[str]                                                 │ │ │        │
│  │  │ domain: BusinessDomain                                            │ │ │        │
│  │  │ context: str                                                      │ │ │        │
│  │  └───────────────────────────────────────────────────────────────────┘ │ │        │
│  └─────────────────────────────────────────────────────────────────────────┘ │        │
│                                                                              │        │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

## Validation Rules

### ExtractedQueryElements
- `year` must be between 2020 and 2030
- `has_count_query` must be true if query contains "多少/几个/总数"
- `query_type` must be one of: meta_info, business_query, unknown
- If `is_followup` is true, `referenced_slots` must not be empty

### BeliefState
- `turn_count` must be >= 0
- `status` must be one of: "active", "complete", "expired"
- `company_id` must match regex `^[A-Z]\d{6,}$` (e.g., N000002)

### QueryGenerationResult
- `must_include` must have 3-6 items
- `keywords` must have 5-10 items
- `q1`, `q2`, `q3` must all be non-empty

### ConversationalQueryInput
- `query` must be 1-500 characters (non-empty after trim)
- `max_turns` must be between 1 and 20

## State Transitions

### BeliefState Lifecycle

```
┌─────────┐    1. Create session    ┌─────────┐
│  None   │ ─────────────────────▶ │ Active  │
└─────────┘                        └────┬────┘
                                        │
           2. Accumulate slots      │ 3. All slots present
           or timeout                │
        ┌─────────────────────────────┼────────────┐
        │                             │            │
        ▼                             ▼            ▼
   ┌─────────┐                   ┌─────────┐ ┌──────────┐
   │ Expired │                   │ Complete│ │  Active  │
   │ (TTL)   │                   │         │ │ (more    │
   └─────────┘                   └─────────┘ │  turns)  │
                                             └──────────┘
```

## Storage Schema

### Redis Key Structure

```
belief_state:{trace_id} → BeliefState (JSON)
```

**Example**:
```json
{
  "trace_id": "abc-123",
  "company_id": "N000002",
  "turn_count": 2,
  "created_at": "2026-04-10T10:30:00Z",
  "last_activity": "2026-04-10T10:32:15Z",
  "slots": {
    "year": 2024,
    "domain": "safety",
    "topic": "消防"
  },
  "pending_slots": ["level"],
  "query_history": ["安全规定", "2024年的", "消防的"],
  "extraction_history": [...],
  "current_query_type": "business_query",
  "current_domain": "safety",
  "status": "active"
}
```

## File Locations

| Entity | File Location |
|--------|---------------|
| `QueryType`, `BusinessDomain`, `Confidence` | `src/rag_service/models/conversational_query.py` |
| `ExtractedQueryElements` | `src/rag_service/models/conversational_query.py` |
| `BeliefState` | `src/rag_service/models/conversational_query.py` |
| `QueryGenerationResult` | `src/rag_service/models/conversational_query.py` |
| `ColloquialTermMapping` | `src/rag_service/models/conversational_query.py` |
| `ConversationalQueryInput` | `src/rag_service/capabilities/conversational_query.py` |
| `ConversationalQueryOutput` | `src/rag_service/capabilities/conversational_query.py` |
| `BeliefStateStore` | `src/rag_service/services/belief_state_store.py` |
| `ColloquialMapper` | `src/rag_service/services/colloquial_mapper.py` |
