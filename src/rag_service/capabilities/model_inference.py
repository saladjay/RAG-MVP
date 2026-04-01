"""
Model Inference Capability for RAG Service.

This capability provides unified access to LLM inference operations
via the LiteLLM gateway. HTTP endpoints use this capability - they
NEVER access LiteLLM directly.
"""

import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator

from rag_service.capabilities.base import (
    Capability,
    CapabilityInput,
    CapabilityOutput,
    CapabilityValidationResult,
)
from rag_service.core.exceptions import GenerationError
from rag_service.core.logger import get_logger

logger = get_logger(__name__)


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
        start_time = time.time()
        model = input_data.model or self._default_model

        try:
            # Use LiteLLM Gateway for actual inference
            if self._litellm_client is None:
                # Import gateway if not provided
                from rag_service.inference.gateway import get_gateway
                self._litellm_client = await get_gateway()

            # Call async completion
            result = await self._litellm_client.acomplete(
                prompt=input_data.prompt,
                model_hint=model,
                max_tokens=input_data.max_tokens,
                temperature=input_data.temperature,
            )

            elapsed_ms = (time.time() - start_time) * 1000

            logger.info(
                "Model inference completed",
                extra={
                    "trace_id": input_data.trace_id,
                    "model": result.model,
                    "provider": result.provider,
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                    "latency_ms": elapsed_ms,
                },
            )

            return ModelInferenceOutput(
                text=result.text,
                model=result.model,
                usage={
                    "prompt_tokens": result.input_tokens,
                    "completion_tokens": result.output_tokens,
                    "total_tokens": result.total_tokens,
                    "cost": result.cost,
                },
                inference_time_ms=elapsed_ms,
                trace_id=input_data.trace_id,
                metadata={
                    "temperature": input_data.temperature,
                    "provider": result.provider,
                },
            )

        except Exception as e:
            logger.error(
                "Model inference failed",
                extra={
                    "trace_id": input_data.trace_id,
                    "model": model,
                    "error": str(e),
                },
            )
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
                # Check if gateway has available models
                available_models = self._litellm_client.get_available_models()
                available_providers = self._litellm_client.get_available_providers()

                health["litellm"] = "connected"
                health["available_models"] = len(available_models)
                health["available_providers"] = available_providers
                health["status"] = "healthy" if available_providers else "degraded"

            except Exception as e:
                health["litellm"] = f"disconnected: {e}"
                health["status"] = "unhealthy"
        else:
            health["litellm"] = "not_configured"
            health["status"] = "degraded"

        return health
