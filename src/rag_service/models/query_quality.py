"""
Query Quality Enhancement data models.

This module defines the data models for the Query Quality Enhancement feature,
which supports multi-turn conversation for gathering missing query dimensions
before executing document searches.

Models support extended dimension values from 2025 document analysis including:
- 会议纪要 (meeting minutes)
- 会议类型 (meeting types: 职工代表大会, 工会会员代表大会, 各专业委员会)
- 专业委员会 (professional committees: 经审委员会, 女职工委员会, 提案委员会)

Document Dimensions:
- Company ID (公司标识): Provided by external system
- File Category (文件类别): PublicDocDispatch (发文), PublicDocReceive (收文)
- Document Type (公文类型): Including 2025 additions
- Organization (发文单位): Including 2025 additions
- Year/Number (年份文号): Year and document number format
- Subject/Content (主题内容): Including 2025 expanded categories
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DimensionType(str, Enum):
    """Document dimension types for query analysis.

    These dimensions are required for effective document retrieval in the
    official document management system. Each dimension represents a key
    attribute that helps narrow down search results.
    """

    COMPANY_ID = "company_id"
    FILE_CATEGORY = "file_category"
    DOCUMENT_TYPE = "document_type"
    ORGANIZATION = "organization"
    YEAR_NUMBER = "year_number"
    SUBJECT_CONTENT = "subject_content"


class DimensionStatus(str, Enum):
    """Status of a dimension in the user's query.

    Indicates whether a dimension value is present, missing, inferred from
    context, or unclear and requires clarification.
    """

    PRESENT = "present"
    ABSENT = "absent"
    INFERRED = "inferred"
    UNCLEAR = "unclear"


class FileType(str, Enum):
    """File category (文件类别) for document routing.

    Determines which knowledge base to search:
    - PublicDocDispatch: Outgoing documents (发文)
    - PublicDocReceive: Incoming documents (收文)
    """

    PUBLIC_DOC_DISPATCH = "PublicDocDispatch"
    PUBLIC_DOC_RECEIVE = "PublicDocReceive"


class DocumentType(str, Enum):
    """Official document types (公文类型).

    Includes both basic types and 2025 additions for comprehensive coverage.
    """

    # Basic document types
    NOTICE = "通知"
    BULLETIN = "通报"
    REPORT = "报告"
    REQUEST = "请示"
    SUMMARY = "纪要"
    ANNOUNCEMENT = "公示"
    PLAN = "方案"
    MEASURE = "办法"
    RULE = "细则"
    REGULATION = "规则"
    PLANNING = "规划"
    KEY_POINTS = "要点"

    # 2025 additions
    MEETING_MINUTES = "会议纪要"


class Organization(str, Enum):
    """Document issuing organizations (发文单位).

    Includes both basic units and 2025 additions for meeting-related bodies.
    """

    # Basic organizations
    YUEDONG_KE = "粤东科"
    PARTY_BRANCH = "粤东科党总支"
    LABOR_UNION = "粤东科工会"
    PARTY_BRANCHES = "各党支部"

    # 2025 additions - Meeting bodies
    WORKERS_CONGRESS = "职工代表大会"
    UNION_MEMBER_CONGRESS = "工会会员代表大会"
    PROFESSIONAL_COMMITTEES = "各专业委员会"

    # Professional committees (专业委员会 subcategories)
    AUDIT_COMMITTEE = "经审委员会"
    FEMALE_WORKER_COMMITTEE = "女职工委员会"
    PROPOSAL_COMMITTEE = "提案委员会"


class SubjectCategory(str, Enum):
    """Document subject/content categories (主题内容).

    Includes both basic categories and 2025 expanded categories.
    """

    # Basic categories
    PARTY_BUILDING = "党建相关"
    PERSONNEL = "人事相关"
    SAFETY_PRODUCTION = "安全生产"
    ADMINISTRATION = "行政管理"
    SYSTEM_BUILDING = "制度建设"

    # 2025 expanded categories
    MEETING_MANAGEMENT = "会议管理"
    DEMOCRATIC_MANAGEMENT = "民主管理"
    PROPOSAL_HANDLING = "提案办理"
    WORKER_RIGHTS = "职工权益"
    AUDIT_WORK = "经审工作"
    FEMALE_WORKER = "女工工作"


class DimensionInfo(BaseModel):
    """Information about a single dimension in the user's query.

    Attributes:
        dimension_type: Type of dimension
        status: Whether the dimension is present/absent/inferred/unclear
        value: The actual or inferred value
        confidence: Confidence score (0.0-1.0)
        source: Where the value came from (user_query, inferred, system_default)
    """

    dimension_type: DimensionType = Field(..., description="Dimension type")
    status: DimensionStatus = Field(..., description="Dimension status")
    value: Optional[str] = Field(default=None, description="Dimension value")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence score")
    source: str = Field(default="user_query", description="Value source")


class DimensionAnalysisResult(BaseModel):
    """Result of analyzing a user query for required dimensions.

    Attributes:
        dimensions: Analysis of each dimension
        quality_score: Overall query completeness score (0.0-1.0)
        action: What action to take (proceed/prompt/complete)
        missing_dimensions: List of dimension types that are missing
        suggested_prompts: Suggested prompt texts for missing dimensions
    """

    dimensions: Dict[DimensionType, DimensionInfo] = Field(
        default_factory=dict,
        description="Analysis of each required dimension",
    )
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Query completeness score")
    action: str = Field(default="prompt", description="Action to take: proceed/prompt/complete")
    missing_dimensions: List[DimensionType] = Field(
        default_factory=list,
        description="Dimensions that need user input",
    )
    suggested_prompts: List[str] = Field(
        default_factory=list,
        description="Suggested prompts for missing dimensions",
    )
    trace_id: str = Field(..., description="Trace ID for correlation")

    class Config:
        """Pydantic model configuration."""

        use_enum_values = True


@dataclass
class KnowledgeBaseRoute:
    """Knowledge base routing information.

    Determines which knowledge base(s) to search based on company_id and file_type.

    Attributes:
        company_id: Company identifier
        file_type: File category (dispatch or receive)
        collection_name: Full collection name for routing
        search_both: Whether to search both dispatch and receive KBs
    """

    company_id: str
    file_type: Optional[FileType]
    collection_name: str
    search_both: bool = False

    def get_dispatch_collection(self) -> str:
        """Get the dispatch (outgoing) KB collection name.

        Returns:
            Collection name for outgoing documents
        """
        return f"{self.company_id}_PublicDocDispatch"

    def get_receive_collection(self) -> str:
        """Get the receive (incoming) KB collection name.

        Returns:
            Collection name for incoming documents
        """
        return f"{self.company_id}_PublicDocReceive"


@dataclass
class SessionState:
    """Session state for multi-turn query quality conversations.

    Tracks the conversation state across multiple turns to gather
    missing query dimensions from the user.

    Attributes:
        session_id: Unique session identifier
        company_id: Company identifier from external system
        original_query: The user's original query text
        current_dimensions: Current dimension values accumulated
        dimension_prompts_sent: History of prompts sent to user
        user_responses: User's responses to prompts
        turn_count: Number of conversation turns
        created_at: Session creation timestamp
        updated_at: Last update timestamp
        is_complete: Whether all required dimensions are gathered
        enriched_query: The final enriched query with all dimensions
    """

    session_id: str
    company_id: str
    original_query: str
    current_dimensions: Dict[DimensionType, DimensionInfo] = field(default_factory=dict)
    dimension_prompts_sent: List[str] = field(default_factory=list)
    user_responses: List[str] = field(default_factory=list)
    turn_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    is_complete: bool = False
    enriched_query: Optional[str] = None
    trace_id: Optional[str] = None

    def add_dimension(self, dimension: DimensionInfo) -> None:
        """Add or update a dimension in the current state.

        Args:
            dimension: Dimension info to add
        """
        self.current_dimensions[dimension.dimension_type] = dimension
        self.updated_at = datetime.utcnow()

    def get_missing_dimensions(self, required: List[DimensionType]) -> List[DimensionType]:
        """Get list of required dimensions that are still missing.

        Args:
            required: List of required dimension types

        Returns:
            List of missing dimension types
        """
        missing = []
        for dim_type in required:
            if dim_type not in self.current_dimensions:
                missing.append(dim_type)
            elif self.current_dimensions[dim_type].status in (
                DimensionStatus.ABSENT,
                DimensionStatus.UNCLEAR,
            ):
                missing.append(dim_type)
        return missing

    def can_proceed(self) -> bool:
        """Check if session has enough information to proceed with search.

        Returns:
            True if enough dimensions are present to search
        """
        # Must have at least company_id and one of subject_content or document_type
        has_company = (
            DimensionType.COMPANY_ID in self.current_dimensions
            and self.current_dimensions[DimensionType.COMPANY_ID].status == DimensionStatus.PRESENT
        )
        has_content = DimensionType.SUBJECT_CONTENT in self.current_dimensions and self.current_dimensions[
            DimensionType.SUBJECT_CONTENT
        ].status in (DimensionStatus.PRESENT, DimensionStatus.INFERRED)
        has_doc_type = DimensionType.DOCUMENT_TYPE in self.current_dimensions and self.current_dimensions[
            DimensionType.DOCUMENT_TYPE
        ].status in (DimensionStatus.PRESENT, DimensionStatus.INFERRED)

        return has_company and (has_content or has_doc_type)

    def to_dict(self) -> Dict[str, Any]:
        """Convert session state to dictionary for Redis storage.

        Returns:
            Dictionary representation of session state
        """
        return {
            "session_id": self.session_id,
            "company_id": self.company_id,
            "original_query": self.original_query,
            "current_dimensions": {
                k.value: v.model_dump() for k, v in self.current_dimensions.items()
            },
            "dimension_prompts_sent": self.dimension_prompts_sent,
            "user_responses": self.user_responses,
            "turn_count": self.turn_count,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "is_complete": self.is_complete,
            "enriched_query": self.enriched_query,
            "trace_id": self.trace_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionState":
        """Create SessionState from dictionary (from Redis).

        Args:
            data: Dictionary representation of session state

        Returns:
            SessionState instance
        """
        dimensions = {}
        for dim_type_str, dim_info in data.get("current_dimensions", {}).items():
            dim_type = DimensionType(dim_type_str)
            dimensions[dim_type] = DimensionInfo(**dim_info)

        return cls(
            session_id=data["session_id"],
            company_id=data["company_id"],
            original_query=data["original_query"],
            current_dimensions=dimensions,
            dimension_prompts_sent=data.get("dimension_prompts_sent", []),
            user_responses=data.get("user_responses", []),
            turn_count=data.get("turn_count", 0),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            is_complete=data.get("is_complete", False),
            enriched_query=data.get("enriched_query"),
            trace_id=data.get("trace_id"),
        )


class QueryQualityRequest(BaseModel):
    """Request for query quality analysis and enhancement.

    Attributes:
        query: User's query text
        company_id: Company identifier (from external system)
        session_id: Optional session ID for multi-turn conversations
        trace_id: Trace ID for correlation
        enable_auto_enrich: Enable automatic query enrichment
        require_all_dimensions: Require all dimensions before proceeding
    """

    query: str = Field(..., min_length=1, description="User's query text")
    company_id: str = Field(..., description="Company identifier")
    session_id: Optional[str] = Field(default=None, description="Session ID for multi-turn")
    trace_id: str = Field(..., description="Trace ID for correlation")
    enable_auto_enrich: bool = Field(default=True, description="Enable auto enrichment")
    require_all_dimensions: bool = Field(default=False, description="Require all dimensions")


class QueryQualityResponse(BaseModel):
    """Response from query quality analysis.

    Attributes:
        action: Action to take (proceed/prompt/complete)
        enriched_query: The enriched query (if action is proceed)
        prompt_text: Prompt text to show user (if action is prompt)
        quality_score: Query completeness score
        dimensions: Current dimension states
        session_id: Session ID for continuation
        turn_count: Number of conversation turns
        trace_id: Trace ID for correlation
    """

    action: str = Field(..., description="Action to take: proceed/prompt/complete")
    enriched_query: Optional[str] = Field(default=None, description="Enriched query for search")
    prompt_text: Optional[str] = Field(default=None, description="Prompt text for user")
    quality_score: float = Field(..., ge=0.0, le=1.0, description="Query completeness score")
    dimensions: Dict[str, DimensionInfo] = Field(default_factory=dict, description="Current dimensions")
    session_id: str = Field(..., description="Session ID for continuation")
    turn_count: int = Field(default=0, description="Conversation turn count")
    trace_id: str = Field(..., description="Trace ID for correlation")
    feedback: Optional[str] = Field(default=None, description="Quality feedback for user")
