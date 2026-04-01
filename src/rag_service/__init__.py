"""
rag_service: RAG Service MVP - AI Component Validation Platform

This package provides a RAG (Retrieval-Augmented Generation) service
for validating AI development components with comprehensive observability.

Core Architecture:
- Capability Interface Layer: Unified abstraction between HTTP endpoints and components
- Three-Layer Observability: LLM (LiteLLM) → Agent (Phidata) → Prompt (Langfuse)
- Unified Trace Propagation: trace_id flows across all layers

Components:
- FastAPI web service with async support
- Milvus vector database for knowledge storage
- LiteLLM gateway for multi-model inference
- Phidata agent orchestration
- Langfuse prompt management and tracing
"""

__version__ = "0.1.0"
