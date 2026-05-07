"""
Strategy protocols and implementations for RAG Service query pipeline.

This module defines Protocol-based interfaces for retrieval and quality
enhancement strategies. Strategies are selected by configuration and
injected into QueryCapability at runtime.

Protocols:
- RetrievalStrategy: Milvus | ExternalKB retrieval backend
- QualityStrategy: Basic | DimensionGather | Conversational quality mode

Implementations:
- MilvusRetrieval: Vector search via Milvus
- ExternalKBRetrieval: HTTP API to external knowledge base
- BasicQuality: Pass-through (no enhancement)
- DimensionGatherQuality: Multi-turn dimension gathering
- ConversationalQuality: Slot extraction and conversational query

API Reference:
- Location: src/rag_service/strategies/__init__.py
"""

from rag_service.strategies.retrieval import (
    RetrievalStrategy,
    MilvusRetrieval,
    ExternalKBRetrieval,
)
from rag_service.strategies.quality import (
    QualityStrategy,
    BasicQuality,
    DimensionGatherQuality,
    ConversationalQuality,
)

__all__ = [
    # Protocols
    "RetrievalStrategy",
    "QualityStrategy",
    # Retrieval implementations
    "MilvusRetrieval",
    "ExternalKBRetrieval",
    # Quality implementations
    "BasicQuality",
    "DimensionGatherQuality",
    "ConversationalQuality",
]
