"""
Model Provider Configuration for RAG Service.

This module provides configuration classes for AI model providers.
It handles:
- Provider-specific settings
- Model availability and capabilities
- Cost tracking per provider
- Fallback chain configuration

API Reference:
- Location: src/rag_service/inference/models.py
- Classes: ModelProvider, ModelConfig, ProviderConfig
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum


class ProviderType(Enum):
    """Types of model providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    VLLM = "vllm"
    SGLANG = "sglang"
    CUSTOM = "custom"


@dataclass
class ModelCapabilities:
    """Capabilities of a model.

    Attributes:
        max_tokens: Maximum tokens for input/output
        supports_streaming: Whether streaming is supported
        supports_function_calling: Whether function calling is supported
        supports_vision: Whether vision/multimodal is supported
    """
    max_tokens: int = 4096
    supports_streaming: bool = True
    supports_function_calling: bool = False
    supports_vision: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "max_tokens": self.max_tokens,
            "supports_streaming": self.supports_streaming,
            "supports_function_calling": self.supports_function_calling,
            "supports_vision": self.supports_vision,
        }


@dataclass
class ModelConfig:
    """Configuration for a specific model.

    Attributes:
        model_id: Unique model identifier
        display_name: Human-readable name
        provider: Provider type
        capabilities: Model capabilities
        cost_per_input: Cost per 1M input tokens (USD)
        cost_per_output: Cost per 1M output tokens (USD)
        base_url: Optional custom endpoint
        api_key_env: Environment variable name for API key
    """
    model_id: str
    display_name: str
    provider: ProviderType
    capabilities: ModelCapabilities
    cost_per_input: float = 0.0
    cost_per_output: float = 0.0
    base_url: Optional[str] = None
    api_key_env: Optional[str] = None
    is_available: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "model_id": self.model_id,
            "display_name": self.display_name,
            "provider": self.provider.value,
            "capabilities": self.capabilities.to_dict(),
            "cost_per_input": self.cost_per_input,
            "cost_per_output": self.cost_per_output,
            "base_url": self.base_url,
            "is_available": self.is_available,
        }

    @property
    def full_model_id(self) -> str:
        """Get full model identifier with provider prefix.

        Returns:
            Full model ID (e.g., "ollama/llama3")
        """
        if self.provider == ProviderType.OLLAMA and not self.model_id.startswith("ollama/"):
            return f"ollama/{self.model_id}"
        return self.model_id


@dataclass
class ProviderConfig:
    """Configuration for a provider.

    Attributes:
        provider: Provider type
        name: Provider display name
        base_url: Default base URL for provider
        api_key_env: Environment variable for API key
        models: List of available models from this provider
    """
    provider: ProviderType
    name: str
    base_url: Optional[str] = None
    api_key_env: Optional[str] = None
    models: List[ModelConfig] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "provider": self.provider.value,
            "name": self.name,
            "base_url": self.base_url,
            "models": [m.to_dict() for m in self.models],
        }

    def get_model(self, model_id: str) -> Optional[ModelConfig]:
        """Get model configuration by ID.

        Args:
            model_id: Model identifier

        Returns:
            ModelConfig if found, None otherwise
        """
        for model in self.models:
            if model.model_id == model_id or model.full_model_id == model_id:
                return model
        return None


# Default model configurations
DEFAULT_MODELS = [
    # OpenAI models
    ModelConfig(
        model_id="gpt-4",
        display_name="GPT-4",
        provider=ProviderType.OPENAI,
        capabilities=ModelCapabilities(
            max_tokens=8192,
            supports_function_calling=True,
        ),
        cost_per_input=30.0,
        cost_per_output=60.0,
        api_key_env="OPENAI_API_KEY",
    ),
    ModelConfig(
        model_id="gpt-4-turbo",
        display_name="GPT-4 Turbo",
        provider=ProviderType.OPENAI,
        capabilities=ModelCapabilities(
            max_tokens=128000,
            supports_function_calling=True,
        ),
        cost_per_input=10.0,
        cost_per_output=30.0,
        api_key_env="OPENAI_API_KEY",
    ),
    ModelConfig(
        model_id="gpt-3.5-turbo",
        display_name="GPT-3.5 Turbo",
        provider=ProviderType.OPENAI,
        capabilities=ModelCapabilities(
            max_tokens=16385,
            supports_function_calling=True,
        ),
        cost_per_input=0.5,
        cost_per_output=1.5,
        api_key_env="OPENAI_API_KEY",
    ),

    # Anthropic models
    ModelConfig(
        model_id="claude-3-opus-20040229",
        display_name="Claude 3 Opus",
        provider=ProviderType.ANTHROPIC,
        capabilities=ModelCapabilities(
            max_tokens=200000,
            supports_function_calling=True,
            supports_vision=True,
        ),
        cost_per_input=15.0,
        cost_per_output=75.0,
        api_key_env="ANTHROPIC_API_KEY",
    ),
    ModelConfig(
        model_id="claude-3-sonnet-20240229",
        display_name="Claude 3 Sonnet",
        provider=ProviderType.ANTHROPIC,
        capabilities=ModelCapabilities(
            max_tokens=200000,
            supports_function_calling=True,
            supports_vision=True,
        ),
        cost_per_input=3.0,
        cost_per_output=15.0,
        api_key_env="ANTHROPIC_API_KEY",
    ),
    ModelConfig(
        model_id="claude-3-haiku-20240307",
        display_name="Claude 3 Haiku",
        provider=ProviderType.ANTHROPIC,
        capabilities=ModelCapabilities(
            max_tokens=200000,
            supports_function_calling=False,
        ),
        cost_per_input=0.25,
        cost_per_output=1.25,
        api_key_env="ANTHROPIC_API_KEY",
    ),

    # Ollama models
    ModelConfig(
        model_id="llama3",
        display_name="Llama 3",
        provider=ProviderType.OLLAMA,
        capabilities=ModelCapabilities(
            max_tokens=8192,
            supports_function_calling=False,
        ),
        base_url="http://localhost:11434",
    ),
    ModelConfig(
        model_id="mistral",
        display_name="Mistral 7B",
        provider=ProviderType.OLLAMA,
        capabilities=ModelCapabilities(
            max_tokens=8192,
            supports_function_calling=False,
        ),
        base_url="http://localhost:11434",
    ),
]


# Default provider configurations
DEFAULT_PROVIDERS = [
    ProviderConfig(
        provider=ProviderType.OPENAI,
        name="OpenAI",
        base_url="https://api.openai.com/v1",
        api_key_env="OPENAI_API_KEY",
        models=[m for m in DEFAULT_MODELS if m.provider == ProviderType.OPENAI],
    ),
    ProviderConfig(
        provider=ProviderType.ANTHROPIC,
        name="Anthropic",
        base_url="https://api.anthropic.com/v1",
        api_key_env="ANTHROPIC_API_KEY",
        models=[m for m in DEFAULT_MODELS if m.provider == ProviderType.ANTHROPIC],
    ),
    ProviderConfig(
        provider=ProviderType.OLLAMA,
        name="Ollama",
        base_url="http://localhost:11434",
        models=[m for m in DEFAULT_MODELS if m.provider == ProviderType.OLLAMA],
    ),
]


def get_all_models() -> List[ModelConfig]:
    """Get all default model configurations.

    Returns:
        List of ModelConfig objects
    """
    return DEFAULT_MODELS.copy()


def get_model_by_id(model_id: str) -> Optional[ModelConfig]:
    """Get model configuration by ID.

    Args:
        model_id: Model identifier

    Returns:
        ModelConfig if found, None otherwise
    """
    for model in DEFAULT_MODELS:
        if model.model_id == model_id or model.full_model_id == model_id:
            return model
    return None


def get_provider_by_type(provider_type: ProviderType) -> Optional[ProviderConfig]:
    """Get provider configuration by type.

    Args:
        provider_type: Provider type enum

    Returns:
        ProviderConfig if found, None otherwise
    """
    for provider in DEFAULT_PROVIDERS:
        if provider.provider == provider_type:
            return provider
    return None


def get_available_providers() -> List[ProviderConfig]:
    """Get list of available providers (with API keys configured).

    Returns:
        List of ProviderConfig objects that are configured
    """
    import os

    available = []
    for provider in DEFAULT_PROVIDERS:
        if provider.api_key_env:
            if os.getenv(provider.api_key_env):
                available.append(provider)
        else:
            # No API key required (e.g., local Ollama)
            available.append(provider)

    return available
