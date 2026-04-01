"""
Integration tests for similarity calculator edge cases.
"""

import pytest

from e2e_test.comparators.similarity import SimilarityCalculator


class TestSimilarityCalculatorEdgeCases:
    """Test similarity calculator with edge cases."""

    def test_both_empty_strings_returns_0(self):
        """Test that two empty strings return 0.0 (no expected answer to compare)."""
        score = SimilarityCalculator.calculate("", "")
        assert score == 0.0

    def test_one_empty_string_returns_0(self):
        """Test that one empty and one non-empty string returns 0.0."""
        score1 = SimilarityCalculator.calculate("", "some text")
        score2 = SimilarityCalculator.calculate("some text", "")
        assert score1 == 0.0
        assert score2 == 0.0

    def test_empty_expected_returns_0(self):
        """Test that empty expected answer returns 0.0."""
        score = SimilarityCalculator.calculate("actual answer", "")
        assert score == 0.0

    def test_whitespace_normalized(self):
        """Test that whitespace is normalized for comparison."""
        # Extra spaces, tabs, newlines should be normalized
        score = SimilarityCalculator.calculate(
            "hello    world\ttest",
            "hello world test"
        )
        assert score == 1.0

    def test_case_insensitive(self):
        """Test that comparison is case-insensitive."""
        score = SimilarityCalculator.calculate(
            "Hello World",
            "hELLO wORLD"
        )
        assert score == 1.0

    def test_perfect_match(self):
        """Test that identical strings return 1.0."""
        score = SimilarityCalculator.calculate(
            "The capital of France is Paris",
            "The capital of France is Paris"
        )
        assert score == 1.0

    def test_no_match(self):
        """Test that completely different strings return low score."""
        score = SimilarityCalculator.calculate(
            "abcdefg",
            "xyz123"
        )
        assert score < 0.3

    def test_exact_difference(self):
        """Test with strings differing by one character."""
        score = SimilarityCalculator.calculate(
            "hello world",
            "hello worle"  # One character different
        )
        assert score > 0.8

    def test_partial_match(self):
        """Test partial match with common words."""
        score = SimilarityCalculator.calculate(
            "The quick brown fox jumps over the lazy dog",
            "The quick brown cat jumps over the lazy dog"
        )
        # Should be high similarity due to mostly matching content
        assert score > 0.7

    def test_unsupported_method_raises_error(self):
        """Test that unsupported method raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported similarity method"):
            SimilarityCalculator.calculate("text1", "text2", method="unknown")

    def test_levenshtein_method(self):
        """Test explicit levenshtein method."""
        score = SimilarityCalculator.calculate(
            "test",
            "test",
            method="levenshtein"
        )
        assert score == 1.0

    def test_is_passing_with_threshold(self):
        """Test is_passing with various thresholds."""
        # Perfect match
        assert SimilarityCalculator.is_passing(
            "same text", "same text", threshold=0.7
        ) is True

        # Below threshold
        assert SimilarityCalculator.is_passing(
            "different", "content", threshold=0.7
        ) is False

        # Above threshold
        assert SimilarityCalculator.is_passing(
            "hello world", "hello world test", threshold=0.5
        ) is True

    def test_is_passing_no_expected_answer(self):
        """Test is_passing returns True when no expected answer."""
        assert SimilarityCalculator.is_passing(
            "actual answer",
            "",  # No expected answer
            threshold=0.7
        ) is True

        assert SimilarityCalculator.is_passing(
            "actual answer",
            "   ",  # Only whitespace
            threshold=0.7
        ) is True

    def test_unicode_characters(self):
        """Test similarity with unicode characters."""
        score = SimilarityCalculator.calculate(
            "café résumé",
            "café résumé"
        )
        assert score == 1.0

    def test_numbers_and_special_chars(self):
        """Test similarity with numbers and special characters."""
        score = SimilarityCalculator.calculate(
            "Test score: 95.5% (pass)",
            "Test score: 95.5% (pass)"
        )
        assert score == 1.0

    def test_levenshtein_ratio_direct(self):
        """Test levenshtein_ratio method directly."""
        # Identical
        assert SimilarityCalculator.levenshtein_ratio("test", "test") == 1.0

        # Both empty
        assert SimilarityCalculator.levenshtein_ratio("", "") == 1.0

        # One empty
        assert SimilarityCalculator.levenshtein_ratio("test", "") == 0.0
        assert SimilarityCalculator.levenshtein_ratio("", "test") == 0.0

        # Partial match
        score = SimilarityCalculator.levenshtein_ratio("kitten", "sitting")
        assert 0.3 < score < 0.7  # Classic Levenshtein example
