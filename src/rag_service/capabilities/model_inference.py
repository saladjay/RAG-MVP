"""
Model Inference Capability for RAG Service.

This capability provides unified access to LLM inference operations
via the LiteLLM gateway. HTTP endpoints use this capability - they
NEVER access LiteLLM directly.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator

from rag_service.capabilities.base import (
    Capability,
    CapabilityInput,
    CapabilityOutput,
    CapabilityValidationResult,
)
from rag_service.core.exceptions import GenerationError


class ModelInferenceInput(CapabilityInput):
    """
    Input for model inference operations.

    Attributes:
        prompt: The prompt to send to the model.
        model: Model identifier (uses default if not specified).
        max_tokens: Maximum tokens in response.
        temperature: Sampling temperature.
        context: Optional context information.
    """

    prompt: str = Field(..., min_length=1, description="Prompt for the model")
    model: Optional[str] = Field(default=None, description="Model identifier")
    max_tokens: int = Field(default=1000, ge=1, le=32000, description="Max tokens")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    context: Optional[str] = Field(default=None, description="Additional context")

    @model_validator(mode="after")
    def validate_prompt_not_empty(self) -> "ModelInferenceInput":
        """Validate prompt is not just whitespace."""
        if not self.prompt.strip():
            raise ValueError("Prompt cannot be empty or whitespace")
        return self


class ModelInferenceOutput(CapabilityOutput):
    """
    Output from model inference operations.

    Attributes:
        text: Generated text response.
        model: Model used for generation.
        usage: Token usage information.
        inference_time_ms: Time taken for inference.
    """

    text: str = Field(default="", description="Generated text")
    model: str = Field(..., description="Model used")
    usage: Dict[str, int] = Field(default_factory=dict, description="Token usage")
    inference_time_ms: Optional[float] = Field(default=None, description="Inference time")


class ModelInferenceCapability(Capability[ModelInferenceInput, ModelInferenceOutput]):
    """
    Capability for LLM model inference.

    This capability wraps LiteLLM gateway operations and provides
    a unified interface for model inference. HTTP endpoints use this
    capability to access LiteLLM - they NEVER access LiteLLM directly.

    Features:
    - Multi-model support via LiteLLM
    - Configurable generation parameters
    - Token usage tracking
    - Performance monitoring
    """

    def __init__(self, litellm_client: Optional[Any] = None, default_model: str = "gpt-3.5-turbo") -> None:
        """
        Initialize ModelInferenceCapability.

        Args:
            litellm_client: LiteLLM client instance (injected dependency).
            default_model: Default model to use if not specified.
        """
        super().__init__()
        self._litellm_client = litellm_client
        self._default_model = default_model

    async def execute(self, input_data: ModelInferenceInput) -> ModelInferenceOutput:
        """
        Execute model inference.

        Args:
            input_data: Inference parameters.

        Returns:
            Generated text with usage information.

        Raises:
            GenerationError: If inference fails.
        """
        import time

        start_time = time.time()
        model = input_data.model or self._default_model

        # TODO: Implement actual LiteLLM call
        try:
            # Mock implementation
            generated_text = f"Mock response for prompt: {input_data.prompt[:50]}..."
            usage = {
                "prompt_tokens": len(input_data.prompt.split()),
                "completion_tokens": 20,
                "total_tokens": len(input_data.prompt.split()) + 20,
            }

            elapsed_ms = (time.time() - start_time) * 1000

            return ModelInferenceOutput(
                text=generated_text,
                model=model,
                usage=usage,
                inference_time_ms=elapsed_ms,
                trace_id=input_data.trace_id,
                metadata={"temperature": input_data.temperature},
            )

        except Exception as e:
            raise GenerationError(
                message=f"Inference failed with model '{model}'",
                detail=str(e),
            ) from e

    def validate_input(self, input_data: ModelInferenceInput) -> CapabilityValidationResult:
        """
        Validate model inference input.

        Args:
            input_data: Input to validate.

        Returns:
            Validation result.
        """
        errors = []
        warnings = []

        # Validate prompt
        if not input_data.prompt or not input_data.prompt.strip():
            errors.append("Prompt cannot be empty")

        # Validate max_tokens
        if input_data.max_tokens < 1:
            errors.append("max_tokens must be positive")
        elif input_data.max_tokens > 32000:
            warnings.append("max_tokens > 32000 may not be supported")

        # Validate temperature
        if not 0.0 <= input_data.temperature <= 2.0:
            errors.append("Temperature must be between 0.0 and 2.0")

        return CapabilityValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def get_health(self) -> Dict[str, Any]:
        """
        Get health status of model inference.

        Returns:
            Health status information.
        """
        health = super().get_health()
        health["default_model"] = self._default_model

        # Check LiteLLM connectivity
        if self._litellm_client:
            try:
                # TODO: Implement actual health check
                health["litellm"] = "connected"
            except Exception as e:
                health["litellm"] = f"disconnected: {e}"
                health["status"] = "unhealthy"
        else:
            health["litellm"] = "not_configured"
            health["status"] = "degraded"

        return health
