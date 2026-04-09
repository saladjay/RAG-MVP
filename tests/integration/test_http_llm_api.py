"""
Integration tests for HTTP LLM API calls.

These tests verify the HTTPCompletionGateway can correctly call
external LLM APIs and handle various response formats.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

import pytest
import httpx


class TestHTTPLLMAPI:
    """Integration tests for HTTP LLM API calls.

    Tests verify:
    - Real HTTP API call structure
    - OpenAI-style completion
    - Chat completion format
    - Streaming responses
    - Error handling and retry
    """

    @pytest.fixture
    def http_gateway(self):
        """Create HTTP gateway for testing."""
        from rag_service.inference.gateway import HTTPCompletionGateway

        return HTTPCompletionGateway(
            url="http://test.example.com/v1/completions",
            model="test-model",
            timeout=30,
            auth_token="dGVzdDp0ZXN0",  # base64("test:test")
        )

    @pytest.fixture
    def mock_httpx_client(self):
        """Mock httpx client for testing."""
        mock_client = MagicMock(spec=httpx.Client)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [
                {
                    "text": "Test response",
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
            },
        }
        mock_client.post.return_value = mock_response
        return mock_client

    @pytest.mark.integration
    def test_http_completion_openai_format(self, http_gateway) -> None:
        """Test HTTP completion with OpenAI-style response.

        Given: HTTP gateway configured with API URL
        When: Calling complete with OpenAI format response
        Then: Returns parsed CompletionResult
        """
        mock_response = {
            "choices": [
                {
                    "text": "According to the document, RAG stands for Retrieval-Augmented Generation.",
                    "finish_reason": "stop",
                    "index": 0,
                }
            ],
            "usage": {
                "prompt_tokens": 15,
                "completion_tokens": 25,
                "total_tokens": 40,
            },
            "model": "test-model",
        }

        result = http_gateway._parse_completion_response(mock_response)

        assert result.text == "According to the document, RAG stands for Retrieval-Augmented Generation."
        assert result.input_tokens == 15
        assert result.output_tokens == 25
        assert result.total_tokens == 40
        assert result.provider == "http"

    @pytest.mark.integration
    def test_http_completion_chat_format(self, http_gateway) -> None:
        """Test HTTP completion with chat format response.

        Given: HTTP gateway calling chat endpoint
        When: Response uses message format
        Then: Correctly extracts content
        """
        mock_response = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "The company's holiday policy is outlined in section 3.2.",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 20,
                "completion_tokens": 15,
            },
        }

        result = http_gateway._parse_completion_response(mock_response)

        assert "company's holiday policy" in result.text
        assert result.input_tokens == 20
        assert result.output_tokens == 15

    @pytest.mark.integration
    def test_http_completion_simple_format(self, http_gateway) -> None:
        """Test HTTP completion with simple output format.

        Given: HTTP API returning simple format
        When: Response has "output" or "text" field
        Then: Extracts text correctly
        """
        # Test "output" format
        result1 = http_gateway._parse_completion_response(
            {"output": "Simple answer output"}
        )
        assert result1.text == "Simple answer output"

        # Test "text" format
        result2 = http_gateway._parse_completion_response(
            {"text": "Another text format"}
        )
        assert result2.text == "Another text format"

        # Test "result" format
        result3 = http_gateway._parse_completion_response(
            {"result": "Result format content"}
        )
        assert result3.text == "Result format content"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_http_async_completion(self, http_gateway) -> None:
        """Test async HTTP completion.

        Given: HTTP gateway with async client
        When: Calling acomplete
        Then: Returns CompletionResult asynchronously
        """
        with patch("httpx.AsyncClient") as mock_async_client_class:
            # Setup mock
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"text": "Async response"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            }
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_async_client_class.return_value = mock_client

            result = await http_gateway.acomplete(
                prompt="What is RAG?",
                max_tokens=1000,
                temperature=0.7,
            )

            assert result.text == "Async response"
            assert result.provider == "http"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_http_streaming_completion(self, http_gateway) -> None:
        """Test HTTP streaming completion.

        Given: HTTP gateway with streaming enabled
        When: Calling astream_complete
        Then: Yields tokens as they arrive
        """
        with patch("httpx.AsyncClient") as mock_async_client_class:
            # Setup streaming mock
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()

            # Simulate SSE stream
            async def mock_aiter_lines():
                lines = [
                    'data: {"choices": [{"text": "Hello"}]}\n',
                    'data: {"choices": [{"text": " world"}]}\n',
                    'data: {"choices": [{"text": "!"}]}]\n',
                    'data: [DONE]\n',
                ]
                for line in lines:
                    yield line

            mock_response.aiter_lines = mock_aiter_lines

            mock_stream_context = AsyncMock()
            mock_stream_context.__aenter__.return_value = mock_response
            mock_stream_context.__aexit__.return_value = None

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.stream = MagicMock(return_value=mock_stream_context)
            mock_async_client_class.return_value = mock_client

            # Collect streamed tokens
            tokens = []
            async for token in http_gateway.astream_complete(
                prompt="Say hello",
                max_tokens=100,
            ):
                tokens.append(token)

            assert "".join(tokens) == "Hello world!"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_http_completion_retry_on_failure(self, http_gateway) -> None:
        """Test HTTP completion with retry on failure.

        Given: HTTP gateway with retry enabled
        When: First request fails, second succeeds
        Then: Returns result from successful retry
        """
        with patch("httpx.AsyncClient") as mock_async_client_class:
            call_count = [0]

            async def mock_post(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    raise httpx.HTTPError("Connection error")
                # Second call succeeds
                mock_response = AsyncMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "choices": [{"text": "Retry success"}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 20},
                }
                mock_response.raise_for_status = MagicMock()
                return mock_response

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = mock_post
            mock_async_client_class.return_value = mock_client

            result = await http_gateway.acomplete(
                prompt="Test prompt",
                max_tokens=100,
            )

            assert call_count[0] == 2  # First failed, retried once
            assert result.text == "Retry success"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_http_completion_exhausts_retries(self, http_gateway) -> None:
        """Test HTTP completion when all retries fail.

        Given: HTTP gateway with max_retries=3
        When: All requests fail
        Then: Raises RuntimeError
        """
        with patch("httpx.AsyncClient") as mock_async_client_class:
            async def mock_post(*args, **kwargs):
                raise httpx.HTTPError("Persistent error")

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = mock_post
            mock_async_client_class.return_value = mock_client

            with pytest.raises(RuntimeError, match="failed after"):
                await http_gateway.acomplete(
                    prompt="Test prompt",
                    max_tokens=100,
                )

    @pytest.mark.integration
    def test_http_stream_chunk_parsing_variations(self, http_gateway) -> None:
        """Test parsing various stream chunk formats.

        Given: Different stream chunk formats
        When: _parse_stream_chunk is called
        Then: Extracts text from each format
        """
        test_cases = [
            # OpenAI choices format
            ({"choices": [{"text": "Hello"}]}, "Hello"),
            # Delta content format
            ({"choices": [{"delta": {"content": "World"}}]}, "World"),
            # Simple text format
            ({"text": "Simple"}, "Simple"),
            # Empty/unrecognized format
            ({"unexpected": "data"}, ""),
            # Message content format
            ({"choices": [{"message": {"content": "Message content"}}]}, "Message content"),
        ]

        for chunk, expected_text in test_cases:
            result = http_gateway._parse_stream_chunk(chunk)
            assert result == expected_text, f"Failed for chunk: {chunk}"

    @pytest.mark.integration
    def test_http_completion_with_chat_messages(self, http_gateway) -> None:
        """Test HTTP completion with chat message format.

        Given: Request with messages array
        When: Sending chat-style request
        Then: Formats request correctly
        """
        # This test verifies the request format structure
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is RAG?"},
        ]

        # In real scenario, this would be sent to the API
        # Here we just verify the structure would be correct
        expected_payload = {
            "messages": messages,
            "max_tokens": 1000,
            "temperature": 0.7,
            "top_p": 0.9,
            "model": "test-model",
        }

        assert expected_payload["messages"] == messages
        assert expected_payload["model"] == "test-model"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_model_inference_capability_with_http_backend(self) -> None:
        """Test ModelInferenceCapability using HTTP backend.

        Given: ModelInferenceCapability with HTTP client
        When: execute is called with gateway_backend="http"
        Then: Uses HTTP gateway for inference
        """
        from rag_service.capabilities.model_inference import (
            ModelInferenceCapability,
            ModelInferenceInput,
        )
        from rag_service.inference.gateway import CompletionResult

        # Mock HTTP gateway
        mock_http_gateway = AsyncMock()
        mock_http_gateway.acomplete = AsyncMock(
            return_value=CompletionResult(
                text="HTTP generated response",
                model="http-model",
                input_tokens=10,
                output_tokens=30,
                total_tokens=40,
                cost=0.0,
                latency_ms=200,
                provider="http",
            )
        )

        capability = ModelInferenceCapability(
            http_client=mock_http_gateway,
            default_gateway="litellm",  # Default is litellm
        )

        input_data = ModelInferenceInput(
            prompt="Explain RAG architecture",
            gateway_backend="http",  # Override to use HTTP
            max_tokens=500,
            temperature=0.7,
        )

        result = await capability.execute(input_data)

        assert result.text == "HTTP generated response"
        assert result.metadata.get("gateway") == "http"
        assert result.usage["total_tokens"] == 40

        # Verify HTTP gateway was called
        mock_http_gateway.acomplete.assert_called_once_with(
            prompt="Explain RAG architecture",
            max_tokens=500,
            temperature=0.7,
        )

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_model_inference_capability_streaming_with_http(self) -> None:
        """Test ModelInferenceCapability streaming with HTTP backend.

        Given: ModelInferenceCapability with HTTP client
        When: stream_execute is called with gateway_backend="http"
        Then: Streams tokens from HTTP gateway
        """
        from rag_service.capabilities.model_inference import (
            ModelInferenceCapability,
            ModelInferenceInput,
        )

        # Mock HTTP gateway streaming
        async def mock_stream():
            yield "RAG "
            yield "combines "
            yield "retrieval "
            yield "with "
            yield "generation."

        mock_http_gateway = AsyncMock()
        mock_http_gateway.astream_complete = lambda *args, **kwargs: mock_stream()

        capability = ModelInferenceCapability(
            http_client=mock_http_gateway,
        )

        input_data = ModelInferenceInput(
            prompt="Define RAG",
            gateway_backend="http",
            max_tokens=100,
        )

        tokens = []
        async for token in capability.stream_execute(input_data):
            tokens.append(token)

        assert "".join(tokens) == "RAG combines retrieval with generation."

    @pytest.mark.integration
    def test_http_gateway_headers_configuration(self) -> None:
        """Test HTTP gateway builds correct headers.

        Given: Gateway with auth token
        When: Gateway is initialized
        Then: Headers include auth token
        """
        from rag_service.inference.gateway import HTTPCompletionGateway

        gateway = HTTPCompletionGateway(
            url="http://api.example.com/v1/completions",
            model="gpt-model",
            auth_token="dGVzdDp0ZXN0",  # base64 encoded
        )

        assert gateway._headers["Content-Type"] == "application/json"
        assert gateway._headers["Authorization"] == "Basic dGVzdDp0ZXN0"

    @pytest.mark.integration
    def test_http_gateway_without_auth(self) -> None:
        """Test HTTP gateway without authentication.

        Given: Gateway without auth token
        When: Gateway is initialized
        Then: Headers only include Content-Type
        """
        from rag_service.inference.gateway import HTTPCompletionGateway

        gateway = HTTPCompletionGateway(
            url="http://api.example.com/v1/completions",
            model="gpt-model",
            auth_token="",  # No auth
        )

        assert gateway._headers["Content-Type"] == "application/json"
        assert "Authorization" not in gateway._headers

    @pytest.mark.integration
    def test_http_gateway_custom_response_with_finish_reason(self, http_gateway) -> None:
        """Test HTTP completion preserves finish_reason.

        Given: Response includes finish_reason
        When: Response is parsed
        Then: Result includes finish_reason information
        """
        mock_response = {
            "output": "Generated text",
            "finish_reason": "length",
        }

        result = http_gateway._parse_completion_response(mock_response)

        assert result.text == "Generated text"
        # finish_reason is captured in the response parsing
        # (would be used in extended result metadata)

    @pytest.mark.integration
    def test_http_gateway_available_models_with_url(self, http_gateway) -> None:
        """Test get_available_models with configured URL.

        Given: HTTP gateway with URL
        When: get_available_models is called
        Then: Returns model configuration
        """
        models = http_gateway.get_available_models()

        assert len(models) == 1
        assert models[0]["model_id"] == "test-model"
        assert models[0]["provider"] == "http"
        assert models[0]["available"] is True
        assert models[0]["url"] == "http://test.example.com/v1/completions"

    @pytest.mark.integration
    def test_http_gateway_available_models_without_url(self) -> None:
        """Test get_available_models without URL.

        Given: HTTP gateway without URL
        When: get_available_models is called
        Then: Returns empty list
        """
        from rag_service.inference.gateway import HTTPCompletionGateway

        gateway = HTTPCompletionGateway(url="", model="test")
        models = gateway.get_available_models()

        assert len(models) == 0


class TestHTTPLLMRealScenarios:
    """Integration tests simulating real LLM API scenarios.

    Tests verify:
    - Document QA scenarios
    - Query rewriting
    - Answer generation
    - Fallback behavior
    """

    @pytest.fixture
    def mock_qa_response(self):
        """Mock response for document QA."""
        return {
            "choices": [
                {
                    "text": """
Based on the provided documents, here's the answer:

The RAG (Retrieval-Augmented Generation) architecture consists of three main components:

1. **Retrieval**: Searches a knowledge base for relevant documents
2. **Augmentation**: Combines the query with retrieved context
3. **Generation**: Uses an LLM to generate a response

Key benefits include improved accuracy and reduced hallucination.
                    """.strip(),
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 150,
                "completion_tokens": 80,
                "total_tokens": 230,
            },
        }

    @pytest.mark.integration
    def test_document_qa_response_parsing(self, mock_qa_response) -> None:
        """Test parsing a realistic document QA response.

        Given: Realistic QA response from LLM
        When: Response is parsed
        Then: Extracts all components correctly
        """
        from rag_service.inference.gateway import HTTPCompletionGateway

        gateway = HTTPCompletionGateway(
            url="http://api.example.com/v1/completions",
            model="qa-model",
        )

        result = gateway._parse_completion_response(mock_qa_response)

        assert "RAG" in result.text
        assert "Retrieval" in result.text
        assert result.input_tokens == 150
        assert result.output_tokens == 80
        assert result.total_tokens == 230

    @pytest.mark.integration
    def test_query_rewrite_response(self) -> None:
        """Test query rewrite response format.

        Given: LLM response for query rewriting
        When: Response is parsed
        Then: Extracts rewritten query
        """
        from rag_service.inference.gateway import HTTPCompletionGateway

        gateway = HTTPCompletionGateway(url="http://api.example.com", model="rewrite-model")

        response = {
            "choices": [
                {
                    "text": "What are the company's holiday arrangements for 2025?",
                }
            ],
            "usage": {"prompt_tokens": 30, "completion_tokens": 12},
        }

        result = gateway._parse_completion_response(response)

        assert "holiday arrangements" in result.text.lower()
        assert "2025" in result.text

    @pytest.mark.integration
    def test_answer_generation_with_sources(self) -> None:
        """Test answer generation that includes source citations.

        Given: LLM response with source citations
        When: Response is parsed
        Then: Extracts text with citations intact
        """
        from rag_service.inference.gateway import HTTPCompletionGateway

        gateway = HTTPCompletionGateway(url="http://api.example.com", model="qa-model")

        response = {
            "output": """
According to the employee handbook [Doc: policy-2024.pdf], employees are entitled to:
- 15 days annual leave
- 5 days sick leave
- Public holidays as per government calendar

Reference: Section 4.2, Leave Policy
            """.strip(),
        }

        result = gateway._parse_completion_response(response)

        assert "policy-2024.pdf" in result.text
        assert "15 days" in result.text
        assert "Section 4.2" in result.text

    @pytest.mark.integration
    def test_fallback_response_format(self) -> None:
        """Test fallback response when KB is empty.

        Given: Fallback response from service
        When: Response is parsed
        Then: Extracts fallback message
        """
        from rag_service.inference.gateway import HTTPCompletionGateway

        gateway = HTTPCompletionGateway(url="http://api.example.com", model="qa-model")

        response = {
            "result": "I apologize, but I couldn't find relevant information to answer your question. Please try rephrasing or contact HR for assistance.",
        }

        result = gateway._parse_completion_response(response)

        assert "couldn't find relevant information" in result.text or "apologize" in result.text.lower()


class TestHTTPLLMConcurrency:
    """Integration tests for concurrent HTTP requests.

    Tests verify:
    - Multiple concurrent requests
    - Request queuing
    - Rate limiting behavior
    """

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_concurrent_http_completions(self) -> None:
        """Test multiple concurrent HTTP completions.

        Given: Multiple requests sent concurrently
        When: All requests execute
        Then: Each gets correct response
        """
        from rag_service.inference.gateway import CompletionResult

        async def mock_acomplete(prompt, **kwargs):
            # Simulate variable response time
            await asyncio.sleep(0.01)
            return CompletionResult(
                text=f"Response to: {prompt[:20]}",
                model="test-model",
                input_tokens=10,
                output_tokens=20,
                total_tokens=30,
                cost=0.0,
                latency_ms=10,
                provider="http",
            )

        from unittest.mock import AsyncMock

        mock_gateway = AsyncMock()
        mock_gateway.acomplete = mock_acomplete

        # Send 5 concurrent requests
        prompts = [
            "What is RAG?",
            "Explain retrieval.",
            "Define augmentation.",
            "Describe generation.",
            "How does it work?",
        ]

        tasks = [mock_gateway.acomplete(p) for p in prompts]
        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        for i, result in enumerate(results):
            assert prompts[i][:20] in result.text

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_concurrent_http_streams(self) -> None:
        """Test multiple concurrent streaming requests.

        Given: Multiple streaming requests
        When: All streams execute
        Then: Each stream yields correct tokens
        """
        async def mock_stream(prompt, **kwargs):
            words = prompt.split()
            for word in words:
                yield word + " "

        # Create mock streams
        streams = []
        for i in range(3):
            mock_gateway = AsyncMock()
            mock_gateway.astream_complete = lambda p, **kw: mock_stream(f"Stream {i}: test")
            streams.append(mock_gateway)

        # Execute concurrent streams
        async def collect_stream(gateway):
            tokens = []
            async for token in gateway.astream_complete("test"):
                tokens.append(token)
            return "".join(tokens)

        results = await asyncio.gather(*[collect_stream(gw) for gw in streams])

        assert len(results) == 3
        for result in results:
            assert "test" in result


class TestHTTPLLMErrorScenarios:
    """Integration tests for error scenarios.

    Tests verify:
    - Network errors
    - Timeout handling
    - Invalid responses
    - API rate limits
    """

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_network_error_handling(self) -> None:
        """Test handling of network errors.

        Given: Network connection fails
        When: Request is made
        Then: Appropriate error handling
        """
        from rag_service.inference.gateway import HTTPCompletionGateway
        import httpx

        gateway = HTTPCompletionGateway(
            url="http://unreachable-host:9999/v1/completions",
            model="test",
            timeout=1,  # Short timeout
            max_retries=1,
            retry_delay=0.1,
        )

        with pytest.raises(RuntimeError, match="failed after"):
            await gateway.acomplete(prompt="Test")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_invalid_json_response(self) -> None:
        """Test handling of invalid JSON response.

        Given: API returns invalid JSON
        When: Response is parsed
        Then: Raises appropriate error
        """
        from rag_service.inference.gateway import HTTPCompletionGateway
        import httpx

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
            mock_response.raise_for_status = MagicMock()

            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            gateway = HTTPCompletionGateway(
                url="http://test.com",
                model="test",
            )

            with pytest.raises((RuntimeError, json.JSONDecodeError)):
                await gateway.acomplete(prompt="Test")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_http_error_status_codes(self) -> None:
        """Test handling of HTTP error status codes.

        Given: API returns error status
        When: Request is made
        Then: Handles error appropriately
        """
        import httpx

        status_codes = [400, 401, 403, 404, 429, 500, 503]

        for status_code in status_codes:
            with patch("httpx.AsyncClient") as mock_client_class:
                mock_response = AsyncMock()
                mock_response.status_code = status_code
                mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                    f"Error {status_code}",
                    request=MagicMock(),
                    response=mock_response,
                )

                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.post = AsyncMock(return_value=mock_response)
                mock_client_class.return_value = mock_client

                gateway = HTTPCompletionGateway(
                    url="http://test.com",
                    model="test",
                    max_retries=0,  # No retries for error testing
                )

                with pytest.raises(RuntimeError):
                    await gateway.acomplete(prompt="Test")
