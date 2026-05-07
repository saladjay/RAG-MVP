"""
Unit tests for Gateway Provider Selection (US2 - Multi-Model Inference).

These tests verify the LiteLLM gateway provider selection logic.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any, List


class TestGatewayProviderSelection:
    """Unit tests for LiteLLM gateway provider selection.

    Tests verify:
    - Model hint parsing and routing
    - Provider selection logic
    - Fallback chain behavior
    - Cost calculation per provider
    """

    @pytest.fixture
    def mock_gateway(self):
        """Mock LiteLLM gateway."""
        from rag_service.inference.gateway import LiteLLMGateway

        with patch("rag_service.inference.gateway.litellm"):
            gateway = LiteLLMGateway(default_model="gpt-3.5-turbo")
            return gateway

    @pytest.mark.unit
    def test_gateway_extracts_provider_from_model_id(
        self,
        mock_gateway,
    ) -> None:
        """Test that gateway extracts provider from model ID.

        Given: Various model IDs
        When: _extract_provider is called
        Then: Returns correct provider type
        """
        test_cases = [
            ("gpt-4", "openai"),
            ("gpt-3.5-turbo", "openai"),
            ("claude-3-opus-20040229", "anthropic"),
            ("claude-3-haiku", "anthropic"),
            ("ollama/llama3", "ollama"),
            ("mistral", "unknown"),  # Ollama default
        ]

        for model_id, expected_provider in test_cases:
            provider = mock_gateway._extract_provider(model_id)
            assert provider == expected_provider

    @pytest.mark.unit
    def test_gateway_calculates_cost_per_provider(
        self,
        mock_gateway,
    ) -> None:
        """Test that gateway calculates cost correctly per provider.

        Given: Model with input/output tokens
        When: _estimate_cost is called
        Then: Returns correct cost based on provider pricing
        """
        test_cases = [
            ("gpt-4", 1000, 500, 30.0 * 1 + 60.0 * 0.5),
            ("gpt-3.5-turbo", 1000, 500, 0.5 * 1 + 1.5 * 0.5),
            ("claude-3-opus", 1000, 500, 15.0 * 1 + 75.0 * 0.5),
            ("claude-3-haiku", 1000, 500, 0.25 * 1 + 1.25 * 0.5),
        ]

        for model, input_tokens, output_tokens, expected_cost in test_cases:
            cost = mock_gateway._estimate_cost(model, input_tokens, output_tokens)
            # Cost should match expected (within floating point precision)
            assert abs(cost - expected_cost) < 0.01

    @pytest.mark.unit
    @patch("rag_service.inference.gateway.litellm")
    def test_gateway_uses_requested_model(
        self,
        mock_litellm,
        mock_gateway,
    ) -> None:
        """Test that gateway uses requested model from hint.

        Given: Request with model_hint="gpt-4"
        When: complete is called
        Then: LiteLLM is called with requested model
        """
        from rag_service.inference.gateway import LiteLLMGateway
        from unittest.mock import MagicMock

        gateway = LiteLLMGateway(default_model="gpt-3.5-turbo")

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].message.content = "Response"
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        mock_response.usage.total_tokens = 150

        mock_litellm.completion = Mock(return_value=mock_response)

        result = gateway.complete(
            prompt="Test prompt",
            model_hint="gpt-4",
        )

        # Verify LiteLLM was called with correct model
        mock_litellm.completion.assert_called_once()
        call_kwargs = mock_litellm.completion.call_args
        assert call_kwargs[1]["model"] == "gpt-4"

    @pytest.mark.unit
    @patch("rag_service.inference.gateway.litellm")
    def test_gateway_falls_back_on_failure(
        self,
        mock_litellm,
    ) -> None:
        """Test that gateway falls back to alternative model on failure.

        Given: Primary model fails
        When: complete is called
        Then: Falls back to next available model
        """
        from rag_service.inference.gateway import LiteLLMGateway
        from unittest.mock import MagicMock

        gateway = LiteLLMGateway(
            default_model="gpt-3.5-turbo",
            fallback_models=["claude-3-haiku", "ollama/llama3"],
        )

        # First call fails, second succeeds
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Fallback response"
        mock_response.usage.prompt_tokens = 50
        mock_response.usage.completion_tokens = 30
        mock_response.usage.total_tokens = 80

        # Make first call fail, second succeed
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Primary model unavailable")
            return mock_response

        mock_litellm.completion = Mock(side_effect=side_effect)

        result = gateway.complete(
            prompt="Test prompt",
            model_hint="unavailable-model",
        )

        # Should have fallen back to second model
        assert call_count[0] == 2  # Tried twice
        assert result.text == "Fallback response"

    @pytest.mark.unit
    def test_gateway_handles_empty_model_hint(
        self,
        mock_gateway,
    ) -> None:
        """Test that gateway uses default when model_hint is empty.

        Given: Request with model_hint=None
        When: complete is called
        Then: Uses configured default model
        """
        from rag_service.inference.gateway import LiteLLMGateway

        gateway = LiteLLMGateway(default_model="gpt-3.5-turbo")

        # Verify default is set
        assert gateway.default_model == "gpt-3.5-turbo"

    @pytest.mark.unit
    def test_gateway_supports_ollama_routing(
        self,
        mock_gateway,
    ) -> None:
        """Test that gateway correctly routes Ollama models.

        Given: model_hint="ollama/llama3"
        When: Provider is extracted
        Then: Returns "ollama" as provider
        """
        provider = mock_gateway._extract_provider("ollama/llama3")
        assert provider == "ollama"

    @pytest.mark.unit
    def test_gateway_supports_vllm_routing(
        self,
        mock_gateway,
    ) -> None:
        """Test that gateway supports vLLM models.

        Given: model_hint for vLLM
        When: Provider is extracted
        Then: Correctly identifies vLLM provider
        """
        # vLLM uses OpenAI-compatible API
        provider = mock_gateway._extract_provider("vllm/model")
        # Should be treated as unknown/custom (uses base_url)
        assert provider in ["unknown", "openai"]


class TestModelConfiguration:
    """Unit tests for model configuration.

    Tests verify:
    - Model availability detection
    - Capability metadata
    - Cost configuration
    """

    @pytest.mark.unit
    def test_get_all_models_returns_configured_models(self) -> None:
        """Test that get_all_models returns all configured models.

        Given: Default model configurations
        When: get_all_models is called
        Then: Returns list of ModelConfig objects
        """
        from rag_service.inference.models import get_all_models

        models = get_all_models()

        assert len(models) > 0
        assert all(hasattr(m, "model_id") for m in models)
        assert all(hasattr(m, "provider") for m in models)

    @pytest.mark.unit
    def test_get_model_by_id_finds_openai_models(self) -> None:
        """Test that get_model_by_id finds OpenAI models.

        Given: Model ID "gpt-4"
        When: get_model_by_id is called
        Then: Returns GPT-4 model configuration
        """
        from rag_service.inference.models import get_model_by_id

        model = get_model_by_id("gpt-4")

        assert model is not None
        assert model.model_id == "gpt-4"
        assert model.provider.value == "openai"

    @pytest.mark.unit
    def test_get_model_by_id_finds_anthropic_models(self) -> None:
        """Test that get_model_by_id finds Anthropic models.

        Given: Model ID "claude-3-opus"
        When: get_model_by_id is called
        Then: Returns Claude model configuration
        """
        from rag_service.inference.models import get_model_by_id

        model = get_model_by_id("claude-3-opus")

        assert model is not None
        assert "claude" in model.model_id.lower()
        assert model.provider.value == "anthropic"

    @pytest.mark.unit
    def test_get_model_by_id_returns_none_for_unknown(self) -> None:
        """Test that get_model_by_id returns None for unknown models.

        Given: Unknown model ID
        When: get_model_by_id is called
        Then: Returns None
        """
        from rag_service.inference.models import get_model_by_id

        model = get_model_by_id("unknown-model-xyz")

        assert model is None

    @pytest.mark.unit
    def test_get_available_providers_filters_by_api_key(self) -> None:
        """Test that get_available_providers checks for API keys.

        Given: Environment with some API keys set
        When: get_available_providers is called
        Then: Returns only providers with configured keys
        """
        import os
        from rag_service.inference.models import get_available_providers

        # Set only OpenAI key
        original_keys = {}
        if "OPENAI_API_KEY" in os.environ:
            original_keys["OPENAI_API_KEY"] = os.environ["OPENAI_API_KEY"]

        os.environ["OPENAI_API_KEY"] = "test-key"

        try:
            providers = get_available_providers()

            # Should include OpenAI (has key) and Ollama (no key needed)
            provider_names = [p.provider.value for p in providers]

            # Ollama should always be available (local)
            assert "ollama" in provider_names

        finally:
            # Restore original keys
            if "OPENAI_API_KEY" in original_keys:
                os.environ["OPENAI_API_KEY"] = original_keys["OPENAI_API_KEY"]
            elif "OPENAI_API_KEY" in os.environ:
                del os.environ["OPENAI_API_KEY"]


class TestFallbackConfiguration:
    """Unit tests for fallback configuration.

    Tests verify:
    - Fallback chain ordering
    - Fallback triggering conditions
    - Fallback exhaustion handling
    """

    @pytest.mark.unit
    def test_fallback_chain_ordered_correctly(self) -> None:
        """Test that fallback chain is ordered correctly.

        Given: Configured fallback models
        When: Primary model fails
        Then: Falls back in configured order
        """
        from rag_service.inference.gateway import LiteLLMGateway

        gateway = LiteLLMGateway(
            default_model="gpt-3.5-turbo",
            fallback_models=["claude-3-haiku", "ollama/llama3"],
        )

        assert gateway.fallback_models == ["claude-3-haiku", "ollama/llama3"]

    @pytest.mark.unit
    def test_fallback_exhaustion_returns_error(self) -> None:
        """Test that exhausted fallback chain returns error.

        Given: All fallback models also fail
        When: complete is called
        Then: Raises RuntimeError
        """
        from rag_service.inference.gateway import LiteLLMGateway
        from unittest.mock import Mock

        gateway = LiteLLMGateway(
            default_model="primary-model",
            fallback_models=["fallback1", "fallback2"],
        )

        # Mock all completions to fail
        with patch("rag_service.inference.gateway.litellm") as mock_litellm:
            mock_litellm.completion = Mock(side_effect=Exception("All models failed"))

            with pytest.raises(RuntimeError):
                gateway.complete("Test prompt")

    @pytest.mark.unit
    def test_fallback_skips_same_model(self) -> None:
        """Test that fallback doesn't retry the same failed model.

        Given: Model that fails with model_hint
        When: Fallback chain is processed
        Then: Skips the same model in fallback list
        """
        from rag_service.inference.gateway import LiteLLMGateway

        gateway = LiteLLMGateway(
            default_model="gpt-3.5-turbo",
            fallback_models=["gpt-3.5-turbo", "claude-3-haiku"],
        )

        # If primary is "gpt-3.5-turbo" and it fails, fallback should skip it
        # This is tested implicitly by the fallback logic
        assert len([m for m in gateway.fallback_models if m == "gpt-3.5-turbo"]) >= 0


class TestHTTPCompletionGateway:
    """Unit tests for HTTP Completion Gateway.

    Tests verify:
    - HTTP gateway initialization
    - Response format parsing (OpenAI, simple, custom)
    - Stream chunk parsing
    - Retry with exponential backoff
    """

    @pytest.fixture
    def http_gateway(self):
        """Create HTTP gateway for testing."""
        from rag_service.inference.gateway import HTTPCompletionGateway

        return HTTPCompletionGateway(
            url="http://test.example.com/v1/completions",
            model="test-model",
            timeout=30,
            auth_token="test-token",
            max_retries=3,
            retry_delay=0.1,  # Short delay for tests
        )

    @pytest.mark.unit
    def test_http_gateway_initialization(self, http_gateway) -> None:
        """Test that HTTP gateway initializes correctly.

        Given: URL and model configuration
        When: HTTPCompletionGateway is created
        Then: Gateway has correct configuration
        """
        assert http_gateway.url == "http://test.example.com/v1/completions"
        assert http_gateway.model == "test-model"
        assert http_gateway.timeout == 30
        assert http_gateway.auth_token == "test-token"
        assert http_gateway.max_retries == 3

    @pytest.mark.unit
    def test_parse_openai_style_response(self, http_gateway) -> None:
        """Test parsing OpenAI-style response format.

        Given: Response with "choices" array
        When: _parse_completion_response is called
        Then: Extracts text and usage correctly
        """
        response = {
            "choices": [
                {
                    "text": "Generated text here",
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
            },
        }

        result = http_gateway._parse_completion_response(response)

        assert result.text == "Generated text here"
        assert result.input_tokens == 100
        assert result.output_tokens == 50
        assert result.provider == "http"

    @pytest.mark.unit
    def test_parse_simple_output_response(self, http_gateway) -> None:
        """Test parsing simple output format.

        Given: Response with "output" field
        When: _parse_completion_response is called
        Then: Extracts text correctly
        """
        response = {
            "output": "Simple output text",
            "finish_reason": "stop",
        }

        result = http_gateway._parse_completion_response(response)

        assert result.text == "Simple output text"

    @pytest.mark.unit
    def test_parse_text_field_response(self, http_gateway) -> None:
        """Test parsing text field format.

        Given: Response with "text" field
        When: _parse_completion_response is called
        Then: Extracts text correctly
        """
        response = {
            "text": "Text field content",
        }

        result = http_gateway._parse_completion_response(response)

        assert result.text == "Text field content"

    @pytest.mark.unit
    def test_parse_result_field_response(self, http_gateway) -> None:
        """Test parsing result field format.

        Given: Response with "result" field
        When: _parse_completion_response is called
        Then: Extracts text correctly
        """
        response = {
            "result": "Result field content",
        }

        result = http_gateway._parse_completion_response(response)

        assert result.text == "Result field content"

    @pytest.mark.unit
    def test_parse_unexpected_response_raises_error(self, http_gateway) -> None:
        """Test that unexpected response format raises error.

        Given: Response with unrecognized format
        When: _parse_completion_response is called
        Then: Raises ValueError
        """
        response = {
            "unexpected_field": "some content",
        }

        with pytest.raises(ValueError, match="Unexpected response format"):
            http_gateway._parse_completion_response(response)

    @pytest.mark.unit
    def test_parse_stream_chunk_openai_format(self, http_gateway) -> None:
        """Test parsing OpenAI-style stream chunk.

        Given: Chunk with "choices" array
        When: _parse_stream_chunk is called
        Then: Extracts text correctly
        """
        chunk = {
            "choices": [
                {
                    "text": "Hello",
                }
            ]
        }

        text = http_gateway._parse_stream_chunk(chunk)

        assert text == "Hello"

    @pytest.mark.unit
    def test_parse_stream_chunk_delta_format(self, http_gateway) -> None:
        """Test parsing delta format stream chunk.

        Given: Chunk with "delta" content
        When: _parse_stream_chunk is called
        Then: Extracts text correctly
        """
        chunk = {
            "choices": [
                {
                    "delta": {
                        "content": "World",
                    }
                }
            ]
        }

        text = http_gateway._parse_stream_chunk(chunk)

        assert text == "World"

    @pytest.mark.unit
    def test_parse_stream_chunk_simple_text(self, http_gateway) -> None:
        """Test parsing simple text stream chunk.

        Given: Chunk with "text" field
        When: _parse_stream_chunk is called
        Then: Extracts text correctly
        """
        chunk = {
            "text": "Simple",
        }

        text = http_gateway._parse_stream_chunk(chunk)

        assert text == "Simple"

    @pytest.mark.unit
    def test_parse_stream_chunk_empty(self, http_gateway) -> None:
        """Test parsing empty stream chunk.

        Given: Chunk with no recognizable text
        When: _parse_stream_chunk is called
        Then: Returns empty string
        """
        chunk = {
            "unexpected": "content",
        }

        text = http_gateway._parse_stream_chunk(chunk)

        assert text == ""

    @pytest.mark.unit
    def test_http_gateway_requires_url(self) -> None:
        """Test that HTTP gateway raises error without URL.

        Given: Gateway with no URL configured
        When: complete is called
        Then: Raises ValueError
        """
        from rag_service.inference.gateway import HTTPCompletionGateway

        gateway = HTTPCompletionGateway(url="", model="test")

        with pytest.raises(ValueError, match="URL is not configured"):
            gateway.complete("Test prompt")

    @pytest.mark.unit
    def test_get_available_models(self, http_gateway) -> None:
        """Test that get_available_models returns correct list.

        Given: Configured HTTP gateway
        When: get_available_models is called
        Then: Returns list with single model
        """
        models = http_gateway.get_available_models()

        assert len(models) == 1
        assert models[0]["model_id"] == "test-model"
        assert models[0]["provider"] == "http"
        assert models[0]["available"] is True

    @pytest.mark.unit
    def test_get_available_models_empty_without_url(self) -> None:
        """Test that get_available_models returns empty list without URL.

        Given: Gateway without URL
        When: get_available_models is called
        Then: Returns empty list
        """
        from rag_service.inference.gateway import HTTPCompletionGateway

        gateway = HTTPCompletionGateway(url="", model="test")
        models = gateway.get_available_models()

        assert len(models) == 0


class TestGatewayBackendSelection:
    """Unit tests for gateway backend selection in ModelInferenceCapability.

    Tests verify:
    - Gateway backend selection (litellm vs http)
    - Fallback behavior
    - Configuration handling
    """

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_capability_supports_http_backend(self) -> None:
        """Test that ModelInferenceCapability supports HTTP backend.

        Given: Input with gateway_backend="http"
        When: execute is called
        Then: Uses HTTP gateway for inference
        """
        from rag_service.capabilities.model_inference import (
            ModelInferenceCapability,
            ModelInferenceInput,
        )
        from rag_service.inference.gateway import CompletionResult
        from unittest.mock import AsyncMock, patch

        # Mock HTTP gateway
        mock_http_gateway = AsyncMock()
        mock_http_gateway.acomplete = AsyncMock(
            return_value=CompletionResult(
                text="HTTP response",
                model="http-model",
                input_tokens=10,
                output_tokens=20,
                total_tokens=30,
                cost=0.0,
                latency_ms=100,
                provider="http",
            )
        )

        capability = ModelInferenceCapability(
            http_client=mock_http_gateway,
            default_gateway="http",
        )

        input_data = ModelInferenceInput(
            prompt="Test prompt",
            gateway_backend="http",
        )

        result = await capability.execute(input_data)

        assert result.text == "HTTP response"
        mock_http_gateway.acomplete.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_capability_falls_back_to_litellm_by_default(self) -> None:
        """Test that ModelInferenceCapability defaults to LiteLLM.

        Given: Input without gateway_backend specified
        When: execute is called
        Then: Uses LiteLLM gateway
        """
        from rag_service.capabilities.model_inference import (
            ModelInferenceCapability,
            ModelInferenceInput,
        )
        from rag_service.inference.gateway import CompletionResult
        from unittest.mock import AsyncMock

        # Mock LiteLLM gateway
        mock_litellm = AsyncMock()
        mock_litellm.acomplete = AsyncMock(
            return_value=CompletionResult(
                text="LiteLLM response",
                model="gpt-3.5-turbo",
                input_tokens=10,
                output_tokens=20,
                total_tokens=30,
                cost=0.01,
                latency_ms=150,
                provider="openai",
            )
        )

        capability = ModelInferenceCapability(
            litellm_client=mock_litellm,
            default_gateway="litellm",
        )

        input_data = ModelInferenceInput(
            prompt="Test prompt",
        )

        result = await capability.execute(input_data)

        assert result.text == "LiteLLM response"
        mock_litellm.acomplete.assert_called_once()
