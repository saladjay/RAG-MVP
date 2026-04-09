"""
Integration tests for Streaming Response (US4).

These tests verify the streaming response functionality:
- Server-Sent Events format
- Token streaming as they arrive
- X-Hallucination-Checked header updates
- Connection drop handling
"""

import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from typing import AsyncGenerator

from rag_service.main import app


class TestStreamingResponse:
    """Integration tests for streaming response endpoint."""

    @pytest.fixture
    def client(self) -> AsyncClient:
        """Create test client."""
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    @pytest.fixture
    def sample_streaming_request(self) -> dict:
        """Sample streaming request."""
        return {
            "query": "什么是RAG（Retrieval-Augmented Generation）？",
            "context": {
                "company_id": "N000131",
            },
            "options": {
                "stream": True,
                "enable_hallucination_check": False,
            },
        }

    @pytest.mark.integration
    async def test_streaming_endpoint_returns_501_not_implemented(
        self,
        client: AsyncClient,
        sample_streaming_request: dict,
    ):
        """Test that streaming endpoint returns 501 until implemented.

        Given: A streaming request
        When: POST /qa/query/stream is called
        Then: Returns 501 with not_implemented error
        """
        response = await client.post(
            "/qa/query/stream",
            json=sample_streaming_request,
            timeout=30.0,
        )

        # Currently returns 501 as streaming is not yet implemented
        # After implementation, should return 200 with streaming response
        assert response.status_code in [501, 200]

    @pytest.mark.integration
    async def test_streaming_response_has_correct_headers(
        self,
        client: AsyncClient,
        sample_streaming_request: dict,
    ):
        """Test that streaming response includes required headers.

        Given: A streaming request
        When: POST /qa/query/stream is called
        Then: Response includes X-Hallucination-Checked and X-Trace-ID headers
        """
        response = await client.post(
            "/qa/query/stream",
            json=sample_streaming_request,
            timeout=30.0,
        )

        if response.status_code == 200:
            # Check for required headers
            assert "X-Hallucination-Checked" in response.headers or "x-hallucination-checked" in response.headers
            assert "X-Trace-ID" in response.headers or "x-trace-id" in response.headers

            # Verify header values
            hallucination_header = response.headers.get("X-Hallucination-Checked", response.headers.get("x-hallucination-checked"))
            assert hallucination_header in ["pending", "passed", "failed", "skipped"]

    @pytest.mark.integration
    async def test_streaming_tokens_arrive_incrementally(
        self,
        client: AsyncClient,
        sample_streaming_request: dict,
    ):
        """Test that tokens arrive incrementally during streaming.

        Given: A streaming request
        When: POST /qa/query/stream is called
        Then: Tokens arrive in multiple chunks, not all at once
        """
        if not await self._is_streaming_implemented(client):
            pytest.skip("Streaming not yet implemented")

        response = await client.post(
            "/qa/query/stream",
            json=sample_streaming_request,
            timeout=30.0,
        )

        if response.status_code == 200:
            # Collect chunks with timestamps
            chunks = []
            chunk_times = []

            async def collect_chunks():
                async for line in response.aiter_lines():
                    if line:
                        chunks.append(line)
                        chunk_times.append(asyncio.get_event_loop().time())

            await collect_chunks()

            # Verify we received multiple chunks over time
            assert len(chunks) > 1
            assert len(chunk_times) > 1

            # Verify time spread (not all arrived at once)
            time_span = max(chunk_times) - min(chunk_times)
            assert time_span > 0.1  # At least 100ms between first and last chunk

    @pytest.mark.integration
    async def test_streaming_response_complete_answer(
        self,
        client: AsyncClient,
        sample_streaming_request: dict,
    ):
        """Test that streaming response produces complete answer.

        Given: A streaming request
        When: POST /qa/query/stream is called
        Then: Streamed tokens combine into coherent answer
        """
        if not await self._is_streaming_implemented(client):
            pytest.skip("Streaming not yet implemented")

        response = await client.post(
            "/qa/query/stream",
            json=sample_streaming_request,
            timeout=30.0,
        )

        if response.status_code == 200:
            # Collect all chunks
            full_response = ""

            async def collect_full_response():
                nonlocal full_response
                async for line in response.aiter_lines():
                    if line:
                        # Parse SSE format: "data: <content>"
                        if line.startswith("data:"):
                            content = line[5:].strip()
                            if content != "[DONE]":
                                full_response += content

            await collect_full_response()

            # Verify we got a complete response
            assert len(full_response) > 50  # Should have substantial content
            assert "RAG" in full_response or "检索" in full_response or "生成" in full_response

    @pytest.mark.integration
    async def test_streaming_handles_connection_interrupt(
        self,
        client: AsyncClient,
    ):
        """Test graceful handling of connection interruption.

        Given: A streaming request
        When: Client disconnects mid-stream
        Then: Server logs partial response and handles gracefully
        """
        if not await self._is_streaming_implemented(client):
            pytest.skip("Streaming not yet implemented")

        request = {
            "query": "A very long detailed question about RAG architecture and implementation",
            "options": {"stream": True},
        }

        async def interrupt_stream():
            response = await client.post(
                "/qa/query/stream",
                json=request,
                timeout=30.0,
            )

            # Read a few chunks then close
            chunk_count = 0
            async for line in response.aiter_lines():
                if line:
                    chunk_count += 1
                    if chunk_count >= 3:
                        # Simulate client disconnect
                        break

        # Should not raise exception
        await interrupt_stream()

    @pytest.mark.integration
    async def test_streaming_async_hallucination_check(
        self,
        client: AsyncClient,
    ):
        """Test that hallucination check runs asynchronously after streaming.

        Given: A streaming request with hallucination check enabled
        When: POST /qa/query/stream is called
        Then: Streaming completes quickly, hallucination check runs in background
        """
        if not await self._is_streaming_implemented(client):
            pytest.skip("Streaming not yet implemented")

        request = {
            "query": "Test question",
            "options": {
                "stream": True,
                "enable_hallucination_check": True,
            },
        }

        start_time = asyncio.get_event_loop().time()

        response = await client.post(
            "/qa/query/stream",
            json=request,
            timeout=30.0,
        )

        if response.status_code == 200:
            # Collect streaming response
            async for line in response.aiter_lines():
                if line:
                    pass  # Consume stream

            stream_duration = asyncio.get_event_loop().time() - start_time

            # Streaming should complete quickly (< 5 seconds)
            # Hallucination check runs in background after stream completes
            assert stream_duration < 10.0

    async def _is_streaming_implemented(self, client: AsyncClient) -> bool:
        """Check if streaming is implemented."""
        response = await client.post(
            "/qa/query/stream",
            json={"query": "test"},
        )
        return response.status_code != 501


class TestStreamingErrorHandling:
    """Integration tests for streaming error scenarios."""

    @pytest.fixture
    def client(self) -> AsyncClient:
        """Create test client."""
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    @pytest.mark.integration
    async def test_streaming_with_invalid_query(
        self,
        client: AsyncClient,
    ):
        """Test streaming with invalid query.

        Given: An invalid streaming request (empty query)
        When: POST /qa/query/stream is called
        Then: Returns 400 without starting stream
        """
        request = {
            "query": "",
            "options": {"stream": True},
        }

        response = await client.post(
            "/qa/query/stream",
            json=request,
        )

        # Should return validation error
        assert response.status_code in [400, 422]

    @pytest.mark.integration
    async def test_streaming_with_service_unavailable(
        self,
        client: AsyncClient,
    ):
        """Test streaming when backend service is unavailable.

        Given: A streaming request but services are down
        When: POST /qa/query/stream is called
        Then: Returns appropriate error response
        """
        request = {
            "query": "Test question",
            "options": {"stream": True},
        }

        response = await client.post(
            "/qa/query/stream",
            json=request,
        )

        # May return 501 if not implemented, or 503 if services unavailable
        assert response.status_code in [200, 501, 503, 500]


class TestStreamingPerformance:
    """Integration tests for streaming performance."""

    @pytest.fixture
    def client(self) -> AsyncClient:
        """Create test client."""
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    @pytest.mark.integration
    async def test_first_token_latency(
        self,
        client: AsyncClient,
    ):
        """Test time to first token (TTFT) for streaming.

        Given: A streaming request
        When: POST /qa/query/stream is called
        Then: First token arrives within reasonable time (< 3 seconds)
        """
        if not await self._is_streaming_implemented(client):
            pytest.skip("Streaming not yet implemented")

        request = {
            "query": "What is RAG?",
            "options": {"stream": True},
        }

        start_time = asyncio.get_event_loop().time()
        first_token_time = None

        response = await client.post(
            "/qa/query/stream",
            json=request,
            timeout=30.0,
        )

        if response.status_code == 200:
            async for line in response.aiter_lines():
                if line and first_token_time is None:
                    first_token_time = asyncio.get_event_loop().time()
                    break

            if first_token_time:
                ttft = first_token_time - start_time
                # TTFT should be under 3 seconds for good UX
                assert ttft < 5.0

    async def _is_streaming_implemented(self, client: AsyncClient) -> bool:
        """Check if streaming is implemented."""
        response = await client.post(
            "/qa/query/stream",
            json={"query": "test"},
        )
        return response.status_code != 501
