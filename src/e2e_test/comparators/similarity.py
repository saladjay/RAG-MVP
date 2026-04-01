"""
Similarity calculation for comparing actual vs expected answers.

Uses Levenshtein distance via difflib.SequenceMatcher for basic
text similarity. Optional advanced similarity via sentence-transformers.
"""

from difflib import SequenceMatcher
from typing import Optional

from e2e_test.core.logger import get_logger


class SimilarityCalculator:
    """Calculate similarity between two text strings."""

    logger = get_logger()

    @staticmethod
    def levenshtein_ratio(text1: str, text2: str) -> float:
        """Calculate Levenshtein similarity ratio (0-1).

        Uses SequenceMatcher which implements an algorithm similar to
        Levenshtein distance for fuzzy string matching.

        Args:
            text1: First text string
            text2: Second text string

        Returns:
            Similarity score between 0.0 (no match) and 1.0 (perfect match)
        """
        if not text1 and not text2:
            return 1.0
        if not text1 or not text2:
            return 0.0

        # Normalize whitespace and case for comparison
        normalized1 = " ".join(text1.lower().split())
        normalized2 = " ".join(text2.lower().split())

        return SequenceMatcher(None, normalized1, normalized2).ratio()

    @classmethod
    def calculate(
        cls,
        actual: str,
        expected: str,
        method: str = "levenshtein"
    ) -> float:
        """Calculate similarity between actual and expected text.

        Args:
            actual: Actual answer text from RAG Service
            expected: Expected answer text from test case
            method: Similarity method ("levenshtein" or "semantic")

        Returns:
            Similarity score between 0.0 and 1.0

        Raises:
            ValueError: If method is not supported
        """
        if not expected or not expected.strip():
            # No expected answer provided, return neutral score
            return 0.0

        if method == "levenshtein":
            return cls.levenshtein_ratio(actual, expected)
        elif method == "semantic":
            return cls._semantic_similarity(actual, expected)
        else:
            raise ValueError(f"Unsupported similarity method: {method}")

    @staticmethod
    def _semantic_similarity(text1: str, text2: str) -> float:
        """Calculate semantic similarity using sentence-transformers.

        This is an optional advanced method that requires sentence-transformers
        to be installed. Falls back to Levenshtein if not available.

        Args:
            text1: First text string
            text2: Second text string

        Returns:
            Similarity score between 0.0 and 1.0
        """
        try:
            from sentence_transformers import SentenceTransformer
            import torch

            # Load model (cached after first load)
            model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

            # Encode texts
            embeddings = model.encode([text1, text2], convert_to_tensor=True)

            # Calculate cosine similarity
            similarity = torch.nn.functional.cosine_similarity(
                embeddings[0:1],
                embeddings[1:2]
            ).item()

            # Clamp to [0, 1] range
            return max(0.0, min(1.0, similarity))

        except ImportError:
            SimilarityCalculator.logger.warning(
                "sentence-transformers not installed, falling back to Levenshtein"
            )
            return SimilarityCalculator.levenshtein_ratio(text1, text2)

    @classmethod
    def is_passing(
        cls,
        actual: str,
        expected: str,
        threshold: float = 0.7,
        method: str = "levenshtein"
    ) -> bool:
        """Check if similarity meets the passing threshold.

        Args:
            actual: Actual answer text
            expected: Expected answer text
            threshold: Minimum similarity score to pass (0-1)
            method: Similarity calculation method

        Returns:
            True if similarity >= threshold
        """
        if not expected or not expected.strip():
            # No expected answer means we don't judge by similarity
            return True

        similarity = cls.calculate(actual, expected, method=method)
        return similarity >= threshold
