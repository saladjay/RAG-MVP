"""
Capabilities package - Unified capability interface layer.

This package provides the CORE ARCHITECTURE of the RAG service.
All HTTP endpoints interact ONLY with capability interfaces,
never directly with underlying components.

This enables:
- Component swapping without API changes
- Clean abstraction boundaries
- Testable interfaces with real or mocked implementations
"""

from rag_service.capabilities.base import Capability
from rag_service.capabilities.knowledge_query import KnowledgeQueryCapability
from rag_service.capabilities.model_inference import ModelInferenceCapability
from rag_service.capabilities.trace_observation import TraceObservationCapability
from rag_service.capabilities.document_management import DocumentManagementCapability
from rag_service.capabilities.model_discovery import ModelDiscoveryCapability
from rag_service.capabilities.health_check import HealthCheckCapability

__all__ = [
    "Capability",
    "KnowledgeQueryCapability",
    "ModelInferenceCapability",
    "TraceObservationCapability",
    "DocumentManagementCapability",
    "ModelDiscoveryCapability",
    "HealthCheckCapability",
]
