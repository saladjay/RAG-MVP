"""
Inference Gateways for RAG Service.

This module provides unified model inference via LiteLLM as the sole entry point.
HTTP Cloud and GLM are internal provider implementations within LiteLLMGateway,
not separate Gateways that callers must choose between.

Gateways (all accessed via get_gateway()):
- LiteLLMGateway: Unified inference gateway with internal provider routing
  - Standard LiteLLM providers (OpenAI, Anthropic, Ollama, etc.)
  - Internal cloud_http provider (HTTPCompletionGateway)
  - Internal glm provider (GLMCompletionGateway)
  - Internal embedding (HTTPEmbeddingGateway)

Configuration:
- LITELLM_PROVIDER: "openai" | "cloud_http" | "glm" (default: "openai")
- Old DEFAULT_GATEWAY env var is mapped automatically

API Reference:
- Location: src/rag_service/inference/gateway.py
"""

import asyncio
import json
import time
from typing import List, Dict, Any, Optional, Union, AsyncGenerator, Iterator
from dataclasses import dataclass, field
from datetime import datetime
import os

import httpx

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
        model_id: Model identifier (friendly name)
        litellm_model: Actual model name to pass to litellm (e.g., "openai/glm-4.5-air")
        provider: Provider name
        base_url: Optional custom endpoint URL
        api_key: Optional API key
        cost_per_input: Cost per 1M input tokens
        cost_per_output: Cost per 1M output tokens
    """
    model_id: str
    litellm_model: Optional[str] = None  # If None, use model_id
    provider: str = "unknown"
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    cost_per_input: float = 0.0
    cost_per_output: float = 0.0

    def get_model_for_litellm(self) -> str:
        """Get the actual model name to use for litellm calls."""
        return self.litellm_model or self.model_id


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
        provider: Optional[str] = None,
    ):
        """Initialize the LiteLLM gateway.

        Args:
            config_path: Optional path to litellm config YAML file
            default_model: Default model identifier
            fallback_models: Ordered list of fallback models
            provider: Internal provider to route to ("openai", "cloud_http", "glm").
                      If None, uses LiteLLM's standard routing.
        """
        self.config_path = config_path
        self.default_model = default_model
        self.fallback_models = fallback_models or [
            "gpt-3.5-turbo",
            "claude-3-haiku",
        ]
        self._provider = provider or "openai"

        # Internal provider instances (lazy-initialized)
        self._http_gateway: Optional['HTTPCompletionGateway'] = None
        self._glm_gateway: Optional['GLMCompletionGateway'] = None
        self._embedding_gateway: Optional['HTTPEmbeddingGateway'] = None

        # Initialize models from config or defaults
        self.models: Dict[str, ModelConfig] = {}
        self._init_models()

        logger.info(
            "Initialized LiteLLM gateway",
            extra={
                "default_model": default_model,
                "provider": self._provider,
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
            import os

            with open(config_path, "r") as f:
                config = yaml.safe_load(f)

            for model_config in config.get("model_list", []):
                model_name = model_config.get("model_name")
                litellm_params = model_config.get("litellm_params", {})

                # Get the actual model name for litellm (e.g., "openai/glm-4.5-air")
                litellm_model = litellm_params.get("model", model_name)

                # Expand environment variables in api_key
                api_key = litellm_params.get("api_key", "")
                if api_key and "${" in api_key:
                    # Expand ${VAR_NAME} format
                    var_name = api_key.split("${")[1].split("}")[0]
                    api_key = os.getenv(var_name, api_key)

                self.models[model_name] = ModelConfig(
                    model_id=model_name,
                    litellm_model=litellm_model,
                    provider=self._extract_provider(litellm_model),
                    base_url=litellm_params.get("api_base"),
                    api_key=api_key,
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

    # ----------------------------------------------------------------
    # Internal provider routing
    # ----------------------------------------------------------------

    @property
    def provider(self) -> str:
        """Get the active internal provider name."""
        return self._provider

    def _get_http_gateway(self) -> 'HTTPCompletionGateway':
        """Get or create the internal HTTP Cloud provider."""
        if self._http_gateway is None:
            from rag_service.config import get_settings
            settings = get_settings()
            p = settings.litellm.cloud_http
            if p is None:
                raise RuntimeError("Cloud HTTP provider not configured")
            self._http_gateway = HTTPCompletionGateway(
                url=p.url,
                model=p.model,
                timeout=p.timeout,
                auth_token=p.auth_token,
                max_retries=p.max_retries,
                retry_delay=p.retry_delay,
            )
        return self._http_gateway

    def _get_glm_gateway(self) -> 'GLMCompletionGateway':
        """Get or create the internal GLM provider."""
        if self._glm_gateway is None:
            from rag_service.config import get_settings
            settings = get_settings()
            p = settings.litellm.glm
            if p is None:
                raise RuntimeError("GLM provider not configured")
            self._glm_gateway = GLMCompletionGateway(
                url=p.url,
                model=p.model,
                timeout=p.timeout,
                api_key=p.api_key,
                max_retries=p.max_retries,
                retry_delay=p.retry_delay,
                enable_thinking=p.enable_thinking,
            )
        return self._glm_gateway

    async def _get_embedding_gateway(self) -> 'HTTPEmbeddingGateway':
        """Get or create the internal embedding provider."""
        if self._embedding_gateway is None:
            from rag_service.config import get_settings
            settings = get_settings()
            self._embedding_gateway = HTTPEmbeddingGateway(
                url=settings.litellm.embedding_url,
                model=settings.litellm.embedding_model,
                timeout=settings.litellm.embedding_timeout,
                auth_token=settings.litellm.embedding_auth_token,
            )
        return self._embedding_gateway

    def complete_routed(
        self,
        prompt: str,
        model_hint: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs,
    ) -> CompletionResult:
        """Route completion to the configured internal provider.

        This is the unified entry point that selects between LiteLLM,
        HTTP Cloud, and GLM based on the provider configuration.
        Callers never specify a provider — it's config-driven.

        Args:
            prompt: Input prompt
            model_hint: Optional model hint
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional model parameters

        Returns:
            CompletionResult with generated text and metadata
        """
        if self._provider == "cloud_http":
            gateway = self._get_http_gateway()
            return gateway.complete(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            )
        elif self._provider == "glm":
            gateway = self._get_glm_gateway()
            return gateway.complete(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            )
        else:
            # Standard LiteLLM routing
            return self.complete(
                prompt=prompt,
                model_hint=model_hint,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            )

    async def acomplete_routed(
        self,
        prompt: str,
        model_hint: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs,
    ) -> CompletionResult:
        """Async version of complete_routed.

        Routes to the configured provider asynchronously.
        """
        if self._provider == "cloud_http":
            gateway = self._get_http_gateway()
            return await gateway.acomplete(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            )
        elif self._provider == "glm":
            gateway = self._get_glm_gateway()
            return await gateway.acomplete(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            )
        else:
            return await self.acomplete(
                prompt=prompt,
                model_hint=model_hint,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            )

    async def embed(self, text: str) -> 'EmbeddingResult':
        """Generate embedding via the internal embedding provider.

        Args:
            text: Text to embed.

        Returns:
            EmbeddingResult with vector and metadata.
        """
        gateway = await self._get_embedding_gateway()
        return await gateway.embed(text)


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
        model_hint_or_default = model_hint or self.default_model

        # Resolve the actual model name for LiteLLM
        if model_hint_or_default in self.models:
            model_config = self.models[model_hint_or_default]
            model = model_config.get_model_for_litellm()
            model_id = model_config.model_id  # Keep track of friendly name
        else:
            # Use the hint directly (might be a litellm model name)
            model = model_hint_or_default
            model_id = model_hint_or_default

        # Use time.time() instead of event loop time for thread safety
        import time
        start_time = time.time()

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

            # Add custom base_url and api_key if available
            if model_hint_or_default in self.models:
                model_config = self.models[model_hint_or_default]
                if model_config.base_url:
                    params["api_base"] = model_config.base_url
                if model_config.api_key:
                    params["api_key"] = model_config.api_key

            # Call LiteLLM
            response = completion(**params)

            # Extract result
            text = response.choices[0].message.content
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            total_tokens = input_tokens + output_tokens

            # Calculate cost
            cost = self._estimate_cost(model, input_tokens, output_tokens)

            latency_ms = (time.time() - start_time) * 1000

            result = CompletionResult(
                text=text,
                model=model_id,  # Use friendly name for result
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
                    "model_id": model_id,
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
                    "model_id": model_id,
                    "error": str(e),
                },
            )

            # Try fallback models
            if model_hint_or_default not in self.fallback_models:
                for fallback_model in self.fallback_models:
                    if fallback_model != model_hint_or_default:
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
        # Use functools.partial to properly handle kwargs
        from functools import partial
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            partial(self.complete, prompt, model_hint, max_tokens, temperature, **kwargs)
        )

    async def astream_complete(
        self,
        prompt: str,
        model_hint: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """
        Async streaming version of complete.

        Args:
            prompt: Input prompt
            model_hint: Optional model hint
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional model parameters

        Yields:
            Individual tokens of the generated text

        Raises:
            RuntimeError: If all models fail
        """
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty")

        # Select model
        model = model_hint or self.default_model

        try:
            from litellm import acompletion

            # Prepare parameters
            params = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": True,
                **kwargs,
            }

            # Call LiteLLM streaming
            response = await acompletion(**params)

            # Stream tokens
            async for chunk in response:
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    if hasattr(delta, "content") and delta.content:
                        yield delta.content

        except Exception as e:
            logger.error(
                "Model streaming completion failed",
                extra={
                    "model": model,
                    "error": str(e),
                },
            )
            # For streaming, we can't easily fallback to non-streaming models
            # So we just raise the error
            raise RuntimeError(f"Streaming completion failed: {e}")

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

    The gateway is configured with the active provider from settings.
    LITELLM_PROVIDER (or legacy DEFAULT_GATEWAY) determines which internal
    provider to use. Callers never specify a provider.

    Returns:
        The global LiteLLMGateway instance configured with the active provider.
    """
    global _gateway

    async with _gateway_lock:
        if _gateway is None:
            import os

            config_path = os.getenv("LITELLM_CONFIG_PATH")
            default_model = os.getenv("DEFAULT_MODEL", "gpt-3.5-turbo")

            # Determine provider from new or legacy config
            try:
                from rag_service.config import get_settings
                settings = get_settings()
                provider = settings.litellm.provider
                default_model = settings.litellm.model or default_model
            except Exception:
                provider = "openai"

            _gateway = LiteLLMGateway(
                config_path=config_path,
                default_model=default_model,
                provider=provider,
            )
            logger.info(
                "Initialized global LiteLLM gateway",
                extra={"provider": provider, "default_model": default_model},
            )

    return _gateway


def reset_gateway() -> None:
    """Reset the global gateway instance.

    This is primarily used for testing to ensure clean state between tests.
    """
    global _gateway
    _gateway = None
    logger.debug("Reset global LiteLLM gateway")


# ============================================================================
# HTTP Completion Gateway - Direct HTTP calls to cloud APIs
# ============================================================================


class HTTPCompletionGateway:
    """
    Gateway for direct HTTP calls to cloud completion APIs.

    This gateway provides an alternative to LiteLLM for services that
    expose standard HTTP endpoints without LiteLLM compatibility.
    It supports:
    - OpenAI-style completion and chat endpoints
    - Custom response formats (output, text, result)
    - Basic authentication
    - Retry with exponential backoff
    - Streaming responses (Server-Sent Events)

    Configuration via environment:
    - CLOUD_COMPLETION_URL: API endpoint URL
    - CLOUD_COMPLETION_MODEL: Model name
    - CLOUD_COMPLETION_TIMEOUT: Request timeout
    - CLOUD_COMPLETION_AUTH_TOKEN: Basic auth token
    """

    def __init__(
        self,
        url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 60,
        auth_token: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """Initialize HTTP completion gateway.

        Args:
            url: API endpoint URL
            model: Model name to send in requests
            timeout: Request timeout in seconds
            auth_token: Basic authentication token
            max_retries: Maximum retry attempts
            retry_delay: Initial retry delay in seconds
        """
        self.url = url
        self.model = model
        self.timeout = timeout
        self.auth_token = auth_token
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # Build headers
        self._headers = {"Content-Type": "application/json"}
        if self.auth_token:
            self._headers["Authorization"] = f"Basic {self.auth_token}"

        logger.info(
            "Initialized HTTP completion gateway",
            extra={
                "url": self.url,
                "model": self.model,
                "timeout": self.timeout,
            },
        )

    def _parse_completion_response(self, response: Dict[str, Any]) -> CompletionResult:
        """Parse API response into CompletionResult.

        Supports multiple response formats:
        - OpenAI style: {"choices": [{"text": "...", "message": {"content": "..."}]}
        - Simple: {"output": "..."} or {"text": "..."} or {"result": "..."}
        - With usage: {"usage": {"prompt_tokens": ..., "completion_tokens": ...}}

        Args:
            response: API response JSON

        Returns:
            CompletionResult with text and metadata
        """
        # Extract text based on format
        if "choices" in response:
            choice = response["choices"][0]
            text = choice.get("text", choice.get("message", {}).get("content", ""))
            finish_reason = choice.get("finish_reason")
            usage = response.get("usage")
        elif "output" in response:
            text = response["output"]
            finish_reason = response.get("finish_reason")
            usage = response.get("usage")
        elif "text" in response:
            text = response["text"]
            finish_reason = response.get("finish_reason")
            usage = response.get("usage")
        elif "result" in response:
            text = response["result"]
            finish_reason = response.get("finish_reason")
            usage = response.get("usage")
        else:
            raise ValueError(f"Unexpected response format: {response}")

        # Extract usage if available
        input_tokens = 0
        output_tokens = 0
        if usage:
            input_tokens = usage.get("prompt_tokens", usage.get("input_tokens", 0))
            output_tokens = usage.get("completion_tokens", usage.get("output_tokens", 0))

        total_tokens = input_tokens + output_tokens

        return CompletionResult(
            text=text,
            model=self.model or "unknown",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost=0.0,  # Cost tracking not available for custom APIs
            latency_ms=0.0,  # Will be set by caller
            provider="http",
        )

    def _parse_stream_chunk(self, chunk: Dict[str, Any]) -> str:
        """Parse streaming response chunk.

        Args:
            chunk: Streaming chunk JSON

        Returns:
            Text content from chunk
        """
        if "choices" in chunk:
            choice = chunk["choices"][0]
            return choice.get("text", choice.get("delta", {}).get("content", ""))
        elif "text" in chunk:
            return chunk["text"]
        return ""

    def complete(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        top_p: float = 0.9,
        messages: Optional[List[Dict[str, str]]] = None,
    ) -> CompletionResult:
        """Execute synchronous completion request.

        Args:
            prompt: Input prompt (for completion endpoint)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling parameter
            messages: Optional message list for chat endpoint

        Returns:
            CompletionResult with generated text

        Raises:
            ValueError: If URL is not configured
            RuntimeError: If request fails after retries
        """
        if not self.url:
            raise ValueError("HTTP completion gateway URL is not configured")

        import httpx

        start_time = time.time()

        # Build request payload
        if messages:
            # Chat format
            payload = {
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "model": self.model,
            }
        else:
            # Completion format
            payload = {
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "model": self.model,
            }

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout, headers=self._headers) as client:
                    response = client.post(self.url, json=payload)
                    response.raise_for_status()
                    result = self._parse_completion_response(response.json())

                latency_ms = (time.time() - start_time) * 1000
                result.latency_ms = latency_ms

                logger.info(
                    "HTTP completion successful",
                    extra={
                        "url": self.url,
                        "model": self.model,
                        "input_tokens": result.input_tokens,
                        "output_tokens": result.output_tokens,
                        "latency_ms": latency_ms,
                        "attempt": attempt + 1,
                    },
                )

                return result

            except httpx.HTTPError as e:
                last_error = e
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.warning(
                        f"HTTP completion failed, retrying in {delay}s",
                        extra={
                            "attempt": attempt + 1,
                            "max_retries": self.max_retries,
                            "error": str(e),
                        },
                    )
                    time.sleep(delay)
                continue
            except Exception as e:
                logger.error(
                    "HTTP completion failed with unexpected error",
                    extra={"error": str(e)},
                )
                raise RuntimeError(f"HTTP completion failed: {e}") from e

        raise RuntimeError(f"HTTP completion failed after {self.max_retries} retries: {last_error}")

    async def acomplete(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        top_p: float = 0.9,
        messages: Optional[List[Dict[str, str]]] = None,
    ) -> CompletionResult:
        """Execute async completion request.

        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling parameter
            messages: Optional message list for chat endpoint

        Returns:
            CompletionResult with generated text
        """
        if not self.url:
            raise ValueError("HTTP completion gateway URL is not configured")

        import httpx

        start_time = time.time()

        # Build request payload
        if messages:
            payload = {
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "model": self.model,
            }
        else:
            payload = {
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "model": self.model,
            }

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout, headers=self._headers) as client:
                    response = await client.post(self.url, json=payload)
                    response.raise_for_status()
                    result = self._parse_completion_response(response.json())

                latency_ms = (time.time() - start_time) * 1000
                result.latency_ms = latency_ms

                logger.info(
                    "HTTP async completion successful",
                    extra={
                        "url": self.url,
                        "model": self.model,
                        "latency_ms": latency_ms,
                        "attempt": attempt + 1,
                    },
                )

                return result

            except httpx.HTTPError as e:
                last_error = e
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.warning(
                        f"HTTP async completion failed, retrying in {delay}s",
                        extra={
                            "attempt": attempt + 1,
                            "error": str(e),
                        },
                    )
                    await asyncio.sleep(delay)
                continue
            except Exception as e:
                logger.error(
                    "HTTP async completion failed with unexpected error",
                    extra={"error": str(e)},
                )
                raise RuntimeError(f"HTTP async completion failed: {e}") from e

        raise RuntimeError(f"HTTP async completion failed after {self.max_retries} retries: {last_error}")

    async def astream_complete(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        top_p: float = 0.9,
    ) -> AsyncGenerator[str, None]:
        """Execute async streaming completion.

        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling parameter

        Yields:
            Individual tokens of the generated text
        """
        if not self.url:
            raise ValueError("HTTP completion gateway URL is not configured")

        import httpx

        payload = {
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stream": True,
            "model": self.model,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=self._headers) as client:
                async with client.stream("POST", self.url, json=payload) as response:
                    response.raise_for_status()

                    async for line in response.aiter_lines():
                        line = line.strip()
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data)
                                text = self._parse_stream_chunk(chunk)
                                if text:
                                    yield text
                            except json.JSONDecodeError:
                                continue

        except Exception as e:
            logger.error(
                "HTTP streaming completion failed",
                extra={"error": str(e)},
            )
            raise RuntimeError(f"HTTP streaming completion failed: {e}") from e

    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available models.

        Returns:
            List with single model configuration
        """
        if not self.url:
            return []

        return [
            {
                "model_id": self.model or "http-model",
                "provider": "http",
                "available": True,
                "url": self.url,
            }
        ]


# Global singleton instance for HTTP gateway
_http_gateway: Optional[HTTPCompletionGateway] = None
_http_gateway_lock = asyncio.Lock()


async def get_http_gateway() -> HTTPCompletionGateway:
    """Get or create the global HTTP gateway singleton.

    DEPRECATED: Use get_gateway() instead. HTTP Cloud is now an internal
    provider within LiteLLMGateway.

    Returns:
        The HTTPCompletionGateway instance (via LiteLLMGateway internals).
    """
    gateway = await get_gateway()
    return gateway._get_http_gateway()


def reset_http_gateway() -> None:
    """Reset the global HTTP gateway instance.

    This is primarily used for testing.
    """
    global _http_gateway
    _http_gateway = None
    logger.debug("Reset global HTTP completion gateway")


# ============================================================================
# GLM Completion Gateway - 智谱AI BigModel API
# ============================================================================


class GLMCompletionGateway:
    """
    Gateway for GLM (智谱AI) completion API.

    This gateway provides access to GLM models including:
    - glm-4.5: Latest flagship model
    - glm-4.5-air: Cost-effective model for most tasks
    - glm-4-flash: Fast and lightweight model

    API documentation: https://open.bigmodel.cn/api/paas/v4/chat/completions

    Configuration via environment:
    - GLM_URL: API endpoint URL (default: https://open.bigmodel.cn/api/paas/v4/chat/completions)
    - GLM_MODEL: Model name (default: glm-4.5-air)
    - GLM_API_KEY: API key for Bearer token authentication
    - GLM_TIMEOUT: Request timeout (default: 120)
    - GLM_ENABLE_THINKING: Enable thinking mode (default: false)
    """

    def __init__(
        self,
        url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 120,
        api_key: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        enable_thinking: bool = False,
    ):
        """Initialize GLM completion gateway.

        Args:
            url: API endpoint URL
            model: Model name to send in requests
            timeout: Request timeout in seconds
            api_key: API key for Bearer token authentication
            max_retries: Maximum retry attempts
            retry_delay: Initial retry delay in seconds
            enable_thinking: Enable thinking mode in requests
        """
        self.url = url or "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        self.model = model or "glm-4.5-air"
        self.timeout = timeout
        self.api_key = api_key
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.enable_thinking = enable_thinking

        # Build headers with Bearer token
        self._headers = {"Content-Type": "application/json"}
        if self.api_key:
            self._headers["Authorization"] = f"Bearer {self.api_key}"

        logger.info(
            "Initialized GLM completion gateway",
            extra={
                "url": self.url,
                "model": self.model,
                "timeout": self.timeout,
            },
        )

    def _parse_completion_response(self, response: Dict[str, Any]) -> CompletionResult:
        """Parse GLM API response into CompletionResult.

        GLM uses OpenAI-compatible response format:
        {"choices": [{"message": {"content": "...", "reasoning_content": "..."}, "finish_reason": "..."}], "usage": {...}}

        Note: GLM may have empty "content" when thinking mode is enabled, check "reasoning_content".

        Args:
            response: API response JSON

        Returns:
            CompletionResult with text and metadata
        """
        # Extract text from OpenAI-style response
        if "choices" in response and response["choices"]:
            choice = response["choices"][0]
            message = choice.get("message", {})
            # GLM may put content in reasoning_content when thinking mode is enabled
            text = message.get("content", "")
            if not text:
                text = message.get("reasoning_content", "")
            finish_reason = choice.get("finish_reason")
        else:
            raise ValueError(f"Unexpected GLM response format: {response}")

        # Extract usage if available
        usage = response.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        total_tokens = input_tokens + output_tokens

        return CompletionResult(
            text=text,
            model=self.model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost=0.0,  # Cost tracking not available
            latency_ms=0.0,  # Will be set by caller
            provider="glm",
        )

    async def acomplete(
        self,
        prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        top_p: float = 0.9,
        messages: Optional[List[Dict[str, str]]] = None,
    ) -> CompletionResult:
        """Execute async completion request.

        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling parameter
            messages: Optional message list for chat endpoint (if provided, prompt is ignored)

        Returns:
            CompletionResult with generated text

        Raises:
            ValueError: If API key is not configured
            RuntimeError: If request fails after retries
        """
        if not self.api_key:
            raise ValueError("GLM API key is not configured")

        start_time = time.time()

        # Build request payload - use messages format
        if messages:
            # Use provided messages
            payload_messages = messages
        else:
            # Convert prompt to single user message
            payload_messages = [{"role": "user", "content": prompt}]

        payload = {
            "model": self.model,
            "messages": payload_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
        }

        # Add thinking parameter if enabled
        if self.enable_thinking:
            payload["thinking"] = {"type": "enabled"}

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout, headers=self._headers) as client:
                    response = await client.post(self.url, json=payload)
                    response.raise_for_status()
                    result = self._parse_completion_response(response.json())

                latency_ms = (time.time() - start_time) * 1000
                result.latency_ms = latency_ms

                logger.info(
                    "GLM async completion successful",
                    extra={
                        "model": self.model,
                        "input_tokens": result.input_tokens,
                        "output_tokens": result.output_tokens,
                        "latency_ms": latency_ms,
                        "attempt": attempt + 1,
                    },
                )

                return result

            except httpx.HTTPError as e:
                last_error = e
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.warning(
                        f"GLM completion failed, retrying in {delay}s",
                        extra={
                            "attempt": attempt + 1,
                            "max_retries": self.max_retries,
                            "error": str(e),
                        },
                    )
                    await asyncio.sleep(delay)
                continue
            except Exception as e:
                logger.error(
                    "GLM completion failed with unexpected error",
                    extra={"error": str(e)},
                )
                raise RuntimeError(f"GLM completion failed: {e}") from e

        raise RuntimeError(f"GLM completion failed after {self.max_retries} retries: {last_error}")

    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of available GLM models.

        Returns:
            List with GLM model configuration
        """
        if not self.api_key:
            return []

        return [
            {
                "model_id": self.model,
                "provider": "glm",
                "available": True,
                "url": self.url,
            }
        ]


# Global singleton instance for GLM gateway
_glm_gateway: Optional[GLMCompletionGateway] = None
_glm_gateway_lock = asyncio.Lock()


async def get_glm_gateway() -> GLMCompletionGateway:
    """Get or create the global GLM gateway singleton.

    DEPRECATED: Use get_gateway() instead. GLM is now an internal
    provider within LiteLLMGateway.

    Returns:
        The GLMCompletionGateway instance (via LiteLLMGateway internals).
    """
    gateway = await get_gateway()
    return gateway._get_glm_gateway()


def reset_glm_gateway() -> None:
    """Reset the global GLM gateway instance.

    This is primarily used for testing.
    """
    global _glm_gateway
    _glm_gateway = None
    logger.debug("Reset global GLM completion gateway")


# ============================================================================
# HTTP Embedding Gateway
# ============================================================================

@dataclass
class EmbeddingResult:
    """Result from text embedding.

    Attributes:
        embedding: Embedding vector
        model: Model identifier used
        dimension: Vector dimension
        latency_ms: Request latency in milliseconds
    """
    embedding: List[float]
    model: str
    dimension: int
    latency_ms: float


class HTTPEmbeddingGateway:
    """
    Gateway for text embedding via HTTP API.

    This gateway provides direct HTTP access to embedding services,
    supporting cloud-hosted embedding models.

    Attributes:
        url: Embedding API endpoint URL
        model: Model name
        timeout: Request timeout in seconds
        auth_token: Optional Basic auth token
    """

    def __init__(
        self,
        url: str,
        model: str = "bge-m3",
        timeout: int = 30,
        auth_token: str = "",
    ):
        """Initialize the HTTP embedding gateway.

        Args:
            url: Embedding API endpoint URL
            model: Model name
            timeout: Request timeout in seconds
            auth_token: Optional Basic auth token (format: "username:password" for Basic Auth)
        """
        self.url = url
        self.model = model
        self.timeout = timeout
        self.auth_token = auth_token

        # Initialize HTTP client
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client.

        Returns:
            Async HTTP client instance.
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def embed(self, text: str) -> EmbeddingResult:
        """Generate embedding for a single text.

        Args:
            text: Input text to embed.

        Returns:
            Embedding result with vector and metadata.

        Raises:
            RuntimeError: If embedding request fails.
        """
        client = await self._get_client()
        start_time = time.time()

        # Build headers
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Basic {self.auth_token}"

        # Build request body
        # Support both OpenAI format and custom format
        payload = {
            "input": text,
            "model": self.model,
        }

        try:
            response = await client.post(
                self.url,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()

            latency_ms = (time.time() - start_time) * 1000
            data = response.json()

            # Parse response - return single result from embed_batch
            results = await self.embed_batch([text])
            return results[0]

        except Exception as e:
            logger.error("HTTP embedding request failed", extra={"error": str(e)})
            raise RuntimeError(f"Embedding request failed: {e}") from e

    async def embed_batch(self, texts: List[str]) -> List[EmbeddingResult]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of input texts to embed.

        Returns:
            List of embedding results.

        Raises:
            RuntimeError: If embedding request fails.
        """
        client = await self._get_client()
        start_time = time.time()

        # Build headers
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Basic {self.auth_token}"

        # Build request body
        # Support both OpenAI format and custom format
        payload = {
            "input": texts,
            "model": self.model,
        }

        try:
            response = await client.post(
                self.url,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()

            latency_ms = (time.time() - start_time) * 1000
            data = response.json()

            # Parse response
            results = []

            # Handle different response formats
            if "data" in data:
                # OpenAI format
                for item in data["data"]:
                    results.append(EmbeddingResult(
                        embedding=item["embedding"],
                        model=self.model,
                        dimension=len(item["embedding"]),
                        latency_ms=latency_ms,
                    ))
            elif "embeddings" in data:
                # Custom format
                for i, embedding in enumerate(data["embeddings"]):
                    results.append(EmbeddingResult(
                        embedding=embedding,
                        model=self.model,
                        dimension=len(embedding),
                        latency_ms=latency_ms,
                    ))
            else:
                # Single embedding result (direct list format)
                embedding = data.get("embedding", [])
                if isinstance(embedding, list):
                    results.append(EmbeddingResult(
                        embedding=embedding,
                        model=self.model,
                        dimension=len(embedding),
                        latency_ms=latency_ms,
                    ))

            return results

        except httpx.HTTPStatusError as e:
            logger.error(
                "HTTP embedding request failed",
                extra={"status_code": e.response.status_code, "response": e.response.text},
            )
            raise RuntimeError(
                f"Embedding request failed: {e.response.status_code} - {e.response.text}"
            ) from e

        except Exception as e:
            logger.error("HTTP embedding request failed", extra={"error": str(e)})
            raise RuntimeError(f"Embedding request failed: {e}") from e


# Global HTTP embedding gateway instance
_http_embedding_gateway: Optional[HTTPEmbeddingGateway] = None


async def get_http_embedding_gateway() -> HTTPEmbeddingGateway:
    """Get the global HTTP embedding gateway instance.

    Returns:
        HTTPEmbeddingGateway instance.
    """
    global _http_embedding_gateway

    if _http_embedding_gateway is None:
        from rag_service.config import get_settings

        settings = get_settings()

        if not settings.cloud_embedding.enabled:
            raise RuntimeError(
                "Cloud embedding is not configured. "
                "Set CLOUD_EMBEDDING_URL environment variable."
            )

        _http_embedding_gateway = HTTPEmbeddingGateway(
            url=settings.cloud_embedding.url,
            model=settings.cloud_embedding.model,
            timeout=settings.cloud_embedding.timeout,
            auth_token=settings.cloud_embedding.auth_token,
        )
        logger.info(
            "Initialized global HTTP embedding gateway",
            extra={
                "url": settings.cloud_embedding.url,
                "model": settings.cloud_embedding.model,
            },
        )

    return _http_embedding_gateway


def reset_http_embedding_gateway() -> None:
    """Reset the global HTTP embedding gateway instance.

    This is primarily used for testing.
    """
    global _http_embedding_gateway
    _http_embedding_gateway = None
    logger.debug("Reset global HTTP embedding gateway")
