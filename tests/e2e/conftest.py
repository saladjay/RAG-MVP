"""
Pytest configuration and shared fixtures for E2E Test Framework tests.
"""

import pytest
import sys
from pathlib import Path

# Add src directory to Python path for imports
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))


@pytest.fixture
def sample_rag_response():
    """Sample RAG Service response for testing."""
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
    """Sample test cases for testing."""
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
