"""
Source document validation for RAG retrieval accuracy.

Compares expected document IDs against actual retrieved document IDs.
"""

from typing import List, Set

from e2e_test.models.test_result import SourceDocsMatch


class SourceDocsValidator:
    """Validate source document retrieval accuracy."""

    @staticmethod
    def validate(
        expected_docs: List[str],
        actual_docs: List[str]
    ) -> tuple[bool, SourceDocsMatch]:
        """Validate if expected documents were retrieved.

        Args:
            expected_docs: List of expected document IDs from test case
            actual_docs: List of retrieved document IDs from RAG response

        Returns:
            Tuple of (is_match, match_type):
            - is_match: True if validation passes
            - match_type: Type of match (exact, superset, subset, none, n/a)
        """
        # No expected docs means validation is not applicable
        if not expected_docs:
            return True, SourceDocsMatch.NOT_APPLICABLE

        expected_set: Set[str] = set(expected_docs)
        actual_set: Set[str] = set(actual_docs)

        # Exact match
        if expected_set == actual_set:
            return True, SourceDocsMatch.EXACT

        # Superset match (actual contains all expected plus more)
        if expected_set.issubset(actual_set):
            return True, SourceDocsMatch.SUPERSET

        # Subset match (actual contains some but not all expected)
        if expected_set.intersection(actual_set):
            return False, SourceDocsMatch.SUBSET

        # No overlap at all
        return False, SourceDocsMatch.NONE

    @staticmethod
    def is_passing(
        expected_docs: List[str],
        actual_docs: List[str],
        require_exact: bool = False
    ) -> bool:
        """Check if source document validation passes.

        Args:
            expected_docs: List of expected document IDs
            actual_docs: List of retrieved document IDs
            require_exact: If True, require exact match (not superset)

        Returns:
            True if validation passes
        """
        is_match, match_type = SourceDocsValidator.validate(expected_docs, actual_docs)

        if match_type == SourceDocsMatch.NOT_APPLICABLE:
            return True

        if require_exact:
            return match_type == SourceDocsMatch.EXACT

        return is_match

    @staticmethod
    def get_missing_docs(
        expected_docs: List[str],
        actual_docs: List[str]
    ) -> List[str]:
        """Get expected documents that were not retrieved.

        Args:
            expected_docs: List of expected document IDs
            actual_docs: List of retrieved document IDs

        Returns:
            List of missing document IDs
        """
        expected_set = set(expected_docs)
        actual_set = set(actual_docs)
        return sorted(expected_set - actual_set)

    @staticmethod
    def get_extra_docs(
        expected_docs: List[str],
        actual_docs: List[str]
    ) -> List[str]:
        """Get retrieved documents that were not expected.

        Args:
            expected_docs: List of expected document IDs
            actual_docs: List of retrieved document IDs

        Returns:
            List of extra document IDs
        """
        expected_set = set(expected_docs)
        actual_set = set(actual_docs)
        return sorted(actual_set - expected_set)
