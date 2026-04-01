"""
External clients for RAG Service.

This package provides HTTP clients for external services including
the external knowledge base API.
"""

from rag_service.clients.external_kb_client import (
    ExternalKBChunk,
    ExternalKBClient,
    ExternalKBClientConfig,
    ExternalKBMetadata,
    ExternalKBRequest,
    ExternalKBResponse,
    close_external_kb_client,
    get_external_kb_client,
)

__all__ = [
    "ExternalKBClient",
    "ExternalKBClientConfig",
    "ExternalKBRequest",
    "ExternalKBResponse",
    "ExternalKBChunk",
    "ExternalKBMetadata",
    "get_external_kb_client",
    "close_external_kb_client",
]
