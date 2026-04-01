"""
Integration tests for test filtering functionality.
"""

import tempfile
from pathlib import Path
from typing import List

import pytest

from e2e_test.models.test_case import TestCase
from e2e_test.runners.test_runner import TestRunner


class TestTestFiltering:
    """Test test case filtering functionality."""

    def _create_test_cases(self) -> List[TestCase]:
        """Create sample test cases with different tags and IDs."""
        return [
            TestCase(
                id="test_001",
                question="Question 1",
                tags=["unit", "fast"]
            ),
            TestCase(
                id="test_002",
                question="Question 2",
                tags=["integration", "slow"]
            ),
            TestCase(
                id="test_003",
                question="Question 3",
                tags=["unit", "medium"]
            ),
            TestCase(
                id="test_004",
                question="Question 4",
                tags=["e2e", "slow"]
            ),
            TestCase(
                id="test_005",
                question="Question 5",
                tags=[]  # No tags
            )
        ]

    def test_filter_by_single_tag(self):
        """Test filtering by a single tag."""
        test_cases = self._create_test_cases()
        runner = TestRunner()

        filtered = runner._filter_test_cases(test_cases, tags=["unit"])

        assert len(filtered) == 2
        assert {tc.id for tc in filtered} == {"test_001", "test_003"}

    def test_filter_by_multiple_tags(self):
        """Test filtering by multiple tags (any match)."""
        test_cases = self._create_test_cases()
        runner = TestRunner()

        filtered = runner._filter_test_cases(test_cases, tags=["unit", "e2e"])

        assert len(filtered) == 3
        assert {tc.id for tc in filtered} == {"test_001", "test_003", "test_004"}

    def test_filter_by_exclude_tag(self):
        """Test excluding tests with specific tags."""
        test_cases = self._create_test_cases()
        runner = TestRunner()

        filtered = runner._filter_test_cases(test_cases, exclude_tags=["slow"])

        assert len(filtered) == 3
        assert {tc.id for tc in filtered} == {"test_001", "test_003", "test_005"}

    def test_filter_by_multiple_exclude_tags(self):
        """Test excluding tests with multiple tags."""
        test_cases = self._create_test_cases()
        runner = TestRunner()

        filtered = runner._filter_test_cases(test_cases, exclude_tags=["slow", "medium"])

        assert len(filtered) == 2
        assert {tc.id for tc in filtered} == {"test_001", "test_005"}

    def test_filter_by_test_ids(self):
        """Test filtering by specific test IDs."""
        test_cases = self._create_test_cases()
        runner = TestRunner()

        filtered = runner._filter_test_cases(test_cases, test_ids=["test_001", "test_004"])

        assert len(filtered) == 2
        assert {tc.id for tc in filtered} == {"test_001", "test_004"}

    def test_filter_by_test_ids_nonexistent(self):
        """Test filtering by test IDs that don't exist."""
        test_cases = self._create_test_cases()
        runner = TestRunner()

        filtered = runner._filter_test_cases(test_cases, test_ids=["test_999", "test_000"])

        assert len(filtered) == 0

    def test_filter_combined_tags_and_test_ids(self):
        """Test filtering by both tags and test IDs (test IDs take priority)."""
        test_cases = self._create_test_cases()
        runner = TestRunner()

        # First filter by test_id, then by tag (should only match tests in both sets)
        filtered = runner._filter_test_cases(
            test_cases,
            tags=["unit"],
            test_ids=["test_001", "test_002"]  # test_002 doesn't have "unit" tag
        )

        # test_002 is included by test_ids, but doesn't have "unit" tag
        # Since test_ids is applied first, then tags filter, we get test_001 only
        assert len(filtered) == 1
        assert filtered[0].id == "test_001"

    def test_filter_combined_include_and_exclude_tags(self):
        """Test filtering with both include and exclude tags."""
        test_cases = self._create_test_cases()
        runner = TestRunner()

        filtered = runner._filter_test_cases(
            test_cases,
            tags=["unit", "integration"],  # Include these
            exclude_tags=["slow"]  # But exclude slow ones
        )

        # unit: test_001 (fast), test_003 (medium) - both included
        # integration: test_002 (slow) - excluded by exclude_tags
        assert len(filtered) == 2
        assert {tc.id for tc in filtered} == {"test_001", "test_003"}

    def test_filter_no_filters_returns_all(self):
        """Test that no filters returns all test cases."""
        test_cases = self._create_test_cases()
        runner = TestRunner()

        filtered = runner._filter_test_cases(test_cases)

        assert len(filtered) == len(test_cases)

    def test_filter_empty_tag_list(self):
        """Test that empty tag list returns all test cases."""
        test_cases = self._create_test_cases()
        runner = TestRunner()

        filtered = runner._filter_test_cases(test_cases, tags=[])

        assert len(filtered) == len(test_cases)

    def test_filter_tests_without_any_tags(self):
        """Test that tests without tags are only included when no tag filter."""
        test_cases = self._create_test_cases()
        runner = TestRunner()

        # With tag filter, test_005 (no tags) is excluded
        filtered = runner._filter_test_cases(test_cases, tags=["unit"])
        assert "test_005" not in {tc.id for tc in filtered}

        # Without tag filter, test_005 is included
        filtered = runner._filter_test_cases(test_cases)
        assert "test_005" in {tc.id for tc in filtered}

    def test_filter_case_sensitive_tags(self):
        """Test that tag filtering is case-sensitive."""
        test_cases = [
            TestCase(id="test_001", question="Q1", tags=["Unit"]),
            TestCase(id="test_002", question="Q2", tags=["unit"]),
        ]
        runner = TestRunner()

        filtered = runner._filter_test_cases(test_cases, tags=["unit"])

        # Should only match lowercase "unit", not "Unit"
        assert len(filtered) == 1
        assert filtered[0].id == "test_002"
