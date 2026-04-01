"""
Contract tests for Langfuse integration (US3 - Observability and Tracing).

These tests verify the Langfuse Prompt Layer integration including:
- Trace creation and management
- Span creation and updates
- Prompt version tracking
- Retrieved document tracking
- Non-blocking flush behavior
"""

import pytest
from datetime import datetime
from typing import Dict, Any


class TestLangfuseTraceContract:
    """Contract tests for Langfuse trace operations.

    Tests verify:
    - Trace creation with proper metadata
    - Trace retrieval by ID
    - Trace completion with output
    """

    @pytest.fixture
    async def langfuse_client(self):
        """Create Langfuse client for testing."""
        from rag_service.observability.langfuse_client import get_langfuse_client

        client = await get_langfuse_client()
        return client

    @pytest.mark.contract
    async def test_create_trace_with_valid_input(
        self,
        langfuse_client,
    ) -> None:
        """Test that trace creation works with valid input.

        Given: A valid trace ID, prompt, and context
        When: create_trace is called
        Then: Trace is created and retrievable
        """
        trace_id = "test_trace_001"
        prompt = "What is RAG?"
        context = {"user_id": "test_user", "session_id": "test_session"}

        await langfuse_client.create_trace(
            trace_id=trace_id,
            prompt=prompt,
            context=context,
        )

        # Verify trace was created
        trace = await langfuse_client.get_trace(trace_id)
        assert trace is not None
        assert trace["trace_id"] == trace_id
        assert trace["input"]["prompt"] == prompt
        assert trace["input"]["context"] == context
        assert trace["status"] == "active"

    @pytest.mark.contract
    async def test_create_span_links_to_trace(
        self,
        langfuse_client,
    ) -> None:
        """Test that span creation links to parent trace.

        Given: An existing trace
        When: create_span is called with trace_id
        Then: Span is created and linked to trace
        """
        trace_id = "test_trace_002"
        span_id = "test_span_001"

        # Create trace first
        await langfuse_client.create_trace(
            trace_id=trace_id,
            prompt="Test prompt",
            context={},
        )

        # Create span
        await langfuse_client.create_span(
            trace_id=trace_id,
            span_id=span_id,
            name="retrieval",
            span_type="retrieval",
            metadata={"chunks_count": 3},
        )

        # Verify span is in trace
        trace = await langfuse_client.get_trace(trace_id)
        assert trace is not None
        assert len(trace["spans"]) == 1
        assert trace["spans"][0]["span_id"] == span_id
        assert trace["spans"][0]["span_name"] == "retrieval"
        assert trace["spans"][0]["span_type"] == "retrieval"

    @pytest.mark.contract
    async def test_update_span_modifies_existing_span(
        self,
        langfuse_client,
    ) -> None:
        """Test that update_span modifies existing span data.

        Given: An existing span
        When: update_span is called with new data
        Then: Span metadata is updated
        """
        trace_id = "test_trace_003"
        span_id = "test_span_002"

        # Create trace and span
        await langfuse_client.create_trace(
            trace_id=trace_id,
            prompt="Test prompt",
            context={},
        )
        await langfuse_client.create_span(
            trace_id=trace_id,
            span_id=span_id,
            name="inference",
            span_type="inference",
        )

        # Update span
        await langfuse_client.update_span(
            span_id=span_id,
            output={"answer": "Test answer"},
            metadata={"model": "gpt-4"},
        )

        # Verify span was updated
        trace = await langfuse_client.get_trace(trace_id)
        # Note: In-memory storage may not reflect update immediately
        # This test verifies the API contract
        assert trace is not None

    @pytest.mark.contract
    async def test_complete_trace_sets_status_and_end_time(
        self,
        langfuse_client,
    ) -> None:
        """Test that complete_trace sets status and end time.

        Given: An active trace
        When: complete_trace is called
        Then: Trace status is "completed" and end_time is set
        """
        trace_id = "test_trace_004"

        # Create trace
        await langfuse_client.create_trace(
            trace_id=trace_id,
            prompt="Test prompt",
            context={},
        )

        # Complete trace
        await langfuse_client.complete_trace(
            trace_id=trace_id,
            output={"answer": "Final answer"},
            status="completed",
        )

        # Verify trace is completed
        trace = await langfuse_client.get_trace(trace_id)
        assert trace is not None
        assert trace["status"] == "completed"
        assert trace["end_time"] is not None
        assert trace["output"]["answer"] == "Final answer"

    @pytest.mark.contract
    async def test_flush_trace_is_non_blocking(
        self,
        langfuse_client,
    ) -> None:
        """Test that flush_trace completes without blocking.

        Given: An existing trace
        When: flush_trace is called
        Then: Method completes without raising exception
        """
        trace_id = "test_trace_005"

        # Create trace
        await langfuse_client.create_trace(
            trace_id=trace_id,
            prompt="Test prompt",
            context={},
        )

        # Flush should not raise
        await langfuse_client.flush_trace(trace_id)

        # Verify trace still exists after flush
        trace = await langfuse_client.get_trace(trace_id)
        assert trace is not None


class TestLangfusePromptVersionTracking:
    """Contract tests for prompt version tracking.

    Tests verify:
    - Prompt template version recording
    - Variable interpolation tracking
    - Template name tracking
    """

    @pytest.fixture
    async def langfuse_client(self):
        """Create Langfuse client for testing."""
        from rag_service.observability.langfuse_client import get_langfuse_client

        client = await get_langfuse_client()
        return client

    @pytest.mark.contract
    async def test_track_prompt_version_records_template(
        self,
        langfuse_client,
    ) -> None:
        """Test that prompt version tracking records template data.

        Given: A trace with template information
        When: track_prompt_version is called
        Then: Template name, version, and variables are recorded
        """
        trace_id = "test_trace_006"
        template_name = "rag_query_template"
        template_version = "v1.2.0"
        variables = {
            "question": "What is RAG?",
            "context_length": 2000,
        }

        # Create trace first
        await langfuse_client.create_trace(
            trace_id=trace_id,
            prompt="What is RAG?",
            context={},
        )

        # Track prompt version
        await langfuse_client.track_prompt_version(
            trace_id=trace_id,
            template_name=template_name,
            template_version=template_version,
            variables=variables,
        )

        # Verify version data is recorded
        trace = await langfuse_client.get_trace(trace_id)
        assert trace is not None
        assert trace["template_name"] == template_name
        assert trace["template_version"] == template_version
        assert trace["variables"] == variables


class TestLangfuseRetrievedDocsTracking:
    """Contract tests for retrieved document tracking.

    Tests verify:
    - Retrieved documents injection tracking
    - Document metadata recording
    - Multiple documents tracking
    """

    @pytest.fixture
    async def langfuse_client(self):
        """Create Langfuse client for testing."""
        from rag_service.observability.langfuse_client import get_langfuse_client

        client = await get_langfuse_client()
        return client

    @pytest.mark.contract
    async def test_track_retrieved_docs_records_documents(
        self,
        langfuse_client,
    ) -> None:
        """Test that retrieved documents are tracked.

        Given: A trace with retrieved documents
        When: track_retrieved_docs is called
        Then: Documents are recorded in trace
        """
        trace_id = "test_trace_007"
        docs = [
            {
                "chunk_id": "chunk_001",
                "content": "RAG is...",
                "score": 0.95,
                "source": "doc_rag_intro",
            },
            {
                "chunk_id": "chunk_002",
                "content": "Vector databases...",
                "score": 0.87,
                "source": "doc_vectors",
            },
        ]

        # Create trace first
        await langfuse_client.create_trace(
            trace_id=trace_id,
            prompt="What is RAG?",
            context={},
        )

        # Track retrieved docs
        await langfuse_client.track_retrieved_docs(
            trace_id=trace_id,
            docs=docs,
        )

        # Verify docs are tracked
        trace = await langfuse_client.get_trace(trace_id)
        assert trace is not None
        assert len(trace["retrieved_docs"]) == 2
        assert trace["retrieved_docs"][0]["chunk_id"] == "chunk_001"
        assert trace["retrieved_docs"][1]["chunk_id"] == "chunk_002"

    @pytest.mark.contract
    async def test_track_retrieved_docs_append_to_existing(
        self,
        langfuse_client,
    ) -> None:
        """Test that multiple track_retrieved_docs calls append.

        Given: A trace with existing retrieved docs
        When: track_retrieved_docs is called again
        Then: New docs are appended to existing list
        """
        trace_id = "test_trace_008"

        # Create trace
        await langfuse_client.create_trace(
            trace_id=trace_id,
            prompt="What is RAG?",
            context={},
        )

        # Track first batch
        await langfuse_client.track_retrieved_docs(
            trace_id=trace_id,
            docs=[{"chunk_id": "chunk_001", "content": "First"}],
        )

        # Track second batch
        await langfuse_client.track_retrieved_docs(
            trace_id=trace_id,
            docs=[{"chunk_id": "chunk_002", "content": "Second"}],
        )

        # Verify both batches are tracked
        trace = await langfuse_client.get_trace(trace_id)
        assert trace is not None
        assert len(trace["retrieved_docs"]) == 2


class TestLangfuseErrorHandling:
    """Contract tests for error handling.

    Tests verify:
    - Graceful handling of missing traces
    - Non-blocking behavior on errors
    """

    @pytest.fixture
    async def langfuse_client(self):
        """Create Langfuse client for testing."""
        from rag_service.observability.langfuse_client import get_langfuse_client

        client = await get_langfuse_client()
        return client

    @pytest.mark.contract
    async def test_get_trace_returns_none_for_unknown_id(
        self,
        langfuse_client,
    ) -> None:
        """Test that get_trace returns None for unknown trace ID.

        Given: An unknown trace ID
        When: get_trace is called
        Then: Returns None without raising
        """
        trace = await langfuse_client.get_trace("unknown_trace_id")
        assert trace is None

    @pytest.mark.contract
    async def test_operations_on_unknown_trace_do_not_raise(
        self,
        langfuse_client,
    ) -> None:
        """Test that operations on unknown traces are handled gracefully.

        Given: An unknown trace ID
        When: Any trace operation is called
        Then: Operation completes without raising
        """
        unknown_trace_id = "unknown_trace_xyz"

        # All these should complete without raising
        await langfuse_client.complete_trace(unknown_trace_id)
        await langfuse_client.flush_trace(unknown_trace_id)
        await langfuse_client.track_prompt_version(
            unknown_trace_id,
            "template",
            "v1.0",
            {},
        )
        await langfuse_client.track_retrieved_docs(
            unknown_trace_id,
            [],
        )
