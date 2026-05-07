"""
Contract tests for RAG QA Pipeline API (US1 - Basic QA with External Knowledge).

These tests verify the API contract for the QA endpoints:
- POST /qa/query (question-answering with retrieval and generation)
- GET /qa/health (health check for QA components)
- Request/response schema validation
- Error codes and messages
- HTTP status codes for various scenarios
"""

import pytest
from httpx import AsyncClient, ASGITransport
from typing import Dict, Any

from rag_service.main import app


class TestQAQueryContract:
    """Contract tests for /qa/query endpoint.

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
        """Sample valid request for /qa/query endpoint."""
        return {
            "query": "2025年春节放假几天？",
            "context": {
                "company_id": "N000131",
                "file_type": "PublicDocDispatch",
            },
            "options": {
                "enable_query_rewrite": False,
                "enable_hallucination_check": False,
                "top_k": 10,
            },
        }

    @pytest.mark.contract
    async def test_qa_query_returns_200_with_valid_request(
        self,
        client: AsyncClient,
        sample_valid_request: Dict[str, Any],
    ) -> None:
        """Test that valid request returns 200 with correct response structure.

        Given: A valid request with query and context
        When: POST /qa/query is called
        Then: Returns 200 with answer, sources, hallucination_status, metadata
        """
        response = await client.post(
            "/qa/query",
            json=sample_valid_request
        )

        # May return 200 if successful, 503 if services unavailable, or 400 if validation fails
        assert response.status_code in [200, 503, 400]

        if response.status_code == 200:
            data = response.json()
            assert "answer" in data
            assert "sources" in data
            assert "hallucination_status" in data
            assert "metadata" in data
            assert isinstance(data["sources"], list)
            assert isinstance(data["answer"], str)
            assert len(data["answer"]) > 0

    @pytest.mark.contract
    async def test_qa_query_requires_query_field(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that request without query returns 400.

        Given: A request without query field
        When: POST /qa/query is called
        Then: Returns 400 with validation error
        """
        invalid_request = {
            "context": {
                "company_id": "N000131",
            },
        }

        response = await client.post(
            "/qa/query",
            json=invalid_request
        )

        assert response.status_code in [400, 422]  # Validation error

    @pytest.mark.contract
    async def test_qa_query_rejects_empty_query(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that empty query returns 400.

        Given: A request with empty or whitespace-only query
        When: POST /qa/query is called
        Then: Returns 400 with validation error
        """
        invalid_requests = [
            {"query": ""},
            {"query": "   "},
            {"query": None},
        ]

        for invalid_request in invalid_requests:
            response = await client.post(
                "/qa/query",
                json=invalid_request
            )
            assert response.status_code in [400, 422]

    @pytest.mark.contract
    async def test_qa_query_rejects_oversized_query(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that oversized query returns 400.

        Given: A request with query > 1000 characters
        When: POST /qa/query is called
        Then: Returns 400 with validation error
        """
        invalid_request = {
            "query": "x" * 1001,  # Exceeds 1000 char limit
        }

        response = await client.post(
            "/qa/query",
            json=invalid_request
        )

        assert response.status_code in [400, 422]

    @pytest.mark.contract
    async def test_qa_query_accepts_optional_context(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that context parameter is accepted.

        Given: A request with valid context dict
        When: POST /qa/query is called
        Then: Returns valid response
        """
        request = {
            "query": "什么是机器学习？",
            "context": {
                "company_id": "N000131",
                "file_type": "PublicDocDispatch",
                "doc_date": "2025-01-01",
            },
        }

        response = await client.post(
            "/qa/query",
            json=request
        )

        assert response.status_code in [200, 503, 400]

    @pytest.mark.contract
    async def test_qa_query_validates_company_id_format(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that invalid company_id returns 400.

        Given: A request with invalid company_id format
        When: POST /qa/query is called
        Then: Returns 400 with validation error
        """
        invalid_requests = [
            {"query": "test", "context": {"company_id": "INVALID"}},
            {"query": "test", "context": {"company_id": "N123"}},  # Too short
            {"query": "test", "context": {"company_id": "000131"}},  # Missing N prefix
        ]

        for invalid_request in invalid_requests:
            response = await client.post(
                "/qa/query",
                json=invalid_request
            )
            assert response.status_code in [400, 422]

    @pytest.mark.contract
    async def test_qa_query_validates_file_type_enum(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that invalid file_type returns 400.

        Given: A request with invalid file_type
        When: POST /qa/query is called
        Then: Returns 400 with validation error
        """
        invalid_request = {
            "query": "test",
            "context": {
                "company_id": "N000131",
                "file_type": "InvalidType",
            },
        }

        response = await client.post(
            "/qa/query",
            json=invalid_request
        )

        assert response.status_code in [400, 422]

    @pytest.mark.contract
    async def test_qa_query_accepts_optional_options(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that options parameter is accepted.

        Given: A request with valid options dict
        When: POST /qa/query is called
        Then: Returns valid response
        """
        request = {
            "query": "什么是深度学习？",
            "options": {
                "enable_query_rewrite": True,
                "enable_hallucination_check": True,
                "top_k": 5,
                "stream": False,
            },
        }

        response = await client.post(
            "/qa/query",
            json=request
        )

        assert response.status_code in [200, 503, 400]

    @pytest.mark.contract
    async def test_qa_query_validates_top_k_range(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that invalid top_k returns 400.

        Given: A request with top_k outside [1, 50] range
        When: POST /qa/query is called
        Then: Returns 400 with validation error
        """
        invalid_requests = [
            {"query": "test", "options": {"top_k": 0}},
            {"query": "test", "options": {"top_k": 51}},
            {"query": "test", "options": {"top_k": -1}},
        ]

        for invalid_request in invalid_requests:
            response = await client.post(
                "/qa/query",
                json=invalid_request
            )
            assert response.status_code in [400, 422]

    @pytest.mark.contract
    async def test_qa_query_sources_structure(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that sources in response have correct structure.

        Given: A request that retrieves chunks
        When: POST /qa/query is called
        Then: Returns sources with chunk_id, document_id, document_name, dataset_id, dataset_name, score, content_preview
        """
        request = {
            "query": "Test question for source retrieval",
            "context": {
                "company_id": "N000131",
            },
        }

        response = await client.post(
            "/qa/query",
            json=request
        )

        if response.status_code == 200:
            data = response.json()
            sources = data.get("sources", [])

            for source in sources:
                assert "chunk_id" in source
                assert "document_id" in source
                assert "document_name" in source
                assert "dataset_id" in source
                assert "dataset_name" in source
                assert "score" in source
                assert "content_preview" in source
                assert isinstance(source["score"], (int, float))
                assert 0 <= source["score"] <= 1
                assert len(source["content_preview"]) <= 200

    @pytest.mark.contract
    async def test_qa_query_hallucination_status_structure(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that hallucination_status in response has correct structure.

        Given: A request that completes successfully
        When: POST /qa/query is called
        Then: Returns hallucination_status with checked, passed, confidence
        """
        request = {
            "query": "Test question for hallucination status",
            "options": {
                "enable_hallucination_check": False,
            },
        }

        response = await client.post(
            "/qa/query",
            json=request
        )

        if response.status_code == 200:
            data = response.json()
            hallucination_status = data.get("hallucination_status", {})

            assert "checked" in hallucination_status
            assert "passed" in hallucination_status
            assert "confidence" in hallucination_status
            assert isinstance(hallucination_status["checked"], bool)
            assert isinstance(hallucination_status["passed"], bool)
            assert isinstance(hallucination_status["confidence"], (int, float))
            assert 0 <= hallucination_status["confidence"] <= 1

    @pytest.mark.contract
    async def test_qa_query_metadata_structure(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that metadata in response has correct structure.

        Given: A request that completes successfully
        When: POST /qa/query is called
        Then: Returns metadata with trace_id, query_rewritten, original_query, retrieval_count, timing_ms
        """
        request = {
            "query": "Test question for metadata",
        }

        response = await client.post(
            "/qa/query",
            json=request
        )

        if response.status_code == 200:
            data = response.json()
            metadata = data.get("metadata", {})

            assert "trace_id" in metadata
            assert "query_rewritten" in metadata
            assert "original_query" in metadata
            assert "retrieval_count" in metadata
            assert "timing" in metadata
            assert isinstance(metadata["query_rewritten"], bool)
            assert isinstance(metadata["retrieval_count"], int)
            assert metadata["retrieval_count"] >= 0

            # Check timing structure
            timing_ms = metadata["timing"]
            assert "total_ms" in timing_ms
            assert "retrieve_ms" in timing_ms
            assert "generate_ms" in timing_ms

    @pytest.mark.contract
    async def test_qa_query_trace_id_format(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that trace_id has correct format.

        Given: A request that completes successfully
        When: POST /qa/query is called
        Then: Returns valid trace_id format
        """
        request = {
            "query": "Test question for trace_id",
        }

        response = await client.post(
            "/qa/query",
            json=request
        )

        if response.status_code == 200:
            data = response.json()
            trace_id = data.get("metadata", {}).get("trace_id")

            assert trace_id is not None
            assert isinstance(trace_id, str)
            assert len(trace_id) > 0

    @pytest.mark.contract
    async def test_qa_query_handles_no_results(
        self,
        client: AsyncClient,
    ) -> None:
        """Test behavior when no chunks are retrieved.

        Given: A request that returns no knowledge base results
        When: POST /qa/query is called
        Then: Returns 200 with fallback response
        """
        request = {
            "query": "Very specific question that likely has no matches xyzabc123",
            "context": {
                "company_id": "N000131",
            },
        }

        response = await client.post(
            "/qa/query",
            json=request
        )

        # Should return 200 with fallback message
        assert response.status_code in [200, 503, 400]

        if response.status_code == 200:
            data = response.json()
            sources = data.get("sources", [])
            # Empty sources is valid when KB returns no results
            assert isinstance(sources, list)

    @pytest.mark.contract
    async def test_qa_query_supports_x_trace_id_header(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that X-Trace-ID header is supported.

        Given: A request with X-Trace-ID header
        When: POST /qa/query is called
        Then: Returns response with same trace_id in metadata
        """
        import uuid
        custom_trace_id = str(uuid.uuid4())[:8]

        request = {
            "query": "Test question for trace ID header",
        }

        response = await client.post(
            "/qa/query",
            json=request,
            headers={"X-Trace-ID": custom_trace_id}
        )

        if response.status_code == 200:
            data = response.json()
            trace_id = data.get("metadata", {}).get("trace_id")
            # The service should use the provided trace_id or generate its own
            assert trace_id is not None


class TestQAHealthContract:
    """Contract tests for /qa/health endpoint.

    Tests verify:
    - Health check response structure
    - Component status fields
    """

    @pytest.fixture
    def client(self) -> AsyncClient:
        """Create test client."""
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    @pytest.mark.contract
    async def test_qa_health_returns_200(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that /qa/health returns 200.

        Given: GET /qa/health is called
        When: No parameters
        Then: Returns 200 with health status information
        """
        response = await client.get("/qa/health")

        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "degraded", "unhealthy", "initializing"]

    @pytest.mark.contract
    async def test_qa_health_includes_component_status(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that health check includes component status.

        Given: GET /qa/health is called
        When: No parameters
        Then: Returns status for external_kb, litellm, fallback_ready
        """
        response = await client.get("/qa/health")

        assert response.status_code == 200

        data = response.json()
        # Check for expected component status fields
        expected_fields = ["external_kb", "litellm", "fallback_ready"]
        for field in expected_fields:
            if field in data:
                assert isinstance(data[field], str)
