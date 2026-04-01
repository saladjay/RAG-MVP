"""
Integration tests for JSON reporter.
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from e2e_test.models.test_result import SourceDocsMatch, TestStatus, TestResult, TestReport
from e2e_test.reporters.json_report import JSONReporter


class TestJSONReporter:
    """Test JSON reporter functionality."""

    def test_save_report_creates_valid_json(self):
        """Test that save_report creates a valid JSON file."""
        # Create sample report
        report = TestReport(
            suite_name="test_suite",
            total_tests=0,
            passed=0,
            failed=0,
            errors=0,
            skipped=0
        )

        # Add results via add_result to calculate similarity_avg
        result1 = TestResult(
            test_id="test_001",
            status=TestStatus.PASSED,
            actual_answer="Test answer",
            similarity_score=0.95,
            source_docs_retrieved=["doc_001"],
            source_docs_match=True,
            source_docs_match_type=SourceDocsMatch.EXACT,
            latency_ms=150.0
        )
        result2 = TestResult(
            test_id="test_002",
            status=TestStatus.FAILED,
            actual_answer="Wrong answer",
            similarity_score=0.45,
            source_docs_retrieved=["doc_002"],
            source_docs_match=False,
            source_docs_match_type=SourceDocsMatch.NONE,
            latency_ms=200.0
        )

        report.add_result(result1)
        report.add_result(result2)

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            delete=False
        ) as f:
            output_path = Path(f.name)

        try:
            reporter = JSONReporter()
            reporter.save_report(report, output_path)

            # Verify file exists and is valid JSON
            assert output_path.exists()

            with open(output_path, "r") as f:
                data = json.load(f)

            # Verify structure
            assert data["suite_name"] == "test_suite"
            assert "summary" in data
            assert "results" in data
            assert "timestamp" in data

            # Verify summary
            assert data["summary"]["total_tests"] == 2
            assert data["summary"]["passed"] == 1
            assert data["summary"]["failed"] == 1
            assert data["summary"]["pass_rate"] == 0.5
            assert data["summary"]["similarity_avg"] == 0.7  # (0.95 + 0.45) / 2

            # Verify results
            assert len(data["results"]) == 2
            assert data["results"][0]["test_id"] == "test_001"
            assert data["results"][0]["status"] == "passed"
            assert data["results"][1]["test_id"] == "test_002"
            assert data["results"][1]["status"] == "failed"
        finally:
            output_path.unlink()

    def test_save_report_creates_parent_directory(self):
        """Test that save_report creates parent directories if needed."""
        report = TestReport(
            suite_name="test",
            total_tests=1,
            passed=1,
            failed=0,
            errors=0,
            skipped=0
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "nested" / "dir" / "report.json"

            reporter = JSONReporter()
            reporter.save_report(report, output_path)

            assert output_path.exists()
            assert output_path.parent.exists()

    def test_get_report_json_returns_string(self):
        """Test that get_report_json returns JSON string."""
        report = TestReport(
            suite_name="test",
            total_tests=1,
            passed=1,
            failed=0,
            errors=0,
            skipped=0,
            results=[
                TestResult(
                    test_id="test_001",
                    status=TestStatus.PASSED,
                    actual_answer="Answer",
                    latency_ms=100.0
                )
            ]
        )

        reporter = JSONReporter()
        json_str = reporter.get_report_json(report)

        assert isinstance(json_str, str)

        # Verify it's valid JSON
        data = json.loads(json_str)
        assert data["suite_name"] == "test"

    def test_pretty_false_compacts_output(self):
        """Test that pretty=false produces compact JSON."""
        report = TestReport(
            suite_name="test",
            total_tests=1,
            passed=1,
            failed=0,
            errors=0,
            skipped=0
        )

        reporter_pretty = JSONReporter(pretty=True)
        reporter_compact = JSONReporter(pretty=False)

        json_pretty = reporter_pretty.get_report_json(report)
        json_compact = reporter_compact.get_report_json(report)

        # Compact should be shorter
        assert len(json_compact) < len(json_pretty)

        # Both should be valid JSON
        assert json.loads(json_pretty)["suite_name"] == "test"
        assert json.loads(json_compact)["suite_name"] == "test"

    def test_includes_error_field_when_present(self):
        """Test that error field is included when test has error."""
        result = TestResult(
            test_id="test_001",
            status=TestStatus.ERROR,
            actual_answer="",
            error="Connection timeout"
        )

        report = TestReport(
            suite_name="test",
            total_tests=1,
            passed=0,
            failed=0,
            errors=1,
            skipped=0,
            results=[result]
        )

        reporter = JSONReporter()
        json_str = reporter.get_report_json(report)
        data = json.loads(json_str)

        assert "error" in data["results"][0]
        assert data["results"][0]["error"] == "Connection timeout"

    def test_excludes_actual_answer_when_empty(self):
        """Test that actual_answer is not included when empty."""
        result = TestResult(
            test_id="test_001",
            status=TestStatus.PASSED,
            actual_answer=""
        )

        report = TestReport(
            suite_name="test",
            total_tests=1,
            passed=1,
            failed=0,
            errors=0,
            skipped=0,
            results=[result]
        )

        reporter = JSONReporter()
        json_str = reporter.get_report_json(report)
        data = json.loads(json_str)

        assert "actual_answer" not in data["results"][0]

    def test_timestamp_serialization(self):
        """Test that datetime is properly serialized to ISO format."""
        fixed_time = datetime(2026, 3, 30, 12, 0, 0)

        result = TestResult(
            test_id="test_001",
            status=TestStatus.PASSED,
            actual_answer="Answer",
            timestamp=fixed_time
        )

        report = TestReport(
            suite_name="test",
            total_tests=1,
            passed=1,
            failed=0,
            errors=0,
            skipped=0,
            results=[result],
            timestamp=fixed_time
        )

        reporter = JSONReporter()
        json_str = reporter.get_report_json(report)
        data = json.loads(json_str)

        assert data["timestamp"] == "2026-03-30T12:00:00"
        assert data["results"][0]["timestamp"] == "2026-03-30T12:00:00"

    def test_source_docs_match_type_serialization(self):
        """Test that SourceDocsMatch enum is properly serialized."""
        for match_type in [
            SourceDocsMatch.EXACT,
            SourceDocsMatch.SUPERSET,
            SourceDocsMatch.SUBSET,
            SourceDocsMatch.NONE,
            SourceDocsMatch.NOT_APPLICABLE
        ]:
            result = TestResult(
                test_id=f"test_{match_type.value}",
                status=TestStatus.PASSED,
                actual_answer="Answer",
                source_docs_match_type=match_type
            )

            report = TestReport(
                suite_name="test",
                total_tests=1,
                passed=1,
                failed=0,
                errors=0,
                skipped=0,
                results=[result]
            )

            reporter = JSONReporter()
            json_str = reporter.get_report_json(report)
            data = json.loads(json_str)

            assert data["results"][0]["source_docs"]["match_type"] == match_type.value

    def test_empty_report(self):
        """Test JSON reporter with empty report (no tests run)."""
        report = TestReport(
            suite_name="empty_suite",
            total_tests=0,
            passed=0,
            failed=0,
            errors=0,
            skipped=0
        )

        reporter = JSONReporter()
        json_str = reporter.get_report_json(report)
        data = json.loads(json_str)

        assert data["suite_name"] == "empty_suite"
        assert data["summary"]["total_tests"] == 0
        assert data["results"] == []
        assert data["summary"]["pass_rate"] == 1.0  # Empty = 100% pass rate
