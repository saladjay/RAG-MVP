"""
Capabilities package - Unified capability interface layer.

This package provides the core architecture of the RAG service.
All HTTP endpoints interact ONLY with capability interfaces,
never directly with underlying components.

3 Unified Capabilities:
- QueryCapability: Unified query pipeline with strategy switching
- ManagementCapability: Document management and model discovery
- TraceCapability: Health checks and trace observation
"""

from rag_service.capabilities.base import Capability
from rag_service.capabilities.query_capability import QueryCapability
from rag_service.capabilities.management_capability import ManagementCapability
from rag_service.capabilities.trace_capability import TraceCapability

__all__ = [
    "Capability",
    "QueryCapability",
    "ManagementCapability",
    "TraceCapability",
]
