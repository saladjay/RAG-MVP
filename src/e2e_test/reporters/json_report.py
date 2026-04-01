"""
JSON reporter for exporting test results.

Provides JSON export functionality with detailed metrics and formatting.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from e2e_test.models.test_result import TestReport


class JSONReporter:
    """Generate JSON reports for test results."""

    def __init__(self, pretty: bool = True, ensure_ascii: bool = False) -> None:
        """Initialize JSON reporter.

        Args:
            pretty: Enable pretty-printing with indentation
            ensure_ascii: Whether to escape non-ASCII characters
        """
        self.pretty = pretty
        self.ensure_ascii = ensure_ascii

    def save_report(self, report: TestReport, output_path: Path) -> None:
        """Save test report as JSON file.

        Args:
            report: Test report to save
            output_path: Output file path

        Raises:
            IOError: If file cannot be written
        """
        # Convert report to dict
        data = self._report_to_dict(report)

        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Write to file
        with open(output_path, "w", encoding="utf-8") as f:
            if self.pretty:
                json.dump(data, f, indent=2, ensure_ascii=self.ensure_ascii)
            else:
                json.dump(data, f, ensure_ascii=self.ensure_ascii)

    def get_report_json(self, report: TestReport) -> str:
        """Get test report as JSON string.

        Args:
            report: Test report to convert

        Returns:
            JSON string representation of report
        """
        data = self._report_to_dict(report)
        return json.dumps(data, indent=2 if self.pretty else None, ensure_ascii=self.ensure_ascii)

    def _report_to_dict(self, report: TestReport) -> Dict[str, Any]:
        """Convert TestReport to dictionary for JSON serialization.

        Args:
            report: Test report to convert

        Returns:
            Dictionary representation of report
        """
        return {
            "suite_name": report.suite_name,
            "summary": {
                "total_tests": report.total_tests,
                "passed": report.passed,
                "failed": report.failed,
                "errors": report.errors,
                "skipped": report.skipped,
                "pass_rate": report.pass_rate,
                "similarity_avg": report.similarity_avg,
                "execution_time_s": report.execution_time_s
            },
            "results": [
                self._result_to_dict(result)
                for result in report.results
            ],
            "timestamp": self._serialize_datetime(report.timestamp)
        }

    def _result_to_dict(self, result) -> Dict[str, Any]:
        """Convert TestResult to dictionary for JSON serialization.

        Args:
            result: Test result to convert

        Returns:
            Dictionary representation of result
        """
        data = {
            "test_id": result.test_id,
            "status": result.status.value,
            "similarity_score": result.similarity_score,
            "source_docs": {
                "retrieved": result.source_docs_retrieved,
                "match": result.source_docs_match,
                "match_type": result.source_docs_match_type.value
            },
            "latency_ms": result.latency_ms,
            "timestamp": self._serialize_datetime(result.timestamp)
        }

        # Add optional fields
        if result.actual_answer:
            data["actual_answer"] = result.actual_answer

        if result.error:
            data["error"] = result.error

        return data

    def _serialize_datetime(self, dt: datetime) -> str:
        """Serialize datetime to ISO 8601 format string.

        Args:
            dt: DateTime to serialize

        Returns:
            ISO 8601 formatted string
        """
        return dt.isoformat()
