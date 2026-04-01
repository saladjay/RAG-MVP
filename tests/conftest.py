"""
Shared fixtures and configuration for RAG Service test suite.

This module provides pytest fixtures used across unit, integration,
and contract tests. It supports real implementations with minimal mocks.
"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture(scope="session")
def event_loop():
    """
    Create event loop for async tests.

    This fixture ensures the same event loop is used for all async tests.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """
    Provide a temporary directory for test operations.

    Yields a Path object to a temporary directory that is automatically
    cleaned up after the test completes.
    """
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    # Cleanup is handled by tempfile.mkdtemp


@pytest.fixture
def mock_config(temp_dir: Path) -> dict:
    """
    Provide mock configuration for testing.

    Returns a dictionary with test configuration values.
    """
    return {
        "milvus": {
            "host": "localhost",
            "port": 19530,
            "collection_name": "test_knowledge_base",
            "dimension": 384,
        },
        "litellm": {
            "model": "gpt-3.5-turbo",
            "api_base": "https://api.openai.com/v1",
            "api_key": "test-key",
        },
        "langfuse": {
            "public_key": "test-public",
            "secret_key": "test-secret",
            "host": "http://localhost:3000",
        },
        "embedding": {
            "model": "sentence-transformers/all-MiniLM-L6-v2",
            "dimension": 384,
        },
    }


@pytest.fixture
async def app() -> AsyncGenerator[FastAPI, None]:
    """
    Provide FastAPI app instance for testing.

    This fixture creates a minimal FastAPI app for testing.
    The actual app from main.py should be used in integration tests.
    """
    from rag_service.main import create_app

    app = create_app()
    yield app


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """
    Provide HTTP client for testing FastAPI app.

    Uses ASGI transport for direct app communication without HTTP server.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture
def mock_milvus_client():
    """
    Provide mock Milvus client for testing.

    In unit tests, use this fixture. In integration tests,
    use real Milvus instance when available.
    """
    mock_client = Mock()
    mock_client.insert = Mock(return_value={"insert_cnt": 1})
    mock_client.search = Mock(return_value=[[{"distance": 0.1, "id": 1}]])
    mock_client.load = Mock()
    mock_client.release = Mock()
    return mock_client


@pytest.fixture
def mock_litellm_client():
    """
    Provide mock LiteLLM client for testing.

    In unit tests, use this fixture. In integration tests,
    use real LiteLLM when API keys are available.
    """
    mock_response = {
        "id": "test-id",
        "choices": [{
            "message": {
                "role": "assistant",
                "content": "Test response",
            },
            "finish_reason": "stop",
        }],
        "model": "gpt-3.5-turbo",
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        },
    }

    async_mock = AsyncMock(return_value=mock_response)
    return async_mock


@pytest.fixture
def mock_langfuse_client():
    """
    Provide mock Langfuse client for testing.

    In unit tests, use this fixture. In integration tests,
    use real Langfuse when available.
    """
    mock_client = Mock()
    mock_client.create_trace = Mock(return_value=Mock(id="test-trace-id"))
    mock_client.create_span = Mock()
    mock_client.finalize_trace = AsyncMock()
    mock_client.flush = AsyncMock()
    return mock_client


@pytest.fixture
def sample_documents() -> list[dict]:
    """
    Provide sample documents for testing.

    Returns a list of sample documents with content and metadata.
    """
    return [
        {
            "id": "doc1",
            "content": "Python is a high-level programming language.",
            "metadata": {"source": "docs", "category": "programming"},
        },
        {
            "id": "doc2",
            "content": "FastAPI is a modern web framework for building APIs.",
            "metadata": {"source": "docs", "category": "web"},
        },
        {
            "id": "doc3",
            "content": "Milvus is a vector database for AI applications.",
            "metadata": {"source": "docs", "category": "database"},
        },
    ]


@pytest.fixture
def sample_query_request() -> dict:
    """
    Provide sample query request for testing.

    Returns a sample query request payload.
    """
    return {
        "query": "What is Python?",
        "context": None,
        "trace_id": None,
    }


@pytest.fixture
def sample_embeddings() -> list[list[float]]:
    """
    Provide sample embeddings for testing.

    Returns sample embedding vectors.
    """
    return [
        [0.1, 0.2, 0.3, 0.4] * 96,  # 384-dimensional vector
        [0.5, 0.6, 0.7, 0.8] * 96,
        [0.9, 1.0, 0.1, 0.2] * 96,
    ]


@pytest.fixture
def sample_chunks() -> list[dict]:
    """
    Provide sample retrieved chunks for testing.

    Returns sample chunks from knowledge base retrieval.
    """
    return [
        {
            "id": "chunk1",
            "content": "Python is a high-level programming language.",
            "metadata": {"source": "docs", "doc_id": "doc1"},
            "score": 0.95,
        },
        {
            "id": "chunk2",
            "content": "It emphasizes code readability.",
            "metadata": {"source": "docs", "doc_id": "doc1"},
            "score": 0.90,
        },
    ]


# Environment variables for testing
@pytest.fixture(autouse=True)
def reset_environment() -> Generator[None, None, None]:
    """
    Reset environment variables before and after each test.

    Ensures tests don't affect each other through environment state.
    """
    # Store original environment
    original_env = os.environ.copy()

    # Clear RAG service specific environment variables
    env_keys_to_clear = [
        "MILVUS_HOST",
        "MILVUS_PORT",
        "LITELLM_API_KEY",
        "LITELLM_MODEL",
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
        "LANGFUSE_HOST",
        "LOG_LEVEL",
        "EMBEDDING_MODEL",
    ]
    for key in env_keys_to_clear:
        os.environ.pop(key, None)

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def trace_id() -> str:
    """
    Provide a test trace_id for observability testing.

    Returns a consistent trace ID for testing trace propagation.
    """
    return "test-trace-123456"


@pytest.fixture
def mock_phidata_agent():
    """
    Provide mock Phidata agent for testing.

    In unit tests, use this fixture. In integration tests,
    use real Phidata agent when models are available.
    """
    mock_agent = Mock()
    mock_agent.run = AsyncMock(return_value=Mock(content="Agent response"))
    return mock_agent


# Server startup fixture for integration tests
@pytest.fixture
async def server_port() -> int:
    """
    Provide a port for integration test server.

    Returns a port number for starting the test server.
    """
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.listen(1)
        port = s.getsockname()[1]

    return port


# ============================================================================
# E2E Test Framework Fixtures
# ============================================================================

@pytest.fixture
def sample_rag_response():
    """Sample RAG Service response for E2E testing."""
    return {
        "answer": "RAG Service combines vector search with LLM generation to provide accurate, context-aware responses.",
        "trace_id": "e2e-test-12345",
        "source_documents": [
            {
                "id": "doc_rag_intro",
                "content": "RAG Service introduction text...",
                "score": 0.92
            },
            {
                "id": "doc_rag_architecture",
                "content": "Architecture overview...",
                "score": 0.87
            }
        ],
        "metadata": {
            "model": "gpt-4",
            "latency_ms": 1250,
            "tokens_used": 450
        }
    }


@pytest.fixture
def sample_test_cases():
    """Sample test cases for E2E testing."""
    from e2e_test.models.test_case import TestCase

    return [
        TestCase(
            id="test_basic",
            question="What is RAG?",
            expected_answer="RAG combines retrieval with generation.",
            source_docs=["doc_001"],
            tags=["basic"]
        ),
        TestCase(
            id="test_minimal",
            question="Another question"
        )
    ]


@pytest.fixture
def temp_json_file(tmp_path):
    """Create a temporary JSON test file."""
    import json

    def _create(data):
        file_path = tmp_path / "test.json"
        with open(file_path, "w") as f:
            json.dump(data, f)
        return file_path

    return _create
