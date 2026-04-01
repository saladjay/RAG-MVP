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
        from rag_service.core.logger import get_logger

        logger = get_logger(__name__)

        try:
            # Use LiteLLM Gateway for actual model discovery
            if self._litellm_client is None:
                from rag_service.inference.gateway import get_gateway
                self._litellm_client = await get_gateway()

            # Get available models from gateway
            available_models = self._litellm_client.get_available_models()

            models = []
            for model_data in available_models:
                model_id = model_data.get("model_id", "")
                provider = model_data.get("provider", "unknown")

                # Parse model name for display
                display_name = model_id
                if "gpt-3.5" in model_id:
                    display_name = "GPT-3.5 Turbo"
                elif "gpt-4" in model_id and "turbo" not in model_id:
                    display_name = "GPT-4"
                elif "gpt-4-turbo" in model_id:
                    display_name = "GPT-4 Turbo"
                elif "claude-3-opus" in model_id:
                    display_name = "Claude 3 Opus"
                elif "claude-3-sonnet" in model_id:
                    display_name = "Claude 3 Sonnet"
                elif "claude-3-haiku" in model_id:
                    display_name = "Claude 3 Haiku"
                elif "llama3" in model_id:
                    display_name = "Llama 3"

                # Estimate context length (simplified)
                context_length = 4096
                if "gpt-4" in model_id and "turbo" not in model_id:
                    context_length = 8192
                elif "gpt-4-turbo" in model_id:
                    context_length = 128000
                elif "claude-3" in model_id:
                    context_length = 200000

                models.append(ModelInfo(
                    id=model_id,
                    name=display_name,
                    provider=provider,
                    context_length=context_length,
                ))

            # Filter by provider if specified
            if input_data.provider:
                models = [m for m in models if m.provider == input_data.provider]

            providers = list(set(m.provider for m in models))

            logger.info(
                "Model discovery completed",
                extra={
                    "models_count": len(models),
                    "providers": providers,
                },
            )

            return ModelDiscoveryOutput(
                models=models,
                providers=providers,
                trace_id=input_data.trace_id,
                metadata={"detail_level": input_data.detail_level},
            )

        except Exception as e:
            logger.error(
                "Model discovery failed",
                extra={"error": str(e)},
            )
            # Return empty result on error
            return ModelDiscoveryOutput(
                models=[],
                providers=[],
                trace_id=input_data.trace_id,
                metadata={"error": str(e)},
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
                # Check available providers
                available_providers = self._litellm_client.get_available_providers()
                available_models = self._litellm_client.get_available_models()

                health["litellm"] = "connected"
                health["available_providers"] = available_providers
                health["available_models"] = len(available_models)
                health["status"] = "healthy" if available_providers else "degraded"

            except Exception as e:
                health["litellm"] = f"disconnected: {e}"
                health["status"] = "unhealthy"
        else:
            health["litellm"] = "not_configured"
            health["status"] = "degraded"

        return health
