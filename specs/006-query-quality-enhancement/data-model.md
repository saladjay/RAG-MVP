# Data Model: Query Quality Enhancement Module

**Feature**: 006-query-quality-enhancement
**Date**: 2026-04-09
**Status**: Phase 1 Design

## Overview

This document defines the data entities and their relationships for the Query Quality Enhancement Module.

## Entity Definitions

### 1. DimensionAnalysisResult

Represents the result of analyzing a user query against required document dimensions.

```python
from enum import Enum
from typing import Dict, List, Optional, Set
from pydantic import BaseModel, Field

class DimensionType(str, Enum):
    """Document dimension types."""
    COMPANY_ID = "company_id"           # Provided by external system
    FILE_TYPE = "file_type"             # PublicDocDispatch/PublicDocReceive
    DOC_TYPE = "doc_type"               # 通知/通报/报告/请示/纪要/...
    ORGANIZATION = "organization"       # 粤东科/党总支/工会/...
    YEAR = "year"                       # 2024/2023/...
    DOC_NUMBER = "doc_number"           # 文号格式
    SUBJECT = "subject"                 # 主题内容

class DimensionStatus(BaseModel):
    """Status of a single dimension in the query."""
    dimension: DimensionType
    present: bool
    value: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)

class DimensionAnalysisResult(BaseModel):
    """Result of dimension analysis on a user query."""
    present: Dict[DimensionType, str] = Field(
        default_factory=dict,
        description="Dimensions found in query with their values"
    )
    missing: Set[DimensionType] = Field(
        default_factory=set,
        description="Dimensions not found in query"
    )
    confidence: str = Field(
        default="medium",
        description="Overall analysis confidence: high/medium/low"
    )
    prompt_text: Optional[str] = Field(
        default=None,
        description="Suggested prompt text to request missing dimensions"
    )
    quality_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Query completeness score (0-1)"
    )
```

**Relationships**:
- Input: `QueryQualityInput` (contains original_query and context)
- Output: `QueryQualityOutput` (wraps this with metadata)

### 2. SessionState

Represents the conversation state stored in Redis for multi-turn dimension collection.

```python
class SessionState(BaseModel):
    """Session state for multi-turn dimension collection."""
    trace_id: str
    company_id: str
    file_type: Optional[str] = None  # PublicDocDispatch/PublicDocReceive

    # Conversation tracking
    turn_count: int = 0
    created_at: str  # ISO timestamp
    last_activity: str  # ISO timestamp

    # Dimension accumulation
    established_dimensions: Dict[DimensionType, str] = Field(
        default_factory=dict
    )
    pending_dimensions: Set[DimensionType] = Field(
        default_factory=set
    )

    # Conversation history (for context reference)
    query_history: List[str] = Field(default_factory=list)
    response_history: List[str] = Field(default_factory=list)

    # Session status
    status: str = Field(
        default="active",
        description="active | complete | expired"
    )

    def is_expired(self, timeout_minutes: int = 15) -> bool:
        """Check if session has expired due to inactivity."""
        # Implementation in capability
        pass

    def can_continue(self, max_turns: int = 10) -> bool:
        """Check if session can continue (not at turn limit)."""
        return self.turn_count < max_turns
```

**Storage**:
- Redis key: `session:{trace_id}`
- TTL: 900 seconds (15 minutes)
- Serialization: JSON

**Relationships**:
- Managed by: `SessionStore` service
- Used by: `QueryQualityCapability`

### 3. QueryQualityInput

Input for query quality analysis capability.

```python
class QueryQualityInput(CapabilityInput):
    """Input for query quality analysis."""
    query: str = Field(..., min_length=1, max_length=1000)
    context: QAContext  # Reusing from qa_schemas.py
    session_id: str = Field(..., description="Session trace_id")

    # Options
    auto_enrich: bool = Field(
        default=True,
        description="Automatically enrich with defaults (e.g., current year)"
    )
    require_all_dimensions: bool = Field(
        default=False,
        description="If True, require ALL dimensions before proceeding"
    )
```

### 4. QueryQualityOutput

Output from query quality analysis capability.

```python
class QueryQualityOutput(CapabilityOutput):
    """Output from query quality analysis."""

    # Analysis results
    analysis: DimensionAnalysisResult

    # Session info
    session_state: SessionState

    # Action to take
    action: str = Field(
        ...,
        description="proceed | prompt | complete"
    )
    prompt_text: Optional[str] = None  # Set if action="prompt"

    # Enhanced query (if ready to proceed)
    enhanced_query: Optional[str] = None
    enhanced_context: Optional[QAContext] = None

    # Feedback (for display to user)
    feedback: Optional[str] = Field(
        default=None,
        description="Quality feedback message"
    )
```

### 5. KnowledgeBaseRoute

Determines which knowledge base(s) to search based on query analysis.

```python
class KnowledgeBaseRoute(BaseModel):
    """Routing information for knowledge base selection."""
    company_id: str
    file_type: Optional[str] = None  # None = search both
    search_mode: str = Field(
        default="single",
        description="single | dual"
    )
    collections: List[str] = Field(
        default_factory=list,
        description="List of collection names to search"
    )

    @classmethod
    def from_context(
        cls,
        company_id: str,
        file_type: Optional[str]
    ) -> "KnowledgeBaseRoute":
        """Create route from query context."""
        if file_type:
            return cls(
                company_id=company_id,
                file_type=file_type,
                search_mode="single",
                collections=[f"{company_id}_{file_type}"]
            )
        else:
            # Dual search when file_type unclear
            return cls(
                company_id=company_id,
                file_type=None,
                search_mode="dual",
                collections=[
                    f"{company_id}_PublicDocDispatch",
                    f"{company_id}_PublicDocReceive"
                ]
            )
```

## Entity Relationships

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           Entity Relationship Diagram                                │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  ┌──────────────────────┐         ┌──────────────────────────────────────────┐     │
│  │  QueryQualityInput   │         │         SessionState (Redis)             │     │
│  │  ┌────────────────┐  │         │  ┌────────────────────────────────────┐  │     │
│  │  │ query: str     │  │         │  │ trace_id: str (PK)                 │  │     │
│  │  │ context        │  │         │  │ company_id: str                    │  │     │
│  │  │ session_id     │───┼────────▶│  │ established_dimensions: Dict        │  │     │
│  │  └────────────────┘  │         │  │ turn_count: int                    │  │     │
│  └──────────┬───────────┘         │  │ status: str                        │  │     │
│             │                     │  └────────────────────────────────────┘  │     │
│             │                     └───────────────────────────────────────────┘     │
│             │                                                               │        │
│             │ produces                                                      │        │
│             ▼                                                               │        │
│  ┌──────────────────────────────────────────────────────────────────────┐      │        │
│  │                      QueryQualityOutput                               │      │        │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │      │        │
│  │  │ analysis: DimensionAnalysisResult                               │  │      │        │
│  │  │  ┌─────────────────────────────────────────────────────────┐   │  │      │        │
│  │  │  │ present: Dict[DimensionType, str]                         │   │  │      │        │
│  │  │  │ missing: Set[DimensionType]                               │   │  │      │        │
│  │  │  │ quality_score: float                                      │   │  │      │        │
│  │  │  │ prompt_text: Optional[str]                                │   │  │      │        │
│  │  │  └─────────────────────────────────────────────────────────┘   │  │      │        │
│  │  ├─────────────────────────────────────────────────────────────────┤  │      │        │
│  │  │ action: "proceed" | "prompt" | "complete"                       │  │      │        │
│  │  │ enhanced_query: Optional[str]                                  │  │      │        │
│  │  │ enhanced_context: Optional[QAContext]                           │  │      │        │
│  │  └─────────────────────────────────────────────────────────────────┘  │      │        │
│  └──────────────────────────────────────────────────────────────────────┘      │        │
│                                                                              │        │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │        │
│  │                    KnowledgeBaseRoute                                   │ │ │        │
│  │  ┌───────────────────────────────────────────────────────────────────┐ │ │        │
│  │  │ company_id: str                                                    │ │ │        │
│  │  │ file_type: Optional[str]                                          │ │ │        │
│  │  │ search_mode: "single" | "dual"                                    │ │ │        │
│  │  │ collections: List[str] (e.g., ["N000002_PublicDocDispatch"])      │ │ │        │
│  │  └───────────────────────────────────────────────────────────────────┘ │ │        │
│  └─────────────────────────────────────────────────────────────────────────┘ │        │
│                                                                              │        │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

## Validation Rules

### DimensionAnalysisResult
- `quality_score` must be between 0.0 and 1.0
- `confidence` must be one of: "high", "medium", "low"
- At least one of `present` or `missing` must be non-empty
- If `missing` is empty, `action` should be "proceed"

### SessionState
- `turn_count` must be >= 0
- `status` must be one of: "active", "complete", "expired"
- `company_id` must match regex `^[A-Z]\d{6,}$` (e.g., N000002)

### QueryQualityInput
- `query` must be 1-1000 characters (non-empty after trim)
- `company_id` in context must be provided (from external system)

### QueryQualityOutput
- `action` must be one of: "proceed", "prompt", "complete"
- If `action="prompt"`, `prompt_text` must be provided
- If `action="proceed"`, `enhanced_query` must be provided

## State Transitions

### SessionState Lifecycle

```
┌─────────┐    1. Create session    ┌─────────┐
│  None   │ ─────────────────────▶ │ Active  │
└─────────┘                        └────┬────┘
                                        │
           2. Receive dimensions      │ 3. All dims present
           or timeout                 │
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
session:{trace_id} → SessionState (JSON)
```

**Example**:
```json
{
  "trace_id": "abc-123",
  "company_id": "N000002",
  "file_type": "PublicDocDispatch",
  "turn_count": 2,
  "created_at": "2026-04-09T10:30:00Z",
  "last_activity": "2026-04-09T10:32:15Z",
  "established_dimensions": {
    "year": "2024",
    "doc_type": "通知"
  },
  "pending_dimensions": ["subject"],
  "query_history": ["安全通知", "2024年的"],
  "response_history": ["请问您需要查找哪一年的安全通知？", "好的"],
  "status": "active"
}
```

## File Locations

| Entity | File Location |
|--------|---------------|
| `DimensionType`, `DimensionStatus` | `src/rag_service/models/query_quality.py` |
| `DimensionAnalysisResult` | `src/rag_service/models/query_quality.py` |
| `SessionState` | `src/rag_service/models/query_quality.py` |
| `QueryQualityInput` | `src/rag_service/capabilities/query_quality.py` |
| `QueryQualityOutput` | `src/rag_service/capabilities/query_quality.py` |
| `KnowledgeBaseRoute` | `src/rag_service/models/query_quality.py` |
| `SessionStore` | `src/rag_service/services/session_store.py` |
