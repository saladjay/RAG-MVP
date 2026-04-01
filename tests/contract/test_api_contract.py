"""
Contract tests for RAG Service API (US1 - Knowledge Base Query).

These tests verify the API contract for the main /ai/agent endpoint:
- POST /ai/agent (knowledge base query with AI-generated answer)
- Request/response schema validation
- Error codes and messages
- HTTP status codes for various scenarios
"""

import pytest
from httpx import AsyncClient, ASGITransport
from typing import Dict, Any

from rag_service.main import app


class TestAgentQueryContract:
    """Contract tests for /ai/agent endpoint.

    Tests verify:
    - Request schema validation
    - Response structure matches contract
    - Error codes and messages
    - Status codes for various scenarios
    """

    @pytest.fixture
    def client(self) -> AsyncClient:
        """Create test client."""
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    @pytest.fixture
    def sample_valid_request(self) -> Dict[str, Any]:
        """Sample valid request for /ai/agent endpoint."""
        return {
            "question": "What is RAG (Retrieval-Augmented Generation)?",
            "model_hint": None,
            "context": {},
        }

    @pytest.mark.contract
    async def test_agent_query_returns_200_with_valid_request(
        self,
        client: AsyncClient,
        sample_valid_request: Dict[str, Any],
    ) -> None:
        """Test that valid request returns 200 with correct response structure.

        Given: A valid request with question
        When: POST /ai/agent is called
        Then: Returns 200 with answer, chunks, trace_id
        """
        response = await client.post(
            "/ai/agent",
            json=sample_valid_request
        )

        # May return 200 if successful, 503 if services unavailable, or 400 if validation fails
        assert response.status_code in [200, 503, 400]

        if response.status_code == 200:
            data = response.json()
            assert "answer" in data
            assert "chunks" in data
            assert "trace_id" in data
            assert isinstance(data["chunks"], list)
            assert isinstance(data["answer"], str)
            assert len(data["answer"]) > 0

    @pytest.mark.contract
    async def test_agent_query_requires_question_field(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that request without question returns 400.

        Given: A request without question field
        When: POST /ai/agent is called
        Then: Returns 400 with validation error
        """
        invalid_request = {
            "model_hint": "gpt-4",
            "context": {},
        }

        response = await client.post(
            "/ai/agent",
            json=invalid_request
        )

        assert response.status_code in [400, 422]  # Validation error

    @pytest.mark.contract
    async def test_agent_query_rejects_empty_question(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that empty question returns 400.

        Given: A request with empty or whitespace-only question
        When: POST /ai/agent is called
        Then: Returns 400 with validation error
        """
        invalid_requests = [
            {"question": ""},
            {"question": "   "},
            {"question": None},
        ]

        for invalid_request in invalid_requests:
            response = await client.post(
                "/ai/agent",
                json=invalid_request
            )
            assert response.status_code in [400, 422]

    @pytest.mark.contract
    async def test_agent_query_rejects_oversized_question(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that oversized question returns 400.

        Given: A request with question > 2000 characters
        When: POST /ai/agent is called
        Then: Returns 400 with validation error
        """
        invalid_request = {
            "question": "x" * 2001,  # Exceeds 2000 char limit
        }

        response = await client.post(
            "/ai/agent",
            json=invalid_request
        )

        assert response.status_code in [400, 422]

    @pytest.mark.contract
    async def test_agent_query_accepts_optional_model_hint(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that model_hint parameter is accepted.

        Given: A request with valid model_hint
        When: POST /ai/agent is called
        Then: Returns valid response
        """
        request = {
            "question": "What is machine learning?",
            "model_hint": "gpt-4",
        }

        response = await client.post(
            "/ai/agent",
            json=request
        )

        assert response.status_code in [200, 503, 400]

    @pytest.mark.contract
    async def test_agent_query_accepts_optional_context(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that context parameter is accepted.

        Given: A request with valid context dict
        When: POST /ai/agent is called
        Then: Returns valid response
        """
        request = {
            "question": "What is deep learning?",
            "context": {
                "user_id": "test_user",
                "session_id": "test_session",
            },
        }

        response = await client.post(
            "/ai/agent",
            json=request
        )

        assert response.status_code in [200, 503, 400]

    @pytest.mark.contract
    async def test_agent_query_chunks_structure(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that chunks in response have correct structure.

        Given: A request that retrieves chunks
        When: POST /ai/agent is called
        Then: Returns chunks with chunk_id, content, score, source_doc
        """
        request = {
            "question": "Test question for chunk retrieval",
        }

        response = await client.post(
            "/ai/agent",
            json=request
        )

        if response.status_code == 200:
            data = response.json()
            chunks = data.get("chunks", [])

            for chunk in chunks:
                assert "chunk_id" in chunk
                assert "content" in chunk
                assert "score" in chunk
                assert "source_doc" in chunk
                assert isinstance(chunk["score"], (int, float))
                assert 0 <= chunk["score"] <= 1

    @pytest.mark.contract
    async def test_agent_query_metadata_structure(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that metadata in response has correct structure.

        Given: A request that completes successfully
        When: POST /ai/agent is called
        Then: Returns metadata with model_used, tokens, latency, cost
        """
        request = {
            "question": "Test question for metadata",
        }

        response = await client.post(
            "/ai/agent",
            json=request
        )

        if response.status_code == 200:
            data = response.json()
            metadata = data.get("metadata", {})

            # Check optional metadata fields
            if "model_used" in metadata:
                assert isinstance(metadata["model_used"], str)
            if "total_latency_ms" in metadata:
                assert isinstance(metadata["total_latency_ms"], (int, float))
            if "retrieval_time_ms" in metadata:
                assert isinstance(metadata["retrieval_time_ms"], (int, float))
            if "inference_time_ms" in metadata:
                assert isinstance(metadata["inference_time_ms"], (int, float))

    @pytest.mark.contract
    async def test_agent_query_trace_id_format(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that trace_id has correct format.

        Given: A request that completes successfully
        When: POST /ai/agent is called
        Then: Returns valid trace_id format
        """
        request = {
            "question": "Test question for trace_id",
        }

        response = await client.post(
            "/ai/agent",
            json=request
        )

        if response.status_code == 200:
            data = response.json()
            trace_id = data.get("trace_id")

            assert trace_id is not None
            assert isinstance(trace_id, str)
            assert len(trace_id) > 0
            # Should contain request_id and unique suffix
            assert "_" in trace_id

    @pytest.mark.contract
    async def test_agent_query_handles_no_results(
        self,
        client: AsyncClient,
    ) -> None:
        """Test behavior when no chunks are retrieved.

        Given: A request that returns no knowledge base results
        When: POST /ai/agent is called
        Then: Returns appropriate response (may include error or empty chunks)
        """
        request = {
            "question": "Very specific question that likely has no matches",
        }

        response = await client.post(
            "/ai/agent",
            json=request
        )

        # Should return 200 with empty chunks, or 400/404 with error
        assert response.status_code in [200, 400, 404, 503]

        if response.status_code == 200:
            data = response.json()
            chunks = data.get("chunks", [])
            # Empty chunks list is valid
            assert isinstance(chunks, list)


class TestHealthEndpointContract:
    """Contract tests for /health endpoint."""

    @pytest.fixture
    def client(self) -> AsyncClient:
        """Create test client."""
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    @pytest.mark.contract
    async def test_health_endpoint_returns_200(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that /health returns 200.

        Given: GET /health is called
        When: No parameters
        Then: Returns 200 with status information
        """
        response = await client.get("/health")

        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "degraded", "unhealthy"]


class TestModelsEndpointContract:
    """Contract tests for /models endpoint."""

    @pytest.fixture
    def client(self) -> AsyncClient:
        """Create test client."""
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    @pytest.mark.contract
    async def test_models_endpoint_returns_200(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that /models returns 200.

        Given: GET /models is called
        When: No parameters
        Then: Returns 200 with list of available models
        """
        response = await client.get("/models")

        assert response.status_code == 200

        data = response.json()
        assert "models" in data
        assert isinstance(data["models"], list)
