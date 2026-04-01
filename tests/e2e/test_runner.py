"""
Integration tests for E2E test runner.

Tests the full flow from test file to report generation.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from e2e_test.models.config import TestConfig
from e2e_test.models.test_result import SourceDocsMatch, TestStatus
from e2e_test.runners.test_runner import TestRunner


@pytest.fixture
def mock_rag_response():
    """Mock RAG Service response."""
    return {
        "answer": "RAG Service is a retrieval-augmented generation system.",
        "trace_id": "test-trace-001",
        "source_documents": [
            {"id": "doc_rag_intro", "content": "RAG introduction", "score": 0.92}
        ],
        "metadata": {
            "model": "gpt-4",
            "latency_ms": 500
        }
    }


@pytest.fixture
def test_config():
    """Return test configuration."""
    return TestConfig(
        rag_service_url="http://localhost:8000",
        timeout_seconds=30,
        similarity_threshold=0.7
    )


@pytest.fixture
def runner(test_config):
    """Return TestRunner instance with mocked RAG client."""
    from e2e_test.clients.rag_client import RAGClient

    # Create mock client
    mock_client = AsyncMock()

    runner = TestRunner(config=test_config, rag_client=mock_client)
    runner.mock_client = mock_client  # Store for test manipulation

    return runner


@pytest.fixture
def sample_test_file():
    """Create a sample test file."""
    data = [
        {
            "id": "test_001",
            "question": "What is RAG?",
            "expected_answer": "RAG Service is a retrieval-augmented generation system.",
            "source_docs": ["doc_rag_intro"],
            "tags": ["basic"]
        },
        {
            "id": "test_002",
            "question": "What happens when knowledge base is empty?",
            "tags": ["edge-case"]
        }
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".test.json", delete=False) as f:
        json.dump(data, f)
        return Path(f.name)


@pytest.mark.asyncio
async def test_run_test_file_success(runner, sample_test_file, mock_rag_response):
    """Test running a complete test file successfully."""
    # Mock RAG client responses
    async def mock_query(question, trace_id=None):
        if "RAG" in question:
            return mock_rag_response
        else:
            return {
                "answer": "The service will return a fallback response.",
                "trace_id": trace_id or "test-trace-002",
                "source_documents": [],
                "metadata": {}
            }

    runner.mock_client.query = mock_query

    # Run tests
    report = await runner.run_test_file(sample_test_file)

    # Verify report
    assert report.suite_name == sample_test_file.name
    assert report.total_tests == 2
    assert report.passed >= 1  # At least the basic test should pass
    assert len(report.results) == 2


@pytest.mark.asyncio
async def test_run_test_case_with_similarity(runner, mock_rag_response):
    """Test similarity calculation for test case with expected answer."""
    from e2e_test.models.test_case import TestCase

    test_case = TestCase(
        id="similarity_test",
        question="What is RAG?",
        expected_answer="RAG Service is a retrieval-augmented generation system.",
        source_docs=["doc_rag_intro"]
    )

    runner.mock_client.query = AsyncMock(return_value=mock_rag_response)

    result = await runner.run_test_case(test_case)

    assert result.test_id == "similarity_test"
    assert result.status == TestStatus.PASSED  # High similarity expected
    assert result.similarity_score > 0.5  # Should have some similarity
    assert result.source_docs_match is True
    assert len(result.actual_answer) > 0
    assert result.latency_ms >= 0


@pytest.mark.asyncio
async def test_run_test_case_low_similarity_fails(runner, test_config):
    """Test that low similarity causes test to fail."""
    from e2e_test.models.test_case import TestCase

    # Response with very different answer
    low_similarity_response = {
        "answer": "The quick brown fox jumps over the lazy dog.",
        "trace_id": "test-trace",
        "source_documents": [{"id": "doc_rag_intro", "score": 0.9}],
        "metadata": {}
    }

    test_case = TestCase(
        id="low_sim_test",
        question="What is RAG?",
        expected_answer="RAG Service is a retrieval-augmented generation system."
    )

    runner.mock_client.query = AsyncMock(return_value=low_similarity_response)

    result = await runner.run_test_case(test_case)

    assert result.test_id == "low_sim_test"
    assert result.status == TestStatus.FAILED  # Should fail due to low similarity
    assert result.similarity_score < test_config.similarity_threshold


@pytest.mark.asyncio
async def test_run_test_case_source_docs_mismatch(runner):
    """Test that source docs mismatch causes test to fail."""
    from e2e_test.models.test_case import TestCase

    # Response with wrong source documents
    wrong_docs_response = {
        "answer": "RAG Service is a system.",
        "trace_id": "test-trace",
        "source_documents": [
            {"id": "wrong_doc_1", "score": 0.8},
            {"id": "wrong_doc_2", "score": 0.7}
        ],
        "metadata": {}
    }

    test_case = TestCase(
        id="docs_mismatch_test",
        question="What is RAG?",
        expected_answer="RAG Service is a system.",
        source_docs=["doc_rag_intro"]  # Expect different doc
    )

    runner.mock_client.query = AsyncMock(return_value=wrong_docs_response)

    result = await runner.run_test_case(test_case)

    assert result.test_id == "docs_mismatch_test"
    assert result.status == TestStatus.FAILED  # Should fail due to docs mismatch
    assert result.source_docs_match is False
    assert result.source_docs_match_type == SourceDocsMatch.NONE


@pytest.mark.asyncio
async def test_run_test_case_no_expectations_passes(runner):
    """Test that test with no expected answer or source docs passes."""
    from e2e_test.models.test_case import TestCase

    response = {
        "answer": "Some answer",
        "trace_id": "test-trace",
        "source_documents": [],
        "metadata": {}
    }

    test_case = TestCase(
        id="no_expectations",
        question="What is RAG?"
        # No expected_answer or source_docs
    )

    runner.mock_client.query = AsyncMock(return_value=response)

    result = await runner.run_test_case(test_case)

    assert result.test_id == "no_expectations"
    assert result.status == TestStatus.PASSED  # Should pass (no expectations to fail)


@pytest.mark.asyncio
async def test_run_test_case_rag_error(runner):
    """Test that RAG Service error is handled correctly."""
    from e2e_test.models.test_case import TestCase
    from e2e_test.core.exceptions import RAGConnectionError

    test_case = TestCase(
        id="error_test",
        question="What is RAG?"
    )

    # Mock RAG client raising error
    runner.mock_client.query = AsyncMock(
        side_effect=RAGConnectionError("Connection refused")
    )

    result = await runner.run_test_case(test_case)

    assert result.test_id == "error_test"
    assert result.status == TestStatus.ERROR
    assert result.error is not None
    assert "Connection refused" in result.error


@pytest.mark.asyncio
async def test_parse_unsupported_file_format(runner):
    """Test that unsupported file format raises error."""
    from e2e_test.core.exceptions import TestFileError

    # Create an unsupported file format
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("test content")
        path = Path(f.name)

    with pytest.raises(TestFileError) as exc_info:
        await runner.run_test_file(path)

    assert "Unsupported file extension" in exc_info.value.message


@pytest.mark.asyncio
async def test_report_aggregation(runner, sample_test_file, mock_rag_response):
    """Test that report correctly aggregates statistics."""
    # Mix of passing and failing tests
    async def mock_query(question, trace_id=None):
        if "RAG" in question:
            return mock_rag_response
        else:
            return {
                "answer": "Random unrelated text.",
                "trace_id": trace_id or "test-trace",
                "source_documents": [],
                "metadata": {}
            }

    runner.mock_client.query = mock_query

    report = await runner.run_test_file(sample_test_file)

    # Verify aggregation
    assert report.total_tests == len(report.results)
    assert report.passed + report.failed + report.errors == report.total_tests
    assert report.total_latency_ms > 0
    assert 0.0 <= report.similarity_avg <= 1.0


@pytest.mark.asyncio
async def test_run_empty_test_file(runner):
    """Test that empty test file raises error."""
    from e2e_test.core.exceptions import TestFileError

    with tempfile.NamedTemporaryFile(mode="w", suffix=".test.json", delete=False) as f:
        json.dump([], f)
        path = Path(f.name)

    with pytest.raises(TestFileError) as exc_info:
        await runner.run_test_file(path)

    assert "empty" in exc_info.value.message.lower()
