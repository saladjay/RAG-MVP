"""
Unit tests for HTTPCompletionGateway.

These tests verify the core functionality of HTTPCompletionGateway
in isolation, without making actual HTTP calls.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

import pytest
import httpx


class TestHTTPCompletionGatewayUnit:
    """Unit tests for HTTPCompletionGateway core functionality.

    Tests verify:
    - Gateway initialization
    - Request formatting
    - Response parsing
    - Error handling
    - Header construction
    """

    @pytest.fixture
    def gateway(self):
        """Create a test gateway instance."""
        from rag_service.inference.gateway import HTTPCompletionGateway

        return HTTPCompletionGateway(
            url="http://test.example.com/v1/completions",
            model="test-model",
            timeout=30,
            auth_token="dGVzdDp0ZXN0",
            max_retries=3,
            retry_delay=0.1,
        )

    @pytest.fixture
    def gateway_no_auth(self):
        """Create gateway without authentication."""
        from rag_service.inference.gateway import HTTPCompletionGateway

        return HTTPCompletionGateway(
            url="http://test.example.com/v1/completions",
            model="test-model",
            timeout=30,
            auth_token="",
        )

    # ----------------------------------------------------------------------
    # Initialization Tests
    # ----------------------------------------------------------------------

    @pytest.mark.unit
    def test_gateway_initialization(self, gateway) -> None:
        """Test gateway initializes with correct values."""
        assert gateway.url == "http://test.example.com/v1/completions"
        assert gateway.model == "test-model"
        assert gateway.timeout == 30
        assert gateway.auth_token == "dGVzdDp0ZXN0"
        assert gateway.max_retries == 3
        assert gateway.retry_delay == 0.1

    @pytest.mark.unit
    def test_gateway_headers_with_auth(self, gateway) -> None:
        """Test headers include auth token when configured."""
        assert gateway._headers["Content-Type"] == "application/json"
        assert gateway._headers["Authorization"] == "Basic dGVzdDp0ZXN0"

    @pytest.mark.unit
    def test_gateway_headers_without_auth(self, gateway_no_auth) -> None:
        """Test headers without auth token."""
        assert gateway_no_auth._headers["Content-Type"] == "application/json"
        assert "Authorization" not in gateway_no_auth._headers

    @pytest.mark.unit
    def test_gateway_with_custom_auth_token(self) -> None:
        """Test gateway with custom auth token."""
        from rag_service.inference.gateway import HTTPCompletionGateway

        gateway = HTTPCompletionGateway(
            url="http://test.com",
            model="test",
            auth_token="bXl0b2tlbjp2YWx1ZQ==",
        )

        assert gateway._headers["Authorization"] == "Basic bXl0b2tlbjp2YWx1ZQ=="

    # ----------------------------------------------------------------------
    # Response Parsing Tests
    # ----------------------------------------------------------------------

    @pytest.mark.unit
    def test_parse_openai_completion_format(self, gateway) -> None:
        """Test parsing OpenAI completion format."""
        response = {
            "choices": [
                {
                    "text": "This is the generated text.",
                    "finish_reason": "stop",
                    "index": 0,
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
            "model": "test-model",
        }

        result = gateway._parse_completion_response(response)

        assert result.text == "This is the generated text."
        assert result.input_tokens == 10
        assert result.output_tokens == 5
        assert result.total_tokens == 15
        assert result.provider == "http"

    @pytest.mark.unit
    def test_parse_openai_chat_format(self, gateway) -> None:
        """Test parsing OpenAI chat format."""
        response = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Chat response here",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 15,
                "completion_tokens": 3,
            },
        }

        result = gateway._parse_completion_response(response)

        assert result.text == "Chat response here"
        assert result.input_tokens == 15
        assert result.output_tokens == 3

    @pytest.mark.unit
    def test_parse_simple_output_format(self, gateway) -> None:
        """Test parsing simple output format."""
        response = {"output": "Simple output text"}

        result = gateway._parse_completion_response(response)

        assert result.text == "Simple output text"

    @pytest.mark.unit
    def test_parse_text_format(self, gateway) -> None:
        """Test parsing text field format."""
        response = {"text": "Text field content"}

        result = gateway._parse_completion_response(response)

        assert result.text == "Text field content"

    @pytest.mark.unit
    def test_parse_result_format(self, gateway) -> None:
        """Test parsing result field format."""
        response = {"result": "Result field content"}

        result = gateway._parse_completion_response(response)

        assert result.text == "Result field content"

    @pytest.mark.unit
    def test_parse_with_usage_metadata(self, gateway) -> None:
        """Test parsing response with usage metadata."""
        response = {
            "output": "Response with usage",
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
            },
        }

        result = gateway._parse_completion_response(response)

        assert result.text == "Response with usage"
        assert result.input_tokens == 100
        assert result.output_tokens == 50
        assert result.total_tokens == 150

    @pytest.mark.unit
    def test_parse_without_usage(self, gateway) -> None:
        """Test parsing response without usage information."""
        response = {"output": "Response without usage"}

        result = gateway._parse_completion_response(response)

        assert result.text == "Response without usage"
        assert result.input_tokens == 0
        assert result.output_tokens == 0
        assert result.total_tokens == 0

    @pytest.mark.unit
    def test_parse_invalid_format_raises_error(self, gateway) -> None:
        """Test that invalid format raises ValueError."""
        response = {"invalid_field": "some value"}

        with pytest.raises(ValueError, match="Unexpected response format"):
            gateway._parse_completion_response(response)

    @pytest.mark.unit
    def test_parse_empty_choices_raises_error(self, gateway) -> None:
        """Test that empty choices array is handled."""
        response = {"choices": []}

        with pytest.raises((ValueError, IndexError, KeyError)):
            gateway._parse_completion_response(response)

    # ----------------------------------------------------------------------
    # Stream Chunk Parsing Tests
    # ----------------------------------------------------------------------

    @pytest.mark.unit
    def test_parse_stream_openai_choices_text(self, gateway) -> None:
        """Test parsing stream chunk with choices.text."""
        chunk = {"choices": [{"text": "Hello"}]}

        text = gateway._parse_stream_chunk(chunk)

        assert text == "Hello"

    @pytest.mark.unit
    def test_parse_stream_openai_delta_content(self, gateway) -> None:
        """Test parsing stream chunk with delta.content."""
        chunk = {"choices": [{"delta": {"content": " world"}}]}

        text = gateway._parse_stream_chunk(chunk)

        assert text == " world"

    @pytest.mark.unit
    def test_parse_stream_simple_text(self, gateway) -> None:
        """Test parsing stream chunk with text field."""
        chunk = {"text": "Simple"}

        text = gateway._parse_stream_chunk(chunk)

        assert text == "Simple"

    @pytest.mark.unit
    def test_parse_stream_empty_chunk(self, gateway) -> None:
        """Test parsing empty stream chunk."""
        chunk = {"unexpected": "data"}

        text = gateway._parse_stream_chunk(chunk)

        assert text == ""

    @pytest.mark.unit
    def test_parse_stream_message_content(self, gateway) -> None:
        """Test parsing stream chunk with message.content."""
        chunk = {"choices": [{"message": {"content": "Message text"}}]}

        text = gateway._parse_stream_chunk(chunk)

        assert text == "Message text"

    @pytest.mark.unit
    def test_parse_stream_nested_delta(self, gateway) -> None:
        """Test parsing stream chunk with nested delta."""
        chunk = {"choices": [{"delta": {"content": "Nested"}}]}

        text = gateway._parse_stream_chunk(chunk)

        assert text == "Nested"

    # ----------------------------------------------------------------------
    # Available Models Tests
    # ----------------------------------------------------------------------

    @pytest.mark.unit
    def test_get_available_models_with_url(self, gateway) -> None:
        """Test get_available_models returns model info."""
        models = gateway.get_available_models()

        assert len(models) == 1
        assert models[0]["model_id"] == "test-model"
        assert models[0]["provider"] == "http"
        assert models[0]["available"] is True
        assert models[0]["url"] == "http://test.example.com/v1/completions"

    @pytest.mark.unit
    def test_get_available_models_without_url(self, gateway_no_auth) -> None:
        """Test get_available_models without URL returns empty."""
        gateway_no_auth.url = ""
        models = gateway_no_auth.get_available_models()

        assert len(models) == 0

    @pytest.mark.unit
    def test_get_available_models_with_different_model(self) -> None:
        """Test get_available_models with different model name."""
        from rag_service.inference.gateway import HTTPCompletionGateway

        gateway = HTTPCompletionGateway(
            url="http://test.com",
            model="custom-model-name",
        )

        models = gateway.get_available_models()

        assert models[0]["model_id"] == "custom-model-name"

    # ----------------------------------------------------------------------
    # Error Handling Tests
    # ----------------------------------------------------------------------

    @pytest.mark.unit
    def test_complete_without_url_raises_error(self) -> None:
        """Test complete raises error without URL."""
        from rag_service.inference.gateway import HTTPCompletionGateway

        gateway = HTTPCompletionGateway(url="", model="test")

        with pytest.raises(ValueError, match="URL is not configured"):
            gateway.complete("Test prompt")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_acomplete_without_url_raises_error(self) -> None:
        """Test acomplete raises error without URL."""
        from rag_service.inference.gateway import HTTPCompletionGateway

        gateway = HTTPCompletionGateway(url="", model="test")

        with pytest.raises(ValueError, match="URL is not configured"):
            await gateway.acomplete("Test prompt")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_astream_complete_without_url_raises_error(self) -> None:
        """Test astream_complete raises error without URL."""
        from rag_service.inference.gateway import HTTPCompletionGateway

        gateway = HTTPCompletionGateway(url="", model="test")

        with pytest.raises(ValueError, match="URL is not configured"):
            async for _ in gateway.astream_complete("Test"):
                pass

    @pytest.mark.unit
    def test_parse_malformed_openai_response(self, gateway) -> None:
        """Test handling malformed OpenAI response."""
        malformed_responses = [
            {"choices": [{}]},  # Missing text/message
            {"choices": [{"text": None}]},  # Null text
            {"choices": [{"message": {}}]},  # Empty message
        ]

        for response in malformed_responses:
            # Should handle gracefully or raise appropriate error
            try:
                result = gateway._parse_completion_response(response)
                # If no error, result.text should be empty string
                assert result.text == ""
            except (ValueError, KeyError, TypeError):
                # Also acceptable to raise error
                pass


class TestHTTPCompletionGatewayRetryLogic:
    """Unit tests for retry logic in HTTPCompletionGateway.

    Tests verify:
    - Retry on transient errors
    - Exponential backoff
    - Max retry limit
    - Different error types
    """

    @pytest.fixture
    def gateway_with_short_retry(self):
        """Create gateway with short retry settings for testing."""
        from rag_service.inference.gateway import HTTPCompletionGateway

        return HTTPCompletionGateway(
            url="http://test.com/v1/completions",
            model="test-model",
            max_retries=2,
            retry_delay=0.01,  # 10ms for fast tests
        )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_retry_on_http_error(self, gateway_with_short_retry) -> None:
        """Test retry logic on HTTP error."""
        call_count = {"count": 0}

        async def mock_post(*args, **kwargs):
            call_count["count"] += 1
            if call_count["count"] <= 2:
                raise httpx.HTTPError("Temporary error")
            # Third call succeeds
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"output": "Success"}
            mock_response.raise_for_status = MagicMock()
            return mock_response

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = mock_post
            mock_client_class.return_value = mock_client

            result = await gateway_with_short_retry.acomplete("Test")

            assert call_count["count"] == 3
            assert result.text == "Success"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_retry_exhaustion(self, gateway_with_short_retry) -> None:
        """Test behavior when retries are exhausted."""
        call_count = {"count": 0}

        async def mock_post(*args, **kwargs):
            call_count["count"] += 1
            raise httpx.HTTPError("Persistent error")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = mock_post
            mock_client_class.return_value = mock_client

            with pytest.raises(RuntimeError, match="failed after"):
                await gateway_with_short_retry.acomplete("Test")

            # Should have tried max_retries + 1 times
            assert call_count["count"] == 3

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_no_retry_on_validation_error(self, gateway_with_short_retry) -> None:
        """Test that validation errors don't trigger retry."""
        from rag_service.inference.gateway import HTTPCompletionGateway

        gateway = HTTPCompletionGateway(
            url="http://test.com",
            model="test",
            max_retries=3,
        )

        # Invalid JSON should not retry
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.side_effect = json.JSONDecodeError("Invalid", "", 0)
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            with pytest.raises((RuntimeError, json.JSONDecodeError)):
                await gateway.acomplete("Test")

            # Should not retry JSON decode errors
            mock_client.post.assert_called_once()

    @pytest.mark.unit
    def test_sync_complete_retry(self) -> None:
        """Test retry logic in sync complete method."""
        from rag_service.inference.gateway import HTTPCompletionGateway
        import time

        gateway = HTTPCompletionGateway(
            url="http://test.com",
            model="test",
            max_retries=2,
            retry_delay=0.01,
        )

        call_count = {"count": 0}

        def mock_post(*args, **kwargs):
            call_count["count"] += 1
            if call_count["count"] <= 1:
                raise httpx.HTTPError("Network error")
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"output": "Success"}
            return mock_response

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client.post = mock_post
            mock_client_class.return_value.__enter__.return_value = mock_client

            result = gateway.complete("Test")

            assert call_count["count"] == 2
            assert result.text == "Success"


class TestHTTPCompletionGatewayRequestFormatting:
    """Unit tests for request formatting.

    Tests verify:
    - Completion request format
    - Chat request format
    - Parameter encoding
    """

    @pytest.fixture
    def gateway(self):
        """Create a test gateway."""
        from rag_service.inference.gateway import HTTPCompletionGateway

        return HTTPCompletionGateway(
            url="http://test.com/v1/completions",
            model="test-model",
        )

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_completion_request_format(self, gateway) -> None:
        """Test completion request payload format."""
        with patch("httpx.AsyncClient") as mock_client_class:
            captured_payload = {}

            async def capture_post(url, json):
                captured_payload.update(json)
                mock_response = AsyncMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"output": "Response"}
                mock_response.raise_for_status = MagicMock()
                return mock_response

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = capture_post
            mock_client_class.return_value = mock_client

            await gateway.acomplete(
                prompt="Test prompt",
                max_tokens=500,
                temperature=0.8,
                top_p=0.95,
            )

            assert captured_payload["prompt"] == "Test prompt"
            assert captured_payload["max_tokens"] == 500
            assert captured_payload["temperature"] == 0.8
            assert captured_payload["top_p"] == 0.95
            assert captured_payload["stream"] is False
            assert captured_payload["model"] == "test-model"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_chat_request_format(self, gateway) -> None:
        """Test chat request payload format."""
        with patch("httpx.AsyncClient") as mock_client_class:
            captured_payload = {}

            async def capture_post(url, json):
                captured_payload.update(json)
                mock_response = AsyncMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"choices": [{"message": {"content": "Chat response"}}]}
                mock_response.raise_for_status = MagicMock()
                return mock_response

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = capture_post
            mock_client_class.return_value = mock_client

            messages = [
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "Hello"},
            ]

            await gateway.acomplete(
                prompt="",  # Not used for chat
                messages=messages,
                max_tokens=100,
                temperature=0.7,
            )

            assert "messages" in captured_payload
            assert captured_payload["messages"] == messages
            assert captured_payload["model"] == "test-model"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_streaming_request_format(self, gateway) -> None:
        """Test streaming request has stream=True."""
        with patch("httpx.AsyncClient") as mock_client_class:
            captured_payload = {}

            async def mock_stream(method, url, json):
                captured_payload.update(json)
                mock_response = AsyncMock()
                mock_response.status_code = 200
                mock_response.raise_for_status = MagicMock()
                mock_response.aiter_lines = AsyncMock(return_value=iter([]))
                mock_stream_ctx = AsyncMock()
                mock_stream_ctx.__aenter__.return_value = mock_response
                mock_stream_ctx.__aexit__.return_value = None
                return mock_stream_ctx

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.stream = mock_stream
            mock_client_class.return_value = mock_client

            async for _ in gateway.astream_complete(
                prompt="Stream test",
                max_tokens=200,
            ):
                pass

            assert captured_payload["stream"] is True


class TestHTTPCompletionGatewaySingleton:
    """Unit tests for global gateway singleton.

    Tests verify:
    - Singleton pattern
    - Reset functionality
    - Configuration loading
    """

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_get_http_gateway_singleton(self) -> None:
        """Test that get_http_gateway returns singleton."""
        from rag_service.inference.gateway import get_http_gateway, reset_http_gateway

        reset_http_gateway()

        gateway1 = await get_http_gateway()
        gateway2 = await get_http_gateway()

        assert gateway1 is gateway2

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_reset_http_gateway(self) -> None:
        """Test reset_http_gateway clears singleton."""
        from rag_service.inference.gateway import get_http_gateway, reset_http_gateway

        # Get first instance
        gateway1 = await get_http_gateway()
        reset_http_gateway()

        # Get new instance
        gateway2 = await get_http_gateway()

        assert gateway1 is not gateway2

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_gateway_loads_from_settings(self) -> None:
        """Test gateway loads configuration from settings."""
        from rag_service.inference.gateway import get_http_gateway, reset_http_gateway
        from rag_service.config import Settings
        from unittest.mock import patch

        reset_http_gateway()

        mock_settings = MagicMock(spec=Settings)
        mock_settings.cloud_completion.url = "http://configured-url.com/v1/completions"
        mock_settings.cloud_completion.model = "configured-model"
        mock_settings.cloud_completion.timeout = 45
        mock_settings.cloud_completion.auth_token = "configured-token"
        mock_settings.cloud_completion.max_retries = 5
        mock_settings.cloud_completion.retry_delay = 2.0
        mock_settings.cloud_completion.enabled = True

        with patch("rag_service.inference.gateway.get_settings", return_value=mock_settings):
            gateway = await get_http_gateway()

            assert gateway.url == "http://configured-url.com/v1/completions"
            assert gateway.model == "configured-model"
            assert gateway.timeout == 45

        reset_http_gateway()


class TestHTTPCompletionGatewayTimeoutHandling:
    """Unit tests for timeout handling.

    Tests verify:
    - Timeout parameter is used
    - Timeout errors are handled
    - Different timeout values
    """

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_timeout_in_http_client(self) -> None:
        """Test timeout is passed to httpx client."""
        from rag_service.inference.gateway import HTTPCompletionGateway

        gateway = HTTPCompletionGateway(
            url="http://test.com",
            model="test",
            timeout=60,  # 60 second timeout
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client

            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"output": "Response"}
            mock_response.raise_for_status = MagicMock()

            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            await gateway.acomplete("Test")

            # Verify timeout was passed to client
            mock_client_class.assert_called()
            call_kwargs = mock_client_class.call_args
            assert call_kwargs[1]["timeout"] == 60

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_timeout_error_handling(self) -> None:
        """Test timeout error is properly raised."""
        from rag_service.inference.gateway import HTTPCompletionGateway

        gateway = HTTPCompletionGateway(
            url="http://test.com",
            model="test",
            timeout=1,
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            async def timeout_post(*args, **kwargs):
                raise httpx.TimeoutException("Request timed out")

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = timeout_post
            mock_client_class.return_value = mock_client

            with pytest.raises(RuntimeError):
                await gateway.acomplete("Test")
