"""
Test result models including status enums and result data structures.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class TestStatus(str, Enum):
    """Test execution status."""
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


class SourceDocsMatch(str, Enum):
    """Source document match result."""
    EXACT = "exact"
    SUPERSET = "superset"
    SUBSET = "subset"
    NONE = "none"
    NOT_APPLICABLE = "n/a"


class TestResult(BaseModel):
    """Result of a single test case execution."""

    test_id: str
    status: TestStatus
    actual_answer: str
    similarity_score: float = Field(ge=0.0, le=1.0, default=0.0)
    source_docs_retrieved: List[str] = Field(default_factory=list)
    source_docs_match: bool = False
    source_docs_match_type: SourceDocsMatch = SourceDocsMatch.NOT_APPLICABLE
    error: Optional[str] = None
    latency_ms: float = Field(default=0.0, ge=0.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("test_id")
    @classmethod
    def test_id_must_be_valid(cls, v: str) -> str:
        """Validate test ID is not empty."""
        if not v or v.isspace():
            raise ValueError("Test ID cannot be empty")
        return v

    @property
    def is_passed(self) -> bool:
        """Check if test passed.

        Returns:
            True if test status is PASSED and (if source_docs specified) they match
        """
        if self.status != TestStatus.PASSED:
            return False
        return True

    @property
    def latency_s(self) -> float:
        """Latency in seconds."""
        return self.latency_ms / 1000.0


class TestReport(BaseModel):
    """Aggregated report for a test suite execution."""

    suite_name: str
    total_tests: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    errors: int = Field(ge=0)
    skipped: int = Field(ge=0)
    results: List[TestResult] = Field(default_factory=list)
    similarity_avg: float = Field(ge=0.0, le=1.0, default=0.0)
    total_latency_ms: float = Field(default=0.0, ge=0.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @property
    def pass_rate(self) -> float:
        """Calculate pass rate (0-1).

        Returns:
            Pass rate as fraction. Returns 1.0 if no tests.
        """
        if self.total_tests == 0:
            return 1.0
        return self.passed / self.total_tests

    @property
    def execution_time_s(self) -> float:
        """Total execution time in seconds."""
        return self.total_latency_ms / 1000.0

    def add_result(self, result: TestResult) -> None:
        """Add a test result and update aggregates.

        Args:
            result: Test result to add
        """
        self.results.append(result)
        self.total_tests += 1

        if result.status == TestStatus.PASSED:
            self.passed += 1
        elif result.status == TestStatus.FAILED:
            self.failed += 1
        elif result.status == TestStatus.ERROR:
            self.errors += 1
        elif result.status == TestStatus.SKIPPED:
            self.skipped += 1

        self.total_latency_ms += result.latency_ms

        # Recalculate average similarity
        scored_results = [r for r in self.results if r.similarity_score > 0]
        if scored_results:
            self.similarity_avg = sum(r.similarity_score for r in scored_results) / len(scored_results)
