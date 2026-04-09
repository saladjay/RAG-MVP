"""
Inference package - LLM inference services.

This package provides components for:
- LiteLLM gateway interface (multi-provider LLM access)
- HTTP completion gateway (direct cloud API calls)
- GLM completion gateway (智谱AI BigModel API)
- Model provider configuration

NOTE: These are INTERNAL components, accessed via Capability interfaces only.
"""

from rag_service.inference.gateway import (
    LiteLLMGateway,
    HTTPCompletionGateway,
    GLMCompletionGateway,
    CompletionResult,
    ModelConfig,
    get_gateway,
    get_http_gateway,
    get_glm_gateway,
    reset_gateway,
    reset_http_gateway,
    reset_glm_gateway,
)

__all__ = [
    "LiteLLMGateway",
    "HTTPCompletionGateway",
    "GLMCompletionGateway",
    "CompletionResult",
    "ModelConfig",
    "get_gateway",
    "get_http_gateway",
    "get_glm_gateway",
    "reset_gateway",
    "reset_http_gateway",
    "reset_glm_gateway",
]
