"""
RAG Service Services Module.

This module provides service layer components for RAG operations.
"""

from rag_service.services.belief_state_store import (
    BeliefStateStoreService,
    get_belief_state_store,
)
from rag_service.services.colloquial_mapper import (
    ColloquialMapperService,
    get_colloquial_mapper,
)
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
from rag_service.services.session_store import (
    SessionStoreService,
    get_session_store,
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
    "SessionStoreService",
    "get_session_store",
    "BeliefStateStoreService",
    "get_belief_state_store",
    "ColloquialMapperService",
    "get_colloquial_mapper",
]
