"""
LiteLLM Gateway for RAG Service.

This module provides unified multi-model inference via LiteLLM.
It handles:
- Multi-provider model access (OpenAI, Anthropic, Ollama, etc.)
- Model selection and routing
- Cost tracking and optimization
- Error handling and fallback

API Reference:
- Location: src/rag_service/inference/gateway.py
- Class: LiteLLMGateway
- Method: complete() -> Generate model completion
- Method: get_available_models() -> List configured models
"""

import asyncio
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, field
from datetime import datetime
import os

from rag_service.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CompletionResult:
    """Result from model completion.

    Attributes:
        text: Generated text response
        model: Model identifier used
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        total_tokens: Total tokens used
        cost: Estimated cost in USD
        latency_ms: Request latency in milliseconds
        provider: Provider identifier
    """
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost: float
    latency_ms: float
    provider: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "text": self.text,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cost": self.cost,
            "latency_ms": self.latency_ms,
            "provider": self.provider,
        }


@dataclass
class ModelConfig:
    """Configuration for a model.

    Attributes:
        model_id: Model identifier
        provider: Provider name
        base_url: Optional custom endpoint URL
        api_key: Optional API key
        cost_per_input: Cost per 1M input tokens
        cost_per_output: Cost per 1M output tokens
    """
    model_id: str
    provider: str
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    cost_per_input: float = 0.0
    cost_per_output: float = 0.0


class LiteLLMGateway:
    """
    Gateway for multi-model inference using LiteLLM.

    This gateway provides a unified interface for accessing multiple
    LLM providers through LiteLLM, including:
    - OpenAI (GPT-4, GPT-3.5)
    - Anthropic (Claude)
    - Local models via Ollama
    - Other OpenAI-compatible endpoints

    Attributes:
        config_path: Path to litellm config file
        models: Dictionary of available model configurations
        default_model: Default model to use
        fallback_models: Fallback models in order
    """

    # Approximate costs per 1M tokens (USD)
    MODEL_COSTS = {
        "gpt-4": {"input": 30.0, "output": 60.0},
        "gpt-4-turbo": {"input": 10.0, "output": 30.0},
        "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
        "claude-3-opus": {"input": 15.0, "output": 75.0},
        "claude-3-sonnet": {"input": 3.0, "output": 15.0},
        "claude-3-haiku": {"input": 0.25, "output": 1.25},
    }

    def __init__(
        self,
        config_path: Optional[str] = None,
        default_model: str = "gpt-3.5-turbo",
        fallback_models: Optional[List[str]] = None,
    ):
        """Initialize the LiteLLM gateway.

        Args:
            config_path: Optional path to litellm config YAML file
            default_model: Default model identifier
            fallback_models: Ordered list of fallback models
        """
        self.config_path = config_path
        self.default_model = default_model
        self.fallback_models = fallback_models or [
            "gpt-3.5-turbo",
            "claude-3-haiku",
        ]

        # Initialize models from config or defaults
        self.models: Dict[str, ModelConfig] = {}
        self._init_models()

        logger.info(
            "Initialized LiteLLM gateway",
            extra={
                "default_model": default_model,
                "models_count": len(self.models),
            },
        )

    def _init_models(self) -> None:
        """Initialize model configurations.

        Loads from config file or uses environment-based defaults.
        """
        if self.config_path and os.path.exists(self.config_path):
            self._load_config_from_file(self.config_path)
        else:
            self._init_default_models()

    def _load_config_from_file(self, config_path: str) -> None:
        """Load model configurations from YAML file.

        Args:
            config_path: Path to litellm config YAML
        """
        try:
            import yaml

            with open(config_path, "r") as f:
                config = yaml.safe_load(f)

            for model_config in config.get("model_list", []):
                model_name = model_config.get("model_name")
                litellm_params = model_config.get("litellm_params", {})

                self.models[model_name] = ModelConfig(
                    model_id=model_name,
                    provider=self._extract_provider(model_name),
                    base_url=litellm_params.get("api_base"),
                    api_key=litellm_params.get("api_key"),
                )

            logger.info(
                f"Loaded {len(self.models)} models from config",
                extra={"config_path": config_path},
            )

        except Exception as e:
            logger.warning(f"Failed to load config file: {e}, using defaults")
            self._init_default_models()

    def _init_default_models(self) -> None:
        """Initialize default model configurations from environment."""
        # Check for common model providers via environment variables
        if os.getenv("OPENAI_API_KEY"):
            self.models["gpt-4"] = ModelConfig(
                model_id="gpt-4",
                provider="openai",
            )
            self.models["gpt-3.5-turbo"] = ModelConfig(
                model_id="gpt-3.5-turbo",
                provider="openai",
            )

        if os.getenv("ANTHROPIC_API_KEY"):
            self.models["claude-3-opus"] = ModelConfig(
                model_id="claude-3-opus-20040229",
                provider="anthropic",
            )
            self.models["claude-3-sonnet"] = ModelConfig(
                model_id="claude-3-sonnet-20240229",
                provider="anthropic",
            )
            self.models["claude-3-haiku"] = ModelConfig(
                model_id="claude-3-haiku-20240307",
                provider="anthropic",
            )

        # Check for Ollama
        ollama_base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.models["ollama/llama3"] = ModelConfig(
            model_id="ollama/llama3",
            provider="ollama",
            base_url=ollama_base,
        )

    def _extract_provider(self, model_id: str) -> str:
        """Extract provider name from model ID.

        Args:
            model_id: Model identifier

        Returns:
            Provider name
        """
        if model_id.startswith("ollama/"):
            return "ollama"
        elif model_id.startswith("vllm/"):
            return "vllm"
        elif model_id.startswith("sglang/"):
            return "sglang"
        elif "gpt" in model_id.lower():
            return "openai"
        elif "claude" in model_id.lower():
            return "anthropic"
        else:
            return "unknown"

    def select_provider_model(
        self,
        model_hint: Optional[str] = None,
        required_provider: Optional[str] = None,
    ) -> tuple[str, str]:
        """
        Select appropriate provider and model based on hint and availability.

        Args:
            model_hint: Optional model hint from user request
            required_provider: Optional required provider filter

        Returns:
            Tuple of (selected_model, provider_name)

        Raises:
            ValueError: If no suitable model found
        """
        # If model_hint specified, try to use it
        if model_hint:
            # Check if model is configured
            if model_hint in self.models or model_hint in [m.model_id for m in self.models.values()]:
                provider = self._extract_provider(model_hint)
                return model_hint, provider
            else:
                logger.warning(
                    "Model hint not configured, using fallback",
                    extra={"model_hint": model_hint}
                )

        # Check if required provider is specified
        if required_provider:
            matching_models = [
                m for m in self.models.values()
                if m.provider == required_provider
            ]
            if matching_models:
                return matching_models[0].model_id, required_provider

        # Use default model
        default_provider = self._extract_provider(self.default_model)
        return self.default_model, default_provider

    def check_provider_availability(self, provider: str) -> bool:
        """
        Check if a provider is available (has credentials or is local).

        Args:
            provider: Provider name (openai, anthropic, ollama, etc.)

        Returns:
            True if provider is available
        """
        import os

        # Check API key for cloud providers
        if provider == "openai":
            return bool(os.getenv("OPENAI_API_KEY"))
        elif provider == "anthropic":
            return bool(os.getenv("ANTHROPIC_API_KEY"))
        elif provider in ["ollama", "vllm", "sglang"]:
            # Local providers - assume available if configured
            return True
        else:
            return False

    def get_available_providers(self) -> List[str]:
        """
        Get list of available providers.

        Returns:
            List of provider names that are available
        """
        providers = set()
        for model in self.models.values():
            if self.check_provider_availability(model.provider):
                providers.add(model.provider)

        return sorted(list(providers))


    def _estimate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Estimate cost for model usage.

        Args:
            model: Model identifier
            input_tokens: Input token count
            output_tokens: Output token count

        Returns:
            Estimated cost in USD
        """
        # Find matching cost table entry
        model_key = next(
            (k for k in self.MODEL_COSTS if k in model.lower()),
            None,
        )

        if model_key:
            costs = self.MODEL_COSTS[model_key]
            input_cost = (input_tokens / 1_000_000) * costs["input"]
            output_cost = (output_tokens / 1_000_000) * costs["output"]
            return input_cost + output_cost

        return 0.0

    def complete(
        self,
        prompt: str,
        model_hint: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs,
    ) -> CompletionResult:
        """
        Generate model completion.

        Args:
            prompt: Input prompt
            model_hint: Optional model hint for selection
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional model parameters

        Returns:
            CompletionResult with generated text and metadata

        Raises:
            RuntimeError: If all models fail
        """
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty")

        # Select model
        model = model_hint or self.default_model

        start_time = asyncio.get_event_loop().time()

        try:
            from litellm import completion

            # Prepare parameters
            params = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
                **kwargs,
            }

            # Call LiteLLM
            response = completion(**params)

            # Extract result
            text = response.choices[0].message.content
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            total_tokens = input_tokens + output_tokens

            # Calculate cost
            cost = self._estimate_cost(model, input_tokens, output_tokens)

            latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000

            result = CompletionResult(
                text=text,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cost=cost,
                latency_ms=latency_ms,
                provider=self._extract_provider(model),
            )

            logger.info(
                "Model completion successful",
                extra={
                    "model": model,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "latency_ms": latency_ms,
                    "cost": cost,
                },
            )

            return result

        except Exception as e:
            logger.error(
                "Model completion failed",
                extra={
                    "model": model,
                    "error": str(e),
                },
            )

            # Try fallback models
            if model not in self.fallback_models:
                for fallback_model in self.fallback_models:
                    if fallback_model != model:
                        logger.info(f"Trying fallback model: {fallback_model}")
                        try:
                            return self.complete(
                                prompt,
                                model_hint=fallback_model,
                                max_tokens=max_tokens,
                                temperature=temperature,
                                **kwargs,
                            )
                        except Exception:
                            continue

            raise RuntimeError(f"All models failed. Last error: {e}")

    async def acomplete(
        self,
        prompt: str,
        model_hint: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs,
    ) -> CompletionResult:
        """
        Async version of complete.

        Args:
            prompt: Input prompt
            model_hint: Optional model hint
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional model parameters

        Returns:
            CompletionResult with generated text and metadata
        """
        # Run blocking complete in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.complete,
            prompt,
            model_hint,
            max_tokens,
            temperature,
            kwargs,
        )

    def get_available_models(self) -> List[Dict[str, Any]]:
        """
        Get list of available models.

        Returns:
            List of model configurations
        """
        return [
            {
                "model_id": config.model_id,
                "provider": config.provider,
                "available": True,
            }
            for config in self.models.values()
        ]


# Global singleton instance
_gateway: Optional[LiteLLMGateway] = None
_gateway_lock = asyncio.Lock()


async def get_gateway() -> LiteLLMGateway:
    """Get or create the global gateway singleton.

    Returns:
        The global LiteLLMGateway instance
    """
    global _gateway

    async with _gateway_lock:
        if _gateway is None:
            # Read configuration from environment
            import os

            config_path = os.getenv("LITELLM_CONFIG_PATH")
            default_model = os.getenv("DEFAULT_MODEL", "gpt-3.5-turbo")

            _gateway = LiteLLMGateway(
                config_path=config_path,
                default_model=default_model,
            )
            logger.info("Initialized global LiteLLM gateway")

    return _gateway


def reset_gateway() -> None:
    """Reset the global gateway instance.

    This is primarily used for testing to ensure clean state between tests.
    """
    global _gateway
    _gateway = None
    logger.debug("Reset global LiteLLM gateway")
