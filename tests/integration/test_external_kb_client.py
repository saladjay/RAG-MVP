"""
Integration tests for External Knowledge Base Client.

These tests verify the integration with the external HTTP knowledge base service.
Run with EXTERNAL_KB_BASE_URL configured or skip these tests.
"""

import pytest
from httpx import HTTPStatusError, RequestError

from rag_service.clients.external_kb_client import (
    ExternalKBClient,
    ExternalKBClientConfig,
)
from rag_service.core.exceptions import RetrievalError


@pytest.mark.integration
class TestExternalKBClient:
    """Test external KB client functionality."""

    @pytest.fixture
    def client_config(self):
        """Get client config from environment or use test defaults."""
        import os

        base_url = os.getenv("EXTERNAL_KB_BASE_URL", "http://128.23.77.226:9981")
        return ExternalKBClientConfig(
            base_url=base_url,
            timeout=30,
            max_retries=2,
        )

    @pytest.fixture
    async def client(self, client_config):
        """Create and return a client instance."""
        client = ExternalKBClient(client_config)
        yield client
        await client.close()

    @pytest.mark.asyncio
    async def test_query_basic(self, client):
        """Test basic query functionality."""
        chunks = await client.query(
            query="东方思维",
            comp_id="N000131",
            file_type="PublicDocDispatch",
            topk=2,
            search_type=1,  # fulltext search
        )

        assert isinstance(chunks, list)
        # Note: May return empty if external KB is not accessible
        # In production, this would have actual results

    @pytest.mark.asyncio
    async def test_query_with_filters(self, client):
        """Test query with additional filters."""
        chunks = await client.query(
            query="合同",
            comp_id="N000131",
            file_type="PublicDocDispatch",
            doc_date="2024-01-12",
            topk=5,
            score_min=0.5,
            search_type=2,  # hybrid search
        )

        assert isinstance(chunks, list)

    @pytest.mark.asyncio
    async def test_health_check(self, client):
        """Test health check functionality."""
        # Health check may fail if service is not accessible
        try:
            is_healthy = await client.health_check()
            assert isinstance(is_healthy, bool)
        except Exception:
            # Service may not be available in test environment
            pytest.skip("External KB service not accessible")

    @pytest.mark.asyncio
    async def test_invalid_params(self, client):
        """Test query with invalid parameters."""
        with pytest.raises(RetrievalError):
            await client.query(
                query="",  # Empty query should fail
                comp_id="N000131",
                file_type="InvalidType",
                search_type=1,
            )

    @pytest.mark.asyncio
    async def test_chunk_structure(self, client):
        """Test that returned chunks have correct structure."""
        chunks = await client.query(
            query="测试",
            comp_id="N000131",
            file_type="PublicDocDispatch",
            topk=1,
            search_type=1,
        )

        if chunks:
            chunk = chunks[0]
            assert "id" in chunk
            assert "content" in chunk
            assert "metadata" in chunk
            assert "score" in chunk
            assert "source_doc" in chunk


@pytest.mark.integration
class TestExternalKBQueryCapability:
    """Test external KB query capability."""

    @pytest.mark.asyncio
    async def test_capability_execution(self):
        """Test capability can execute queries."""
        from rag_service.capabilities.external_kb_query import (
            ExternalKBQueryCapability,
            ExternalKBQueryInput,
        )

        capability = ExternalKBQueryCapability()

        input_data = ExternalKBQueryInput(
            query="东方思维",
            comp_id="N000131",
            file_type="PublicDocDispatch",
            topk=5,
            search_type=1,
        )

        try:
            result = await capability.execute(input_data)
            assert hasattr(result, "chunks")
            assert hasattr(result, "total_found")
            assert hasattr(result, "trace_id")
        except RetrievalError:
            # Service may not be available in test environment
            pytest.skip("External KB service not accessible")

    @pytest.mark.asyncio
    async def test_input_validation(self):
        """Test input validation."""
        from rag_service.capabilities.external_kb_query import (
            ExternalKBQueryCapability,
            ExternalKBQueryInput,
        )

        capability = ExternalKBQueryCapability()

        # Test invalid file_type
        with pytest.raises(ValueError):
            ExternalKBQueryInput(
                query="test",
                comp_id="N000131",
                file_type="InvalidType",
                search_type=1,
            )

        # Test invalid search_type
        with pytest.raises(ValueError):
            ExternalKBQueryInput(
                query="test",
                comp_id="N000131",
                file_type="PublicDocDispatch",
                search_type=5,
            )
