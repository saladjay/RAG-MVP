"""
RAG Service Services Module.

This module provides service layer components for RAG operations.
"""

from rag_service.services.prompt_client import (
    PromptClient,
    get_prompt_client,
    reset_prompt_client,
    TEMPLATE_QUERY_REWRITE,
    TEMPLATE_ANSWER_GENERATION,
    TEMPLATE_ANSWER_GENERATION_STRICT,
    TEMPLATE_HALLUCINATION_DETECTION,
    TEMPLATE_RAG_AGENT_INSTRUCTIONS,
    TEMPLATE_FALLBACK_RESPONSE,
)

__all__ = [
    "PromptClient",
    "get_prompt_client",
    "reset_prompt_client",
    "TEMPLATE_QUERY_REWRITE",
    "TEMPLATE_ANSWER_GENERATION",
    "TEMPLATE_ANSWER_GENERATION_STRICT",
    "TEMPLATE_HALLUCINATION_DETECTION",
    "TEMPLATE_RAG_AGENT_INSTRUCTIONS",
    "TEMPLATE_FALLBACK_RESPONSE",
]
