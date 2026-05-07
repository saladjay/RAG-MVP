"""
RAG Service data models.

This package contains all data models used across the RAG service,
including query quality enhancement, conversational query enhancement,
QA pipeline, and capabilities.
"""

from rag_service.models.conversational_query import (
    BusinessDomain,
    ColloquialTermMapping,
    ContentElements,
    ConversationalQueryRequest,
    ConversationalQueryResponse,
    DocumentElements,
    ExtractedQueryElements,
    BeliefState,
    QueryGenerationResult,
    QueryType,
    TemporalElements,
    QuantityElements,
    SpatialElements,
)
from rag_service.models.query_quality import (
    DimensionAnalysisResult,
    DimensionInfo,
    DimensionStatus,
    DimensionType,
    DocumentType,
    KnowledgeBaseRoute,
    Organization,
    QueryQualityRequest,
    QueryQualityResponse,
    SessionState,
    SubjectCategory,
    FileType,
)

__all__ = [
    # Query Quality models
    "DimensionType",
    "DimensionStatus",
    "DimensionInfo",
    "DimensionAnalysisResult",
    "SessionState",
    "KnowledgeBaseRoute",
    "DocumentType",
    "Organization",
    "SubjectCategory",
    "FileType",
    "QueryQualityRequest",
    "QueryQualityResponse",
    # Conversational Query models
    "QueryType",
    "BusinessDomain",
    "TemporalElements",
    "SpatialElements",
    "DocumentElements",
    "ContentElements",
    "QuantityElements",
    "ExtractedQueryElements",
    "BeliefState",
    "QueryGenerationResult",
    "ColloquialTermMapping",
    "ConversationalQueryRequest",
    "ConversationalQueryResponse",
]

