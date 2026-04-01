"""
Model Discovery Capability for RAG Service.

This capability provides unified access to available models and
model provider information. HTTP endpoints use this capability -
they NEVER access LiteLLM directly.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from rag_service.capabilities.base import (
    Capability,
    CapabilityInput,
    CapabilityOutput,
    CapabilityValidationResult,
)


class ModelDiscoveryInput(CapabilityInput):
    """
    Input for model discovery operations.

    Attributes:
        provider: Optional provider filter.
        detail_level: Level of detail (basic, detailed).
    """

    provider: str = Field(default="", description="Provider filter (optional)")
    detail_level: str = Field(default="basic", description="Detail level")


class ModelInfo(BaseModel):
    """
    Information about an available model.

    Attributes:
        id: Model identifier.
        name: Model display name.
        provider: Model provider.
        context_length: Maximum context length.
    """

    id: str = Field(..., description="Model identifier")
    name: str = Field(..., description="Model display name")
    provider: str = Field(..., description="Model provider")
    context_length: int = Field(default=4096, description="Max context length")


class ModelDiscoveryOutput(CapabilityOutput):
    """
    Output from model discovery operations.

    Attributes:
        models: List of available models.
        providers: List of available providers.
    """

    models: List[ModelInfo] = Field(default_factory=list, description="Available models")
    providers: List[str] = Field(default_factory=list, description="Available providers")


class ModelDiscoveryCapability(Capability[ModelDiscoveryInput, ModelDiscoveryOutput]):
    """
    Capability for model discovery.

    This capability wraps LiteLLM model discovery and provides
    a unified interface for listing available models. HTTP endpoints
    use this capability - they NEVER access LiteLLM directly.

    Features:
    - List all available models
    - Filter by provider
    - Model information retrieval
    """

    def __init__(self, litellm_client: Optional[Any] = None) -> None:
        """
        Initialize ModelDiscoveryCapability.

        Args:
            litellm_client: LiteLLM client instance (injected dependency).
        """
        super().__init__()
        self._litellm_client = litellm_client

    async def execute(self, input_data: ModelDiscoveryInput) -> ModelDiscoveryOutput:
        """
        Execute model discovery.

        Args:
            input_data: Model discovery parameters.

        Returns:
            Available models and providers.
        """
        # TODO: Implement actual LiteLLM model list
        # For now, return mock output
        models = [
            ModelInfo(
                id="gpt-3.5-turbo",
                name="GPT-3.5 Turbo",
                provider="openai",
                context_length=4096,
            ),
            ModelInfo(
                id="gpt-4",
                name="GPT-4",
                provider="openai",
                context_length=8192,
            ),
        ]

        # Filter by provider if specified
        if input_data.provider:
            models = [m for m in models if m.provider == input_data.provider]

        providers = list(set(m.provider for m in models))

        return ModelDiscoveryOutput(
            models=models,
            providers=providers,
            trace_id=input_data.trace_id,
            metadata={"detail_level": input_data.detail_level},
        )

    def validate_input(self, input_data: ModelDiscoveryInput) -> CapabilityValidationResult:
        """
        Validate model discovery input.

        Args:
            input_data: Input to validate.

        Returns:
            Validation result.
        """
        errors = []

        # Validate detail_level
        valid_levels = {"basic", "detailed"}
        if input_data.detail_level not in valid_levels:
            errors.append(f"detail_level must be one of {valid_levels}")

        return CapabilityValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
        )

    def get_health(self) -> Dict[str, Any]:
        """
        Get health status of model discovery.

        Returns:
            Health status information.
        """
        health = super().get_health()

        # Check LiteLLM connectivity
        if self._litellm_client:
            try:
                # TODO: Implement actual health check
                health["litellm"] = "connected"
            except Exception as e:
                health["litellm"] = f"disconnected: {e}"
                health["status"] = "degraded"
        else:
            health["litellm"] = "not_configured"

        return health
