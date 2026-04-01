"""
Test runner for executing E2E test cases against RAG Service.

Orchestrates test execution including parsing, querying, comparing,
and aggregating results.
"""

import asyncio
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from e2e_test.clients.rag_client import RAGClient
from e2e_test.comparators.similarity import SimilarityCalculator
from e2e_test.comparators.validator import SourceDocsValidator
from e2e_test.core.exceptions import E2ETestError, TestFileError
from e2e_test.core.logger import get_logger
from e2e_test.models.config import TestConfig
from e2e_test.models.test_case import TestCase
from e2e_test.models.test_result import SourceDocsMatch, TestResult, TestStatus, TestReport
from e2e_test.parsers.factory import ParserFactory


class TestRunner:
    """Execute E2E test cases against RAG Service."""

    def __init__(
        self,
        config: Optional[TestConfig] = None,
        rag_client: Optional[RAGClient] = None
    ) -> None:
        """Initialize test runner.

        Args:
            config: Test configuration (uses defaults if None)
            rag_client: RAG Service client (creates default if None)
        """
        self.config = config or TestConfig()
        self.rag_client = rag_client or RAGClient(
            base_url=self.config.rag_service_url,
            timeout_seconds=self.config.timeout_seconds,
            retry_count=self.config.retry_count
        )
        self.logger = get_logger()

    async def run_test_file(
        self,
        file_path: Path,
        tags: Optional[List[str]] = None,
        exclude_tags: Optional[List[str]] = None,
        test_ids: Optional[List[str]] = None
    ) -> TestReport:
        """Run all tests from a single test file.

        Args:
            file_path: Path to test file
            tags: Optional list of tags to filter by (only tests with these tags will run)
            exclude_tags: Optional list of tags to exclude (tests with these tags will be skipped)
            test_ids: Optional list of specific test IDs to run (other tests will be skipped)

        Returns:
            TestReport with aggregated results

        Raises:
            TestFileError: If file cannot be parsed
        """
        self.logger.suite_start(
            suite_name=file_path.name,
            total_tests=0  # Will update after parsing
        )

        start_time = time.time()

        # Parse test file
        test_cases = self._parse_test_file(file_path)

        # Apply filters
        test_cases = self._filter_test_cases(
            test_cases,
            tags=tags,
            exclude_tags=exclude_tags,
            test_ids=test_ids
        )

        self.logger.suite_start(
            suite_name=file_path.name,
            total_tests=len(test_cases)
        )

        # Run all test cases
        results = []
        for test_case in test_cases:
            result = await self._run_single_test(test_case)
            results.append(result)

        # Build report
        duration_ms = (time.time() - start_time) * 1000

        report = TestReport(
            suite_name=file_path.name,
            total_tests=len(test_cases),
            passed=sum(1 for r in results if r.status == TestStatus.PASSED),
            failed=sum(1 for r in results if r.status == TestStatus.FAILED),
            errors=sum(1 for r in results if r.status == TestStatus.ERROR),
            skipped=0,
            results=results,
            total_latency_ms=duration_ms
        )

        # Calculate average similarity
        scored_results = [r for r in results if r.similarity_score > 0]
        if scored_results:
            report.similarity_avg = sum(r.similarity_score for r in scored_results) / len(scored_results)

        self.logger.suite_complete(
            suite_name=file_path.name,
            passed=report.passed,
            failed=report.failed,
            errors=report.errors,
            duration_ms=duration_ms
        )

        return report

    async def run_test_case(self, test_case: TestCase) -> TestResult:
        """Run a single test case.

        Args:
            test_case: Test case to execute

        Returns:
            TestResult with execution details
        """
        return await self._run_single_test(test_case)

    async def _run_single_test(self, test_case: TestCase) -> TestResult:
        """Execute a single test case.

        Args:
            test_case: Test case to execute

        Returns:
            TestResult with execution details
        """
        trace_id = f"e2e-{test_case.id}-{uuid.uuid4()}"
        start_time = time.time()

        self.logger.test_start(
            test_id=test_case.id,
            question=test_case.question,
            trace_id=trace_id
        )

        try:
            # Query RAG Service
            response = await self.rag_client.query(
                question=test_case.question,
                trace_id=trace_id
            )

            # Extract answer and source documents
            actual_answer = response.get("answer", "")
            source_docs_data = response.get("source_documents", [])
            actual_docs = [doc.get("id", "") for doc in source_docs_data if doc.get("id")]

            # Calculate similarity if expected answer provided
            similarity = 0.0
            if test_case.has_expected_answer:
                similarity = SimilarityCalculator.calculate(
                    actual=actual_answer,
                    expected=test_case.expected_answer,
                    method="levenshtein"
                )

            # Validate source documents
            source_match, source_match_type = SourceDocsValidator.validate(
                expected_docs=test_case.source_docs,
                actual_docs=actual_docs
            )

            # Determine test status
            status = self._determine_status(
                similarity=similarity,
                source_match=source_match,
                test_case=test_case
            )

            latency_ms = (time.time() - start_time) * 1000

            result = TestResult(
                test_id=test_case.id,
                status=status,
                actual_answer=actual_answer,
                similarity_score=similarity,
                source_docs_retrieved=actual_docs,
                source_docs_match=source_match,
                source_docs_match_type=source_match_type,
                latency_ms=latency_ms
            )

            self.logger.test_complete(
                test_id=test_case.id,
                status=status.value,
                similarity=similarity,
                latency_ms=latency_ms
            )

            return result

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000

            self.logger.test_error(
                test_id=test_case.id,
                error_message=str(e)
            )

            return TestResult(
                test_id=test_case.id,
                status=TestStatus.ERROR,
                actual_answer="",
                error=str(e),
                latency_ms=latency_ms
            )

    def _determine_status(
        self,
        similarity: float,
        source_match: bool,
        test_case: TestCase
    ) -> TestStatus:
        """Determine test status based on comparison results.

        Args:
            similarity: Similarity score (0-1)
            source_match: Whether source docs match
            test_case: Original test case

        Returns:
            TestStatus (PASSED, FAILED, or ERROR)
        """
        # If no expected answer, pass based on successful execution
        if not test_case.has_expected_answer and not test_case.has_source_docs:
            return TestStatus.PASSED

        # Check similarity threshold
        if test_case.has_expected_answer:
            if similarity < self.config.similarity_threshold:
                return TestStatus.FAILED

        # Check source docs match
        if test_case.has_source_docs and not source_match:
            return TestStatus.FAILED

        return TestStatus.PASSED

    def _parse_test_file(self, file_path: Path) -> List[TestCase]:
        """Parse test file and return test cases.

        Args:
            file_path: Path to test file

        Returns:
            List of test cases

        Raises:
            TestFileError: If file format is not supported
        """
        parser = ParserFactory.create_parser(file_path)
        return parser.parse(file_path)

    def _filter_test_cases(
        self,
        test_cases: List[TestCase],
        tags: Optional[List[str]] = None,
        exclude_tags: Optional[List[str]] = None,
        test_ids: Optional[List[str]] = None
    ) -> List[TestCase]:
        """Filter test cases based on tags and/or test IDs.

        Args:
            test_cases: List of test cases to filter
            tags: Only include tests with these tags (any match)
            exclude_tags: Exclude tests with these tags (any match)
            test_ids: Only include tests with these IDs

        Returns:
            Filtered list of test cases
        """
        filtered = test_cases

        # Filter by test IDs (highest priority)
        if test_ids:
            test_ids_set = set(test_ids)
            filtered = [tc for tc in filtered if tc.id in test_ids_set]

        # Filter by included tags
        if tags:
            tags_set = set(tags)
            filtered = [tc for tc in filtered if any(tag in tags_set for tag in tc.tags)]

        # Filter by excluded tags
        if exclude_tags:
            exclude_tags_set = set(exclude_tags)
            filtered = [tc for tc in filtered if not any(tag in exclude_tags_set for tag in tc.tags)]

        return filtered
