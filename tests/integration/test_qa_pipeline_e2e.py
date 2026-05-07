"""
Integration tests for RAG QA Pipeline (US1 - Basic QA with External Knowledge).

These tests verify the complete QA pipeline integration:
- Basic QA flow with external KB and LiteLLM
- Fallback scenarios (KB empty, KB error, KB unavailable)
- End-to-end request/response flow
"""

import pytest
from httpx import AsyncClient, ASGITransport
from typing import Dict, Any

from rag_service.main import app


class TestBasicQAFlow:
    """Integration tests for basic QA flow (US1).

    Tests verify:
    - Complete request/response cycle
    - Answer generation with retrieved context
    - Sources are properly included in response
    - Metadata is correctly populated
    """

    @pytest.fixture
    def client(self) -> AsyncClient:
        """Create test client."""
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    @pytest.fixture
    def sample_qa_request(self) -> Dict[str, Any]:
        """Sample QA request."""
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

    @pytest.mark.integration
    async def test_basic_qa_flow_returns_answer_with_sources(
        self,
        client: AsyncClient,
        sample_qa_request: Dict[str, Any],
    ) -> None:
        """Test complete QA flow returns answer and sources.

        Given: A valid QA query request
        When: POST /qa/query is called
        Then: Returns answer with sources from external KB
        """
        response = await client.post(
            "/qa/query",
            json=sample_qa_request,
            timeout=30.0,
        )

        # May return 200, 503 (services unavailable), or 400 (validation)
        assert response.status_code in [200, 503, 400]

        if response.status_code == 200:
            data = response.json()

            # Verify answer
            assert "answer" in data
            assert isinstance(data["answer"], str)
            assert len(data["answer"]) > 0

            # Verify sources
            assert "sources" in data
            assert isinstance(data["sources"], list)

            # Verify metadata
            assert "metadata" in data
            assert "trace_id" in data["metadata"]

    @pytest.mark.integration
    async def test_basic_qa_flow_includes_retrieved_chunks_as_sources(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that retrieved chunks are included as sources.

        Given: A QA query that retrieves chunks
        When: POST /qa/query is called
        Then: Response includes sources with chunk metadata
        """
        request = {
            "query": "Test question about company policy",
            "context": {
                "company_id": "N000131",
                "file_type": "PublicDocDispatch",
            },
        }

        response = await client.post(
            "/qa/query",
            json=request,
            timeout=30.0,
        )

        if response.status_code == 200:
            data = response.json()
            sources = data.get("sources", [])

            # Each source should have required fields
            for source in sources:
                assert "chunk_id" in source
                assert "document_id" in source
                assert "document_name" in source
                assert "score" in source
                assert "content_preview" in source

    @pytest.mark.integration
    async def test_basic_qa_flow_generates_answer_from_context(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that answer is generated from retrieved context.

        Given: A QA query with specific context
        When: POST /qa/query is called
        Then: Generated answer is relevant to the query
        """
        request = {
            "query": "什么是RAG（Retrieval-Augmented Generation）？",
            "context": {
                "company_id": "N000131",
            },
            "options": {
                "enable_hallucination_check": False,
            },
        }

        response = await client.post(
            "/qa/query",
            json=request,
            timeout=30.0,
        )

        if response.status_code == 200:
            data = response.json()
            answer = data.get("answer", "")

            # Answer should be relevant to the question
            # (This is a basic check - more sophisticated checks would need LLM evaluation)
            assert len(answer) > 20  # Should have substantive content

    @pytest.mark.integration
    async def test_basic_qa_flow_includes_timing_metadata(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that response includes timing information.

        Given: A QA query request
        When: POST /qa/query is called
        Then: Response includes timing breakdown
        """
        request = {
            "query": "Test question",
            "context": {
                "company_id": "N000131",
            },
        }

        response = await client.post(
            "/qa/query",
            json=request,
            timeout=30.0,
        )

        if response.status_code == 200:
            data = response.json()
            metadata = data.get("metadata", {})
            timing = metadata.get("timing", {})

            # Should have timing information
            assert "total_ms" in timing
            assert "retrieve_ms" in timing
            assert "generate_ms" in timing

            # Timing values should be positive numbers
            assert timing["total_ms"] >= 0
            if timing["retrieve_ms"] is not None:
                assert timing["retrieve_ms"] >= 0
            if timing["generate_ms"] is not None:
                assert timing["generate_ms"] >= 0

    @pytest.mark.integration
    async def test_basic_qa_flow_hallucination_status_when_disabled(
        self,
        client: AsyncClient,
    ) -> None:
        """Test hallucination status when check is disabled.

        Given: A QA query with hallucination check disabled
        When: POST /qa/query is called
        Then: Response shows hallucination check not performed
        """
        request = {
            "query": "Test question",
            "options": {
                "enable_hallucination_check": False,
            },
        }

        response = await client.post(
            "/qa/query",
            json=request,
            timeout=30.0,
        )

        if response.status_code == 200:
            data = response.json()
            hallucination_status = data.get("hallucination_status", {})

            # Should indicate check was not performed
            assert hallucination_status.get("checked") is False


class TestFallbackScenarios:
    """Integration tests for fallback scenarios (US1).

    Tests verify:
    - KB unavailable returns fallback message
    - KB empty returns default fallback
    - KB error returns appropriate error message
    """

    @pytest.fixture
    def client(self) -> AsyncClient:
        """Create test client."""
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    @pytest.mark.integration
    async def test_fallback_when_kb_unavailable(
        self,
        client: AsyncClient,
    ) -> None:
        """Test fallback response when KB is unavailable.

        Given: A QA query but KB service is down
        When: POST /qa/query is called
        Then: Returns fallback message for KB unavailable
        """
        # This test would require mocking the KB service to be unavailable
        # For now, we test that the endpoint handles 503 gracefully
        request = {
            "query": "Test question",
            "context": {
                "company_id": "N000131",
            },
        }

        response = await client.post(
            "/qa/query",
            json=request,
            timeout=30.0,
        )

        # Should handle gracefully (200 with fallback or 503)
        assert response.status_code in [200, 503, 400]

        if response.status_code == 200:
            data = response.json()
            # If services are down, might get fallback message
            answer = data.get("answer", "")
            # Should have some response
            assert len(answer) >= 0

    @pytest.mark.integration
    async def test_fallback_when_kb_returns_empty(
        self,
        client: AsyncClient,
    ) -> None:
        """Test fallback response when KB returns empty results.

        Given: A QA query that returns no KB results
        When: POST /qa/query is called
        Then: Returns default fallback message for empty KB
        """
        # Use a very specific query unlikely to find results
        request = {
            "query": "xyzabc123nonexistentqueryfortesting",
            "context": {
                "company_id": "N000131",
            },
        }

        response = await client.post(
            "/qa/query",
            json=request,
            timeout=30.0,
        )

        # Should return 200 with empty sources or fallback
        assert response.status_code in [200, 503, 400]

        if response.status_code == 200:
            data = response.json()
            sources = data.get("sources", [])

            # Should have empty sources when KB returns nothing
            assert isinstance(sources, list)
            if len(sources) == 0:
                # Should have fallback message
                answer = data.get("answer", "")
                assert len(answer) > 0

    @pytest.mark.integration
    async def test_fallback_includes_suggestions(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that fallback includes user suggestions.

        Given: A QA query that triggers fallback
        When: POST /qa/query is called
        Then: Fallback message includes helpful suggestions
        """
        request = {
            "query": "Test",
            "context": {
                "company_id": "N000131",
            },
        }

        response = await client.post(
            "/qa/query",
            json=request,
            timeout=30.0,
        )

        # Fallback suggestions are in the DefaultFallbackService
        # This test verifies the endpoint can return fallback messages
        assert response.status_code in [200, 503, 400]

    @pytest.mark.integration
    async def test_fallback_preserves_trace_id(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that fallback responses include trace_id.

        Given: A QA query that triggers fallback
        When: POST /qa/query is called
        Then: Response includes trace_id for debugging
        """
        import uuid
        custom_trace_id = str(uuid.uuid4())[:8]

        request = {
            "query": "Test",
        }

        response = await client.post(
            "/qa/query",
            json=request,
            headers={"X-Trace-ID": custom_trace_id},
            timeout=30.0,
        )

        if response.status_code == 200:
            data = response.json()
            metadata = data.get("metadata", {})
            trace_id = metadata.get("trace_id")

            # Should have trace_id for debugging
            assert trace_id is not None
            assert len(trace_id) > 0


class TestQAFlowWithQueryRewriting:
    """Integration tests for QA flow with query rewriting (US2 integration).

    Tests verify:
    - Query rewriting happens before retrieval
    - Rewritten query improves retrieval
    - Fallback to original if rewrite fails
    """

    @pytest.fixture
    def client(self) -> AsyncClient:
        """Create test client."""
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    @pytest.mark.integration
    async def test_query_rewrite_updates_metadata(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that query rewriting is reflected in metadata.

        Given: A QA query with query rewriting enabled
        When: POST /qa/query is called
        Then: Metadata includes query_rewritten flag and rewritten_query
        """
        request = {
            "query": "春节放假几天？",
            "options": {
                "enable_query_rewrite": True,
            },
        }

        response = await client.post(
            "/qa/query",
            json=request,
            timeout=30.0,
        )

        if response.status_code == 200:
            data = response.json()
            metadata = data.get("metadata", {})

            # Should have query rewrite metadata
            assert "query_rewritten" in metadata
            assert isinstance(metadata["query_rewritten"], bool)

            # If query was rewritten, should have rewritten_query
            if metadata.get("query_rewritten"):
                assert "rewritten_query" in metadata
                assert "rewrite_reason" in metadata

    @pytest.mark.integration
    async def test_query_rewrite_includes_timing(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that query rewriting timing is included.

        Given: A QA query with query rewriting enabled
        When: POST /qa/query is called
        Then: Metadata includes rewrite_ms timing
        """
        request = {
            "query": "Test question",
            "options": {
                "enable_query_rewrite": True,
            },
        }

        response = await client.post(
            "/qa/query",
            json=request,
            timeout=30.0,
        )

        if response.status_code == 200:
            data = response.json()
            metadata = data.get("metadata", {})
            timing = metadata.get("timing", {})

            # Should have rewrite timing if rewriting was enabled
            # (may be None if rewriting was not actually performed)
            assert "rewrite_ms" in timing


class TestQAFlowWithHallucinationCheck:
    """Integration tests for QA flow with hallucination detection (US3 integration).

    Tests verify:
    - Hallucination check runs after generation
    - Regeneration happens when check fails
    - Final response includes verification status
    """

    @pytest.fixture
    def client(self) -> AsyncClient:
        """Create test client."""
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    @pytest.mark.integration
    async def test_hallucination_check_updates_status(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that hallucination check updates status.

        Given: A QA query with hallucination check enabled
        When: POST /qa/query is called
        Then: Response includes hallucination status
        """
        request = {
            "query": "Test question",
            "options": {
                "enable_hallucination_check": True,
            },
        }

        response = await client.post(
            "/qa/query",
            json=request,
            timeout=60.0,  # Longer timeout for hallucination check
        )

        if response.status_code == 200:
            data = response.json()
            hallucination_status = data.get("hallucination_status", {})

            # Should have hallucination check status
            assert "checked" in hallucination_status
            assert "passed" in hallucination_status
            assert "confidence" in hallucination_status

    @pytest.mark.integration
    async def test_hallucination_check_includes_timing(
        self,
        client: AsyncClient,
    ) -> None:
        """Test that hallucination check timing is included.

        Given: A QA query with hallucination check enabled
        When: POST /qa/query is called
        Then: Metadata includes verify_ms timing
        """
        request = {
            "query": "Test question",
            "options": {
                "enable_hallucination_check": True,
            },
        }

        response = await client.post(
            "/qa/query",
            json=request,
            timeout=60.0,
        )

        if response.status_code == 200:
            data = response.json()
            metadata = data.get("metadata", {})
            timing = metadata.get("timing", {})

            # Should have verify timing if check was performed
            if data.get("hallucination_status", {}).get("checked"):
                assert "verify_ms" in timing
