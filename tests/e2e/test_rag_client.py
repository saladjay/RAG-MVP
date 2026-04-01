"""
Integration tests for RAG Service client.

Note: These tests require a running RAG Service or use mocking.
For true integration tests, run with a real RAG Service instance.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from e2e_test.clients.rag_client import RAGClient
from e2e_test.core.exceptions import RAGClientError, RAGConnectionError, RAGServerError, RAGTimeoutError


@pytest.fixture
def client():
    """Return RAGClient instance for testing."""
    return RAGClient(
        base_url="http://localhost:8000",
        timeout_seconds=5,
        retry_count=2
    )


@pytest.mark.asyncio
async def test_query_success(client):
    """Test successful query to RAG Service."""
    mock_response = {
        "answer": "RAG Service combines vector search with LLM generation.",
        "trace_id": "test-trace-123",
        "source_documents": [
            {"id": "doc_001", "content": "RAG introduction", "score": 0.92}
        ],
        "metadata": {
            "model": "gpt-4",
            "latency_ms": 500
        }
    }

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_http_client = AsyncMock()
        mock_response_obj = AsyncMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json = Mock(return_value=mock_response)
        mock_response_obj.headers = {"content-type": "application/json"}

        mock_http_client.post = AsyncMock(return_value=mock_response_obj)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)

        mock_client_class.return_value = mock_http_client

        result = await client.query("What is RAG?")

        assert result["answer"] == mock_response["answer"]
        assert result["trace_id"] == "test-trace-123"
        assert len(result["source_documents"]) == 1
        assert result["source_documents"][0]["id"] == "doc_001"


@pytest.mark.asyncio
async def test_query_with_trace_id(client):
    """Test query with custom trace ID."""
    mock_response = {
        "answer": "Test answer",
        "trace_id": "custom-trace-456",
        "source_documents": []
    }

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_http_client = AsyncMock()
        mock_response_obj = AsyncMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json = Mock(return_value=mock_response)
        mock_response_obj.headers = {"content-type": "application/json"}

        mock_http_client.post = AsyncMock(return_value=mock_response_obj)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)

        mock_client_class.return_value = mock_http_client

        result = await client.query("Test question", trace_id="custom-trace-456")

        # Verify the payload includes the trace_id
        call_args = mock_http_client.post.call_args
        payload = call_args[1]["json"]
        assert payload["trace_id"] == "custom-trace-456"


@pytest.mark.asyncio
async def test_query_5xx_error_raises_server_error(client):
    """Test that 5xx status raises RAGServerError."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_http_client = AsyncMock()
        mock_response_obj = AsyncMock()
        mock_response_obj.status_code = 500
        mock_response_obj.json = Mock(return_value={"error": {"message": "Internal Server Error"}})
        mock_response_obj.headers = {"content-type": "application/json"}

        mock_http_client.post = AsyncMock(return_value=mock_response_obj)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)

        mock_client_class.return_value = mock_http_client

        with pytest.raises(RAGServerError) as exc_info:
            await client.query("Test question")

        assert exc_info.value.details["status_code"] == 500


@pytest.mark.asyncio
async def test_query_4xx_error_raises_client_error(client):
    """Test that 4xx status raises RAGClientError."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_http_client = AsyncMock()
        mock_response_obj = AsyncMock()
        mock_response_obj.status_code = 400
        mock_response_obj.json = Mock(return_value={
            "error": {
                "message": "Invalid request",
                "code": "INVALID_REQUEST"
            }
        })
        mock_response_obj.headers = {"content-type": "application/json"}

        mock_http_client.post = AsyncMock(return_value=mock_response_obj)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)

        mock_client_class.return_value = mock_http_client

        with pytest.raises(RAGClientError) as exc_info:
            await client.query("Invalid question")

        assert exc_info.value.details["status_code"] == 400
        assert "Invalid request" in str(exc_info.value)


@pytest.mark.asyncio
async def test_query_timeout_raises_timeout_error(client):
    """Test that timeout raises RAGTimeoutError."""
    import httpx

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(side_effect=httpx.TimeoutException("Request timeout"))
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)

        mock_client_class.return_value = mock_http_client

        with pytest.raises(RAGTimeoutError) as exc_info:
            await client.query("Test question")

        assert exc_info.value.details["timeout_seconds"] == 5


@pytest.mark.asyncio
async def test_query_connection_error_raises_connection_error(client):
    """Test that connection failure raises RAGConnectionError."""
    import httpx

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)

        mock_client_class.return_value = mock_http_client

        with pytest.raises(RAGConnectionError) as exc_info:
            await client.query("Test question")

        assert "Connection refused" in str(exc_info.value)
        assert exc_info.value.details.get("url") == "http://localhost:8000"


@pytest.mark.asyncio
async def test_query_retry_on_timeout(client):
    """Test that client retries on timeout."""
    import httpx

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_http_client = AsyncMock()

        # First two calls timeout, third succeeds
        mock_response_obj = AsyncMock()
        mock_response_obj.status_code = 200
        mock_response_obj.json = Mock(return_value={"answer": "Success", "trace_id": "retry-test", "source_documents": []})
        mock_response_obj.headers = {"content-type": "application/json"}

        call_count = 0
        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.TimeoutException("Timeout")
            return mock_response_obj

        mock_http_client.post = AsyncMock(side_effect=side_effect)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock()

        mock_client_class.return_value = mock_http_client

        result = await client.query("Test question")

        assert result["answer"] == "Success"
        assert call_count == 3  # 2 failures + 1 success


@pytest.mark.asyncio
async def test_health_check_success(client):
    """Test successful health check."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_http_client = AsyncMock()
        mock_response_obj = AsyncMock()
        mock_response_obj.status_code = 200

        mock_http_client.get = AsyncMock(return_value=mock_response_obj)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock()

        mock_client_class.return_value = mock_http_client

        is_healthy = await client.health_check()

        assert is_healthy is True


@pytest.mark.asyncio
async def test_health_check_failure(client):
    """Test health check with non-200 status."""
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_http_client = AsyncMock()
        mock_response_obj = AsyncMock()
        mock_response_obj.status_code = 503

        mock_http_client.get = AsyncMock(return_value=mock_response_obj)
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock()

        mock_client_class.return_value = mock_http_client

        is_healthy = await client.health_check()

        assert is_healthy is False


@pytest.mark.asyncio
async def test_health_check_connection_error(client):
    """Test health check with connection error."""
    import httpx

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)

        mock_client_class.return_value = mock_http_client

        is_healthy = await client.health_check()

        assert is_healthy is False
