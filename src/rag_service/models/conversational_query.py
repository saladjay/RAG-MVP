"""
Conversational Query Enhancement data models.

This module defines the data models for the Conversational Query Enhancement
feature, which supports multi-turn conversation with structured query extraction,
business domain classification, and colloquial term mapping.

Key Models:
- QueryType: Enum for query classification (meta_info, business_query, unknown)
- BusinessDomain: Enum for 10 business domains
- ExtractedQueryElements: Structured extraction from user queries
- BeliefState: Conversation context accumulation across turns
- QueryGenerationResult: Generated queries with slot filling and keyword expansion
- ColloquialTermMapping: Colloquial to formal terminology mappings
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class QueryType(str, Enum):
    """Query classification types.

    Determines the processing strategy:
    - meta_info: User is asking ABOUT documents (inventory, metadata)
    - business_query: User is asking FOR document content (answers, procedures)
    - unknown: Cannot determine from query
    """

    META_INFO = "meta_info"
    BUSINESS_QUERY = "business_query"
    UNKNOWN = "unknown"


class BusinessDomain(str, Enum):
    """Business domain classifications for query routing.

    Each domain has specialized keyword sets and query templates.
    """

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

    # Finance sub-domains
    ACCOMMODATION = "accommodation"
    MEAL = "meal"
    TRANSPORT = "transport"


class TemporalElements(BaseModel):
    """Temporal (time-related) elements extracted from query.

    Attributes:
        time_range: General time range (e.g., "最近", "今年", "去年")
        year: Specific year
        month: Specific month
        date: Specific date
        quarter: Quarter (Q1, Q2, Q3, Q4)
    """

    time_range: Optional[str] = Field(default=None, description="Time range")
    year: Optional[str] = Field(default=None, description="Year")
    month: Optional[str] = Field(default=None, description="Month")
    date: Optional[str] = Field(default=None, description="Date")
    quarter: Optional[str] = Field(default=None, description="Quarter")


class SpatialElements(BaseModel):
    """Spatial (location-related) elements extracted from query.

    Attributes:
        city: City name
        province: Province name
        location: General location description
    """

    city: Optional[str] = Field(default=None, description="City name")
    province: Optional[str] = Field(default=None, description="Province name")
    location: Optional[str] = Field(default=None, description="Location description")


class DocumentElements(BaseModel):
    """Document-related elements extracted from query.

    Attributes:
        doc_type: Document type (通知, 通报, 报告, etc.)
        organization: Issuing organization
        doc_number: Document number
    """

    doc_type: Optional[str] = Field(default=None, description="Document type")
    organization: Optional[str] = Field(default=None, description="Issuing organization")
    doc_number: Optional[str] = Field(default=None, description="Document number")


class ContentElements(BaseModel):
    """Content-related elements extracted from query.

    Attributes:
        topic: Main topic or subject
        keywords: List of relevant keywords
        business_domain: Detected business domain
    """

    topic: Optional[str] = Field(default=None, description="Main topic")
    keywords: List[str] = Field(default_factory=list, description="Relevant keywords")
    business_domain: Optional[BusinessDomain] = Field(
        default=None, description="Business domain"
    )


class QuantityElements(BaseModel):
    """Quantity-related elements extracted from query.

    Attributes:
        amount: Monetary amount
        count: Item count
        frequency: Frequency or rate
    """

    amount: Optional[str] = Field(default=None, description="Amount")
    count: Optional[int] = Field(default=None, description="Count")
    frequency: Optional[str] = Field(default=None, description="Frequency")


class ExtractedQueryElements(BaseModel):
    """Structured extraction result from user query.

    Contains all extracted elements organized by category.

    Attributes:
        query_type: Classification of query (meta_info/business_query/unknown)
        is_followup: Whether this is a follow-up query
        temporal: Time-related elements
        spatial: Location-related elements
        document: Document-related elements
        content: Content-related elements
        quantity: Quantity-related elements
        confidence: Extraction confidence score (0.0-1.0)
        missing_slots: List of critical slots that are missing
        clarification_needed: Whether user clarification is needed
        detected_domain: Detected business domain
        trace_id: Trace ID for correlation
    """

    query_type: QueryType = Field(..., description="Query classification")
    is_followup: bool = Field(default=False, description="Is follow-up query")
    temporal: TemporalElements = Field(default_factory=TemporalElements)
    spatial: SpatialElements = Field(default_factory=SpatialElements)
    document: DocumentElements = Field(default_factory=DocumentElements)
    content: ContentElements = Field(default_factory=ContentElements)
    quantity: QuantityElements = Field(default_factory=QuantityElements)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Confidence score")
    missing_slots: List[str] = Field(default_factory=list, description="Missing critical slots")
    clarification_needed: bool = Field(default=False, description="Needs clarification")
    detected_domain: Optional[BusinessDomain] = Field(default=None, description="Detected domain")
    trace_id: str = Field(..., description="Trace ID")

    class Config:
        """Pydantic model configuration."""

        use_enum_values = True


@dataclass
class BeliefState:
    """Belief state for conversational context accumulation.

    Tracks extracted slots across conversation turns for context
    inheritance and slot filling.

    Attributes:
        session_id: Unique session identifier
        user_id: Optional user identifier
        conversation_turn: Current turn number
        slots: Accumulated slot values
        query_history: History of user queries
        extraction_history: History of extraction results
        last_updated: Last update timestamp
        created_at: Session creation timestamp
    """

    session_id: str
    conversation_turn: int = 0
    slots: Dict[str, Any] = field(default_factory=dict)
    query_history: List[str] = field(default_factory=list)
    extraction_history: List[Dict[str, Any]] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.utcnow)
    created_at: datetime = field(default_factory=datetime.utcnow)
    user_id: Optional[str] = None

    # Known slot keys
    SLOT_CITY = "city"
    SLOT_EXPENSE_TYPE = "expense_type"
    SLOT_LEVEL = "level"
    SLOT_TOPIC = "topic"
    SLOT_YEAR = "year"
    SLOT_ORGANIZATION = "organization"
    SLOT_DOC_TYPE = "doc_type"

    def set_slot(self, key: str, value: Any) -> None:
        """Set a slot value.

        Args:
            key: Slot key
            value: Slot value
        """
        self.slots[key] = value
        self.last_updated = datetime.utcnow()

    def get_slot(self, key: str, default: Any = None) -> Any:
        """Get a slot value.

        Args:
            key: Slot key
            default: Default value if not found

        Returns:
            Slot value or default
        """
        return self.slots.get(key, default)

    def has_slot(self, key: str) -> bool:
        """Check if slot has a value.

        Args:
            key: Slot key

        Returns:
            True if slot has non-None value
        """
        return key in self.slots and self.slots[key] is not None

    def add_query(self, query: str) -> None:
        """Add query to history.

        Args:
            query: User query text
        """
        self.query_history.append(query)
        self.conversation_turn += 1
        self.last_updated = datetime.utcnow()

    def add_extraction(self, extraction: Dict[str, Any]) -> None:
        """Add extraction result to history.

        Args:
            extraction: Extraction result dictionary
        """
        self.extraction_history.append(extraction)
        self.last_updated = datetime.utcnow()

    def get_context_string(self) -> str:
        """Get context string for query generation.

        Returns:
            Formatted context string
        """
        parts = []
        for key, value in self.slots.items():
            if value:
                parts.append(f"{key}={value}")
        return " | ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Redis storage.

        Returns:
            Dictionary representation
        """
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "conversation_turn": self.conversation_turn,
            "slots": self.slots,
            "query_history": self.query_history,
            "extraction_history": self.extraction_history,
            "last_updated": self.last_updated.isoformat(),
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BeliefState":
        """Create BeliefState from dictionary.

        Args:
            data: Dictionary representation

        Returns:
            BeliefState instance
        """
        return cls(
            session_id=data["session_id"],
            user_id=data.get("user_id"),
            conversation_turn=data.get("conversation_turn", 0),
            slots=data.get("slots", {}),
            query_history=data.get("query_history", []),
            extraction_history=data.get("extraction_history", []),
            last_updated=datetime.fromisoformat(data["last_updated"]) if data.get("last_updated") else datetime.utcnow(),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow(),
        )


class QueryGenerationResult(BaseModel):
    """Result of structured query generation.

    Contains generated queries with slot filling and keyword expansion.

    Attributes:
        q1: First generated query (direct phrasing)
        q2: Second generated query (professional phrasing)
        q3: Third generated query (combined elements)
        must_include: Core anchor terms (3-6 terms)
        expanded_keywords: Expanded keywords (5-10 terms)
        slot_filled: Slots filled from belief state
        location_context: Location context for query
        domain_specific_terms: Domain-specific terminology
        trace_id: Trace ID for correlation
    """

    q1: str = Field(..., description="First generated query")
    q2: str = Field(..., description="Second generated query")
    q3: str = Field(..., description="Third generated query")
    must_include: List[str] = Field(
        default_factory=list,
        min_length=3,
        max_length=6,
        description="Core anchor terms",
    )
    expanded_keywords: List[str] = Field(
        default_factory=list,
        min_length=5,
        max_length=10,
        description="Expanded keywords",
    )
    slot_filled: Dict[str, str] = Field(default_factory=dict, description="Filled slots")
    location_context: Optional[str] = Field(default=None, description="Location context")
    domain_specific_terms: List[str] = Field(default_factory=list, description="Domain terms")
    trace_id: str = Field(..., description="Trace ID")


class ColloquialTermMapping(BaseModel):
    """Mapping from colloquial to formal terminology.

    Attributes:
        colloquial: Colloquial expression
        formal: Formal terminology
        domain: Associated business domain
        confidence: Mapping confidence
    """

    colloquial: str = Field(..., description="Colloquial expression")
    formal: str = Field(..., description="Formal terminology")
    domain: Optional[BusinessDomain] = Field(default=None, description="Business domain")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence")


class ConversationalQueryRequest(BaseModel):
    """Request for conversational query enhancement.

    Attributes:
        query: User's query text
        session_id: Optional session ID for multi-turn
        trace_id: Trace ID for correlation
        enable_colloquial_mapping: Enable colloquial mapping
        enable_domain_routing: Enable domain routing
        enable_followup_detection: Enable follow-up detection
    """

    query: str = Field(..., min_length=1, description="User's query")
    session_id: Optional[str] = Field(default=None, description="Session ID")
    trace_id: str = Field(..., description="Trace ID")
    enable_colloquial_mapping: bool = Field(default=True, description="Enable colloquial mapping")
    enable_domain_routing: bool = Field(default=True, description="Enable domain routing")
    enable_followup_detection: bool = Field(default=True, description="Enable follow-up detection")


class ConversationalQueryResponse(BaseModel):
    """Response from conversational query enhancement.

    Attributes:
        query_type: Classified query type
        generated_queries: Generated query variations
        extracted_elements: Structured extraction result
        belief_state: Current belief state
        is_followup: Whether this was a follow-up
        confidence: Confidence score
        clarification_needed: Whether clarification is needed
        clarification_prompt: Optional prompt for user
        session_id: Session ID for continuation
        turn_count: Current turn count
        trace_id: Trace ID
    """

    query_type: QueryType = Field(..., description="Classified query type")
    generated_queries: QueryGenerationResult = Field(..., description="Generated queries")
    extracted_elements: ExtractedQueryElements = Field(..., description="Extracted elements")
    belief_state: Dict[str, Any] = Field(default_factory=dict, description="Belief state")
    is_followup: bool = Field(default=False, description="Is follow-up query")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    clarification_needed: bool = Field(default=False, description="Needs clarification")
    clarification_prompt: Optional[str] = Field(default=None, description="Clarification prompt")
    session_id: str = Field(..., description="Session ID")
    turn_count: int = Field(default=0, description="Turn count")
    trace_id: str = Field(..., description="Trace ID")
