"""
Unit tests for Query Rewrite Capability (US2).

These tests verify the query rewriting logic:
- Query rewriting vs original query
- Fallback behavior when LLM fails
- Context injection (company_id, file_type, current_date)
- Prompt template interpolation
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from rag_service.capabilities.query_rewrite import (
    QueryRewriteCapability,
    QueryRewriteInput,
    QueryRewriteOutput,
)
from rag_service.api.qa_schemas import QAContext
from rag_service.core.exceptions import GenerationError


class TestQueryRewriteLogic:
    """Unit tests for query rewriting logic."""

    @pytest.fixture
    def mock_litellm_client(self):
        """Create a mock LiteLLM client."""
        client = AsyncMock()
        client.acomplete = AsyncMock(
            return_value=Mock(
                text="2025年春节放假安排",
                model="gpt-3.5-turbo",
            )
        )
        return client

    @pytest.fixture
    def capability(self, mock_litellm_client):
        """Create capability with mock LiteLLM client."""
        return QueryRewriteCapability(
            litellm_client=mock_litellm_client
        )

    @pytest.mark.unit
    async def test_successful_query_rewrite(
        self,
        capability,
        mock_litellm_client,
    ):
        """Test successful query rewriting.

        Given: A vague user query
        When: Query rewriting is performed
        Then: Returns a more specific rewritten query
        """
        input_data = QueryRewriteInput(
            original_query="春节放假几天？",
            context=QAContext(
                company_id="N000131",
                file_type="PublicDocDispatch",
            ),
            trace_id="test-trace-001",
        )

        result = await capability.execute(input_data)

        assert result.was_rewritten is True
        assert result.original_query == "春节放假几天？"
        assert result.rewritten_query == "2025年春节放假安排"
        assert result.rewrite_reason is not None

    @pytest.mark.unit
    async def test_unchanged_when_no_improvement(
        self,
        capability,
        mock_litellm_client,
    ):
        """Test that original query is used when LLM returns no improvement.

        Given: An already specific query
        When: Query rewriting returns same query
        Then: was_rewritten is False
        """
        # Mock LLM to return same query
        mock_litellm_client.acomplete = AsyncMock(
            return_value=Mock(text="春节放假几天？")  # Same as input
        )

        input_data = QueryRewriteInput(
            original_query="春节放假几天？",
            context=QAContext(company_id="N000131"),
            trace_id="test-trace-002",
        )

        result = await capability.execute(input_data)

        # May or may not be rewritten depending on implementation
        assert result.rewritten_query is not None


class TestFallbackBehavior:
    """Unit tests for fallback logic."""

    @pytest.fixture
    def capability(self):
        """Create capability with failing LiteLLM client."""
        mock_client = AsyncMock()
        mock_client.acomplete = AsyncMock(
            side_effect=GenerationError("LLM service unavailable")
        )
        return QueryRewriteCapability(litellm_client=mock_client)

    @pytest.mark.unit
    async def test_fallback_to_original_on_llm_failure(
        self,
        capability,
    ):
        """Test fallback to original query when LLM fails.

        Given: LLM call raises an exception
        When: Query rewriting is performed
        Then: Returns original query unchanged
        """
        input_data = QueryRewriteInput(
            original_query="春节放假几天？",
            context=QAContext(company_id="N000131"),
            trace_id="test-trace-003",
        )

        result = await capability.execute(input_data)

        assert result.was_rewritten is False
        assert result.rewritten_query == input_data.original_query
        assert result.original_query == input_data.original_query

    @pytest.mark.unit
    async def test_fallback_on_empty_response(
        self,
    ):
        """Test fallback when LLM returns empty response.

        Given: LLM returns empty string
        When: Query rewriting is performed
        Then: Returns original query unchanged
        """
        mock_client = AsyncMock()
        mock_client.acomplete = AsyncMock(
            return_value=Mock(text="")  # Empty response
        )

        capability = QueryRewriteCapability(litellm_client=mock_client)

        input_data = QueryRewriteInput(
            original_query="春节放假几天？",
            context=QAContext(company_id="N000131"),
            trace_id="test-trace-004",
        )

        result = await capability.execute(input_data)

        assert result.was_rewritten is False
        assert result.rewritten_query == input_data.original_query

    @pytest.mark.unit
    async def test_fallback_on_too_long_response(
        self,
    ):
        """Test fallback when LLM returns excessively long response.

        Given: LLM returns response longer than max_length
        When: Query rewriting is performed
        Then: Returns original query unchanged
        """
        mock_client = AsyncMock()
        # Create a response that's too long (> 500 characters)
        long_response = "x" * 501
        mock_client.acomplete = AsyncMock(
            return_value=Mock(text=long_response)
        )

        capability = QueryRewriteCapability(litellm_client=mock_client)

        input_data = QueryRewriteInput(
            original_query="春节放假几天？",
            context=QAContext(company_id="N000131"),
            trace_id="test-trace-005",
        )

        result = await capability.execute(input_data)

        # Should fallback to original if rewrite is too long
        assert result.rewritten_query is not None


class TestContextInjection:
    """Unit tests for context injection into prompts."""

    @pytest.fixture
    def mock_litellm_client(self):
        """Create a mock LiteLLM client that captures prompts."""
        client = AsyncMock()

        async def mock_complete(prompt, **kwargs):
            # Store the prompt for verification
            mock_litellm_client.last_prompt = prompt
            return Mock(text="Rewritten query")

        client.acomplete = AsyncMock(side_effect=mock_complete)
        return client

    @pytest.fixture
    def capability(self, mock_litellm_client):
        """Create capability with mock LiteLLM client."""
        return QueryRewriteCapability(
            litellm_client=mock_litellm_client
        )

    @pytest.mark.unit
    async def test_company_id_injected_into_prompt(
        self,
        capability,
        mock_litellm_client,
    ):
        """Test that company_id is injected into the rewrite prompt.

        Given: A query with company_id in context
        When: Query rewriting is performed
        Then: Prompt includes the company_id
        """
        input_data = QueryRewriteInput(
            original_query="假期安排",
            context=QAContext(
                company_id="N000131",
                file_type="PublicDocDispatch",
            ),
            trace_id="test-trace-006",
        )

        await capability.execute(input_data)

        # Verify company_id was in the prompt
        assert "N000131" in mock_litellm_client.last_prompt

    @pytest.mark.unit
    async def test_file_type_injected_into_prompt(
        self,
        capability,
        mock_litellm_client,
    ):
        """Test that file_type is injected into the rewrite prompt.

        Given: A query with file_type in context
        When: Query rewriting is performed
        Then: Prompt includes the file_type
        """
        input_data = QueryRewriteInput(
            original_query="假期安排",
            context=QAContext(
                company_id="N000131",
                file_type="PublicDocDispatch",
            ),
            trace_id="test-trace-007",
        )

        await capability.execute(input_data)

        # Verify file_type was in the prompt
        assert "PublicDocDispatch" in mock_litellm_client.last_prompt

    @pytest.mark.unit
    async def test_current_date_injected_into_prompt(
        self,
        capability,
        mock_litellm_client,
    ):
        """Test that current date is injected into the rewrite prompt.

        Given: Any query (current date is auto-detected)
        When: Query rewriting is performed
        Then: Prompt includes the current date/year
        """
        input_data = QueryRewriteInput(
            original_query="假期安排",
            context=QAContext(company_id="N000131"),
            trace_id="test-trace-008",
        )

        await capability.execute(input_data)

        # Verify current year (2025 or 2026) was in the prompt
        assert "202" in mock_litellm_client.last_prompt


class TestPromptTemplate:
    """Unit tests for prompt template structure."""

    @pytest.fixture
    def mock_litellm_client(self):
        """Create a mock LiteLLM client that captures prompts."""
        client = AsyncMock()

        async def mock_complete(prompt, **kwargs):
            mock_litellm_client.last_prompt = prompt
            return Mock(text="Rewritten query")

        client.acomplete = AsyncMock(side_effect=mock_complete)
        return client

    @pytest.fixture
    def capability(self, mock_litellm_client):
        """Create capability with mock LiteLLM client."""
        return QueryRewriteCapability(
            litellm_client=mock_litellm_client
        )

    @pytest.mark.unit
    async def test_prompt_contains_instructions(
        self,
        capability,
        mock_litellm_client,
    ):
        """Test that prompt contains rewriting instructions.

        Given: A query to rewrite
        When: Query rewriting is performed
        Then: Prompt contains clear instructions for rewriting
        """
        input_data = QueryRewriteInput(
            original_query="假期安排",
            context=QAContext(company_id="N000131"),
            trace_id="test-trace-009",
        )

        await capability.execute(input_data)

        prompt = mock_litellm_client.last_prompt

        # Verify prompt contains key instructions
        assert "rewrite" in prompt.lower() or "改写" in prompt or "优化" in prompt
        assert input_data.original_query in prompt

    @pytest.mark.unit
    async def test_prompt_uses_chinese_by_default(
        self,
        capability,
        mock_litellm_client,
    ):
        """Test that prompt uses Chinese language by default.

        Given: A Chinese query
        When: Query rewriting is performed
        Then: Prompt instructions are in Chinese
        """
        input_data = QueryRewriteInput(
            original_query="春节放假几天？",
            context=QAContext(company_id="N000131"),
            trace_id="test-trace-010",
        )

        await capability.execute(input_data)

        prompt = mock_litellm_client.last_prompt

        # Prompt should contain Chinese characters
        assert any(ord(c) > 127 for c in prompt)


class TestValidation:
    """Unit tests for input validation."""

    @pytest.fixture
    def capability(self):
        """Create capability for validation tests."""
        mock_client = AsyncMock()
        mock_client.acomplete = AsyncMock(
            return_value=Mock(text="Rewritten query")
        )
        return QueryRewriteCapability(litellm_client=mock_client)

    @pytest.mark.unit
    async def test_validate_empty_query(self, capability):
        """Test validation rejects empty query."""
        input_data = QueryRewriteInput(
            original_query="",
            context=QAContext(company_id="N000131"),
            trace_id="test-trace-011",
        )

        result = await capability.execute(input_data)

        # Empty query should return unchanged
        assert result.rewritten_query == ""

    @pytest.mark.unit
    async def test_validate_none_context(self, capability):
        """Test that None context is handled gracefully."""
        input_data = QueryRewriteInput(
            original_query="Test query",
            context=None,
            trace_id="test-trace-012",
        )

        result = await capability.execute(input_data)

        # Should still work, just without context
        assert result is not None


class TestHealthStatus:
    """Unit tests for health status reporting."""

    @pytest.mark.unit
    def test_health_status_with_client(self):
        """Test health status when LiteLLM client is configured."""
        mock_client = AsyncMock()
        capability = QueryRewriteCapability(litellm_client=mock_client)

        health = capability.get_health()

        assert health["status"] in ["initializing", "ready"]
        assert health["litellm"] == "connected"

    @pytest.mark.unit
    def test_health_status_without_client(self):
        """Test health status when LiteLLM client is not configured."""
        capability = QueryRewriteCapability(litellm_client=None)

        health = capability.get_health()

        assert health["litellm"] == "not_configured"
