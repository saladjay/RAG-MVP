"""
Integration tests for JSON test file parser.
"""

import json
import tempfile
from pathlib import Path

import pytest

from e2e_test.models.test_case import TestCase
from e2e_test.parsers.json_parser import JSONParser
from e2e_test.core.exceptions import TestFileError


@pytest.fixture
def valid_test_file():
    """Create a temporary valid test file."""
    data = [
        {
            "id": "test_001",
            "question": "What is RAG?",
            "expected_answer": "Retrieval-Augmented Generation",
            "source_docs": ["doc_001"],
            "tags": ["basic"]
        },
        {
            "id": "test_002",
            "question": "How does vector search work?",
            "tags": ["advanced"]
        }
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        return Path(f.name)


@pytest.fixture
def parser():
    """Return JSONParser instance."""
    return JSONParser()


def test_parse_valid_file(parser, valid_test_file):
    """Test parsing a valid JSON test file."""
    test_cases = parser.parse_and_validate(valid_test_file)

    assert len(test_cases) == 2
    assert test_cases[0].id == "test_001"
    assert test_cases[0].question == "What is RAG?"
    assert test_cases[0].expected_answer == "Retrieval-Augmented Generation"
    assert test_cases[0].source_docs == ["doc_001"]
    assert test_cases[0].tags == ["basic"]

    assert test_cases[1].id == "test_002"
    assert test_cases[1].question == "How does vector search work?"
    assert test_cases[1].expected_answer is None
    assert test_cases[1].tags == ["advanced"]


def test_parse_minimal_test_case(parser):
    """Test parsing a test case with only required fields."""
    data = [{"id": "minimal_test", "question": "Test question"}]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        path = Path(f.name)

    test_cases = parser.parse_and_validate(path)

    assert len(test_cases) == 1
    assert test_cases[0].id == "minimal_test"
    assert test_cases[0].question == "Test question"
    assert test_cases[0].expected_answer is None
    assert test_cases[0].source_docs == []
    assert test_cases[0].tags == []
    assert test_cases[0].metadata == {}


def test_parse_invalid_json(parser):
    """Test parsing invalid JSON raises error."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("{invalid json")
        path = Path(f.name)

    with pytest.raises(TestFileError) as exc_info:
        parser.parse_and_validate(path)

    assert "Invalid JSON format" in exc_info.value.message


def test_parse_non_array_root(parser):
    """Test parsing JSON with non-array root raises error."""
    data = {"not": "an array"}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        path = Path(f.name)

    with pytest.raises(TestFileError) as exc_info:
        parser.parse_and_validate(path)

    assert "must be an array" in exc_info.value.message


def test_parse_duplicate_ids(parser):
    """Test that duplicate test IDs raise error."""
    data = [
        {"id": "duplicate", "question": "First"},
        {"id": "duplicate", "question": "Second"}
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        path = Path(f.name)

    with pytest.raises(TestFileError) as exc_info:
        parser.parse_and_validate(path)

    assert "Duplicate test IDs" in exc_info.value.message
    assert "duplicate" in exc_info.value.details["duplicate_ids"]


def test_parse_missing_required_field(parser):
    """Test that missing required fields raise error."""
    data = [{"id": "test"}]  # Missing 'question'

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        path = Path(f.name)

    with pytest.raises(TestFileError) as exc_info:
        parser.parse_and_validate(path)

    assert "missing required field" in exc_info.value.message.lower()


def test_parse_empty_array(parser):
    """Test that empty array raises error."""
    data = []

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        path = Path(f.name)

    with pytest.raises(TestFileError) as exc_info:
        parser.parse_and_validate(path)

    assert "empty" in exc_info.value.message.lower()


def test_parse_with_metadata(parser):
    """Test parsing test case with metadata."""
    data = [{
        "id": "test_meta",
        "question": "Test",
        "metadata": {
            "priority": "high",
            "author": "test-team",
            "custom_field": 123
        }
    }]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(data, f)
        path = Path(f.name)

    test_cases = parser.parse_and_validate(path)

    assert len(test_cases) == 1
    assert test_cases[0].metadata["priority"] == "high"
    assert test_cases[0].metadata["author"] == "test-team"
    assert test_cases[0].metadata["custom_field"] == 123
