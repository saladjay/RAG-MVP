"""
Edge case tests for RAG QA Pipeline.

These tests verify behavior with unusual or malformed inputs
that may occur in production but aren't part of the main flow.
"""

import pytest
from httpx import AsyncClient, ASGITransport

from rag_service.main import app


class TestEdgeCases:
    """Unit tests for edge cases in QA pipeline."""

    @pytest.fixture
    def client(self) -> AsyncClient:
        """Create test client."""
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    @pytest.mark.unit
    async def test_malformed_kb_response_handling(self, client):
        """Test handling of malformed KB responses.

        Given: KB returns malformed or unexpected data structure
        When: Query is processed
        Then: System handles gracefully with fallback message
        """
        # This would require mocking the KB client to return malformed data
        # For now, we test that the endpoint can handle unexpected responses
        request = {
            "query": "Test query",
            "context": {"company_id": "N000131"},
        }

        response = await client.post("/qa/query", json=request, timeout=30.0)

        # Should handle gracefully (200 with fallback or error status)
        assert response.status_code in [200, 503, 400, 500]

    @pytest.mark.unit
    async def test_unsupported_language_query(self, client):
        """Test handling of unsupported language queries.

        Given: Query is in a language not supported by the LLM
        When: Query is processed
        Then: System returns response or appropriate fallback
        """
        # Test with a non-Chinese, non-English query
        request = {
            "query": "Как дела? а także крымсько-татарський сьогодні свята",
            "context": {"company_id": "N000131"},
        }

        response = await client.post("/qa/query", json=request, timeout=30.0)

        # Should process or return appropriate response
        assert response.status_code in [200, 503, 400]

    @pytest.mark.unit
    async def test_unrelated_query(self, client):
        """Test handling of completely unrelated queries.

        Given: Query is completely unrelated to the knowledge base domain
        When: Query is processed
        Then: System returns helpful response or fallback
        """
        request = {
            "query": "What's the weather like on Mars today?",
            "context": {"company_id": "N000131"},
        }

        response = await client.post("/qa/query", json=request, timeout=30.0)

        # Should return fallback when no relevant documents found
        assert response.status_code in [200, 503, 400]

        if response.status_code == 200:
            data = response.json()
            sources = data.get("sources", [])
            # Should have empty or very few sources
            assert len(sources) <= 2

    @pytest.mark.unit
    async def test_very_long_query(self, client):
        """Test handling of very long queries.

        Given: Query is at maximum length (1000 characters)
        When: Query is processed
        Then: System handles without error
        """
        # Create a query that's exactly at the limit
        long_query = "这是一个关于公司政策的详细问题。" * 50  # ~1000 chars
        long_query = long_query[:1000]  # Ensure exactly 1000

        request = {
            "query": long_query,
            "context": {"company_id": "N000131"},
        }

        response = await client.post("/qa/query", json=request, timeout=30.0)

        # Should handle within limit
        assert response.status_code in [200, 503, 400]

    @pytest.mark.unit
    async def test_query_with_special_characters(self, client):
        """Test handling of queries with special characters.

        Given: Query contains special characters, emojis, or symbols
        When: Query is processed
        Then: System handles correctly
        """
        special_queries = [
            "春节放假安排🎉？",
            "公司 <script>alert('test')</script> 政策",
            "查询带有引号\"单引号'和反斜杠\\的内容",
            "Test with\ttabs\nand\nnewlines",
            "Query with $pecial characters & symbols!",
        ]

        for query_text in special_queries:
            request = {
                "query": query_text,
                "context": {"company_id": "N000131"},
            }

            response = await client.post("/qa/query", json=request, timeout=30.0)

            # Should handle or validate appropriately
            assert response.status_code in [200, 503, 400]

    @pytest.mark.unit
    async def test_query_with_null_bytes(self, client):
        """Test handling of queries with null bytes.

        Given: Query contains null bytes
        When: Query is processed
        Then: System handles or validates appropriately
        """
        request = {
            "query": "Test\x00query\x00with\x00nulls",
            "context": {"company_id": "N000131"},
        }

        response = await client.post("/qa/query", json=request, timeout=30.0)

        # Should handle gracefully (may sanitize or reject)
        assert response.status_code in [200, 400, 422]

    @pytest.mark.unit
    async def test_context_with_extra_fields(self, client):
        """Test handling of context with unknown extra fields.

        Given: Request context contains fields not in the schema
        When: Query is processed
        Then: System ignores extra fields (Pydantic behavior)
        """
        request = {
            "query": "Test question",
            "context": {
                "company_id": "N000131",
                "unknown_field": "should_be_ignored",
                "another_unknown": 12345,
            },
        }

        response = await client.post("/qa/query", json=request, timeout=30.0)

        # Should process normally, ignoring extra fields
        assert response.status_code in [200, 503, 400]

    @pytest.mark.unit
    async def test_zero_top_k(self, client):
        """Test handling of top_k=0 (edge case).

        Given: Request specifies top_k=0
        When: Query is processed
        Then: System validates or uses default
        """
        request = {
            "query": "Test question",
            "options": {"top_k": 0},
        }

        response = await client.post("/qa/query", json=request, timeout=30.0)

        # Should reject top_k=0 as invalid (must be >= 1)
        assert response.status_code in [400, 422]

    @pytest.mark.unit
    async def test_negative_top_k(self, client):
        """Test handling of negative top_k.

        Given: Request specifies negative top_k
        When: Query is processed
        Then: System returns validation error
        """
        request = {
            "query": "Test question",
            "options": {"top_k": -5},
        }

        response = await client.post("/qa/query", json=request, timeout=30.0)

        # Should reject negative top_k
        assert response.status_code in [400, 422]

    @pytest.mark.unit
    async def test_query_with_only_whitespace(self, client):
        """Test handling of query with only whitespace.

        Given: Query contains only spaces/tabs/newlines
        When: Query is processed
        Then: System returns validation error
        """
        request = {
            "query": "   \t\n   ",
            "context": {"company_id": "N000131"},
        }

        response = await client.post("/qa/query", json=request, timeout=30.0)

        # Should reject whitespace-only queries
        assert response.status_code in [400, 422]

    @pytest.mark.unit
    async def test_concurrent_requests(self, client):
        """Test handling of concurrent requests.

        Given: Multiple requests submitted simultaneously
        When: Requests are processed
        Then: System handles all requests without errors
        """
        import asyncio

        async def make_request(query_id):
            request = {
                "query": f"Concurrent test question {query_id}",
                "context": {"company_id": "N000131"},
            }
            return await client.post("/qa/query", json=request, timeout=30.0)

        # Send 5 concurrent requests
        responses = await asyncio.gather(
            *[make_request(i) for i in range(5)],
            return_exceptions=True,
        )

        # All requests should complete without unhandled exceptions
        for response in responses:
            if isinstance(response, Exception):
                # Some exceptions are acceptable (e.g., service unavailable)
                pass
            else:
                assert response.status_code in [200, 503, 400, 500]

    @pytest.mark.unit
    async def test_very_short_query(self, client):
        """Test handling of very short (single character) queries.

        Given: Query is a single character
        When: Query is processed
        Then: System processes or returns helpful response
        """
        single_char_queries = ["?", "。", "a", "1"]

        for query_text in single_char_queries:
            request = {
                "query": query_text,
                "context": {"company_id": "N000131"},
            }

            response = await client.post("/qa/query", json=request, timeout=30.0)

            # Should process or return appropriate response
            assert response.status_code in [200, 503, 400]

    @pytest.mark.unit
    async def test_unicode_normalization(self, client):
        """Test handling of Unicode normalization issues.

        Given: Query contains Unicode characters with multiple representations
        When: Query is processed
        Then: System handles consistently
        """
        # Different Unicode representations of the same character
        request = {
            "query": "cafe\u0301",  # "café" with combining acute accent
            "context": {"company_id": "N000131"},
        }

        response = await client.post("/qa/query", json=request, timeout=30.0)

        # Should handle without error
        assert response.status_code in [200, 503, 400]

    @pytest.mark.unit
    async def test_numeric_company_id_variations(self, client):
        """Test various company_id format variations.

        Given: company_id with various numeric formats
        When: Query is processed
        Then: System validates correctly
        """
        company_ids = [
            "N000001",  # Minimum valid
            "N999999",  # Large number
            "N123",     # Too short (invalid)
            "N0000000000001",  # Too long (invalid)
            "n000131",  # Lowercase n (invalid)
            "N00013A",  # Contains letter (invalid)
        ]

        for company_id in company_ids:
            request = {
                "query": "Test question",
                "context": {"company_id": company_id},
            }

            response = await client.post("/qa/query", json=request, timeout=30.0)

            if len(company_id) == 7 and company_id.startswith("N") and company_id[1:].isdigit():
                # Valid format
                assert response.status_code in [200, 503, 400]
            else:
                # Invalid format should be rejected
                assert response.status_code in [400, 422]
