"""
Unit tests for External KB Test Runner.
"""

import json
import tempfile
from pathlib import Path

import pytest

from e2e_test.runners.external_kb_test import (
    ExternalKBTestInput,
    ExternalKBTestResult,
    ExternalKBTestRunner,
)


class TestExternalKBTestInput:
    """Tests for ExternalKBTestInput."""

    def test_init(self) -> None:
        """Test initialization of ExternalKBTestInput."""
        input_data = ExternalKBTestInput(
            title="Test Title",
            query="Test Query",
            answer_list=["Answer 1", "Answer 2"],
        )

        assert input_data.title == "Test Title"
        assert input_data.query == "Test Query"
        assert input_data.answer_list == ["Answer 1", "Answer 2"]


class TestExternalKBTestResult:
    """Tests for ExternalKBTestResult."""

    def test_init_success(self) -> None:
        """Test initialization of successful ExternalKBTestResult."""
        result = ExternalKBTestResult(
            title="Test Title",
            query="Test Query",
            expected_answers=["Answer 1"],
            chunks=[{"content": "Test content"}],
            success=True,
        )

        assert result.title == "Test Title"
        assert result.query == "Test Query"
        assert result.success is True
        assert result.error is None
        assert len(result.chunks) == 1

    def test_init_failure(self) -> None:
        """Test initialization of failed ExternalKBTestResult."""
        result = ExternalKBTestResult(
            title="Test Title",
            query="Test Query",
            expected_answers=["Answer 1"],
            chunks=[],
            success=False,
            error="Connection failed",
        )

        assert result.success is False
        assert result.error == "Connection failed"
        assert len(result.chunks) == 0

    def test_to_dict(self) -> None:
        """Test to_dict method."""
        result = ExternalKBTestResult(
            title="Test Title",
            query="Test Query",
            expected_answers=["Answer 1", "Answer 2"],
            chunks=[{"content": "Test", "score": 0.9}],
            success=True,
        )

        data = result.to_dict()

        assert data["title"] == "Test Title"
        assert data["query"] == "Test Query"
        assert data["expected_answers"] == ["Answer 1", "Answer 2"]
        assert data["chunk_count"] == 1
        assert data["success"] is True
        assert data["error"] is None


class TestExternalKBTestRunner:
    """Tests for ExternalKBTestRunner."""

    def test_init(self) -> None:
        """Test initialization of ExternalKBTestRunner."""
        runner = ExternalKBTestRunner(
            base_url="http://localhost:8001",
            comp_id="N000131",
            file_type="PublicDocDispatch",
            search_type=1,
            topk=10,
        )

        assert runner.base_url == "http://localhost:8001"
        assert runner.comp_id == "N000131"
        assert runner.file_type == "PublicDocDispatch"
        assert runner.search_type == 1
        assert runner.topk == 10

    def test_parse_jsonl_with_separator(self) -> None:
        """Test parsing JSONL file with ### separator."""
        # Create temporary JSONL file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"title_question": "Doc Title###What is the query?", "answear_list": ["Answer"]}\n')
            f.write('{"title_question": "Another Doc###Another question?", "answear_list": ["A1", "A2"]}\n')
            temp_path = Path(f.name)

        try:
            inputs = ExternalKBTestRunner.parse_jsonl(temp_path)

            assert len(inputs) == 2
            assert inputs[0].title == "Doc Title"
            assert inputs[0].query == "What is the query?"
            assert inputs[0].answer_list == ["Answer"]

            assert inputs[1].title == "Another Doc"
            assert inputs[1].query == "Another question?"
            assert inputs[1].answer_list == ["A1", "A2"]
        finally:
            temp_path.unlink()

    def test_parse_jsonl_without_separator(self) -> None:
        """Test parsing JSONL file without ### separator."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"title_question": "Doc Title - What is the query?", "answear_list": ["Answer"]}\n')
            temp_path = Path(f.name)

        try:
            inputs = ExternalKBTestRunner.parse_jsonl(temp_path)

            assert len(inputs) == 1
            # When no separator, both title and query get the full string
            assert inputs[0].title == "Doc Title - What is the query?"
            assert inputs[0].query == "Doc Title - What is the query?"
        finally:
            temp_path.unlink()

    def test_parse_jsonl_empty_lines(self) -> None:
        """Test parsing JSONL file with empty lines."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"title_question": "Doc###Query?", "answear_list": ["A"]}\n')
            f.write("\n")  # Empty line
            f.write('{"title_question": "Doc2###Query2?", "answear_list": ["A2"]}\n')
            temp_path = Path(f.name)

        try:
            inputs = ExternalKBTestRunner.parse_jsonl(temp_path)

            assert len(inputs) == 2  # Empty lines should be skipped
        finally:
            temp_path.unlink()

    def test_parse_jsonl_file_not_found(self) -> None:
        """Test parsing non-existent file."""
        with pytest.raises(Exception) as exc_info:
            ExternalKBTestRunner.parse_jsonl(Path("nonexistent.jsonl"))

        assert "File not found" in str(exc_info.value)

    def test_parse_jsonl_invalid_json(self) -> None:
        """Test parsing file with invalid JSON."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"title_question": "Doc###Query?", "answear_list": ["A"]}\n')
            f.write('invalid json line\n')
            temp_path = Path(f.name)

        try:
            with pytest.raises(Exception) as exc_info:
                ExternalKBTestRunner.parse_jsonl(temp_path)

            assert "Invalid JSON" in str(exc_info.value)
        finally:
            temp_path.unlink()

    def test_save_results(self) -> None:
        """Test saving results to file."""
        results = [
            ExternalKBTestResult(
                title="Test",
                query="Query?",
                expected_answers=["A"],
                chunks=[{"content": "Content"}],
                success=True,
            ),
            ExternalKBTestResult(
                title="Test2",
                query="Query2?",
                expected_answers=["A2"],
                chunks=[],
                success=False,
                error="Failed",
            ),
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = Path(f.name)

        try:
            runner = ExternalKBTestRunner(base_url="http://localhost:8001")
            runner.save_results(results, temp_path)

            # Verify file contents
            with open(temp_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            assert data["total_tests"] == 2
            assert data["successful"] == 1
            assert data["failed"] == 1
            assert len(data["results"]) == 2

            # Check first result
            assert data["results"][0]["title"] == "Test"
            assert data["results"][0]["success"] is True

            # Check second result
            assert data["results"][1]["success"] is False
            assert data["results"][1]["error"] == "Failed"
        finally:
            temp_path.unlink()
