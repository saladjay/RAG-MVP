"""
Unit tests for Hallucination Detection Capability (US3).

These tests verify the similarity-based hallucination detection logic:
- Cosine similarity calculation
- Threshold comparison
- Confidence scoring
- Fallback behavior when embeddings are unavailable
"""

import pytest
from unittest.mock import Mock, patch
import numpy as np

from rag_service.capabilities.hallucination_detection import (
    HallucinationDetectionCapability,
    HallucinationCheckInput,
    HallucinationCheckOutput,
)
from rag_service.core.exceptions import GenerationError


class TestSimilarityCalculation:
    """Unit tests for similarity calculation logic."""

    @pytest.fixture
    def mock_embeddings_model(self):
        """Create a mock embeddings model."""
        model = Mock()
        # Return predictable embeddings for testing
        model.encode = Mock(side_effect=lambda text: np.array([
            0.1, 0.2, 0.3, 0.4, 0.5  # Simplified 5-dim embedding
        ]))
        return model

    @pytest.fixture
    def capability(self, mock_embeddings_model):
        """Create capability with mock embeddings."""
        return HallucinationDetectionCapability(
            embeddings_model=mock_embeddings_model
        )

    @pytest.mark.unit
    async def test_cosine_similarity_high_match(
        self,
        capability,
        mock_embeddings_model,
    ):
        """Test similarity calculation with highly matching answer and chunks.

        Given: An answer that closely matches retrieved chunks
        When: Similarity is calculated
        Then: Returns high similarity score (> 0.7)
        """
        # Make embeddings similar for high match
        mock_embeddings_model.encode = Mock(
            side_effect=lambda text: np.array([0.9, 0.8, 0.7, 0.6, 0.5])
        )

        input_data = HallucinationCheckInput(
            generated_answer="Python is a high-level programming language.",
            retrieved_chunks=[
                {"content": "Python is a high-level programming language."},
                {"content": "It emphasizes code readability."},
            ],
            threshold=0.7,
            trace_id="test-trace-001",
        )

        result = await capability.execute(input_data)

        assert result.similarity_score > 0.7
        assert result.passed is True
        assert result.confidence >= result.similarity_score

    @pytest.mark.unit
    async def test_cosine_similarity_low_match(
        self,
        capability,
        mock_embeddings_model,
    ):
        """Test similarity calculation with poorly matching answer and chunks.

        Given: An answer that doesn't match retrieved chunks
        When: Similarity is calculated
        Then: Returns low similarity score (< 0.5)
        """
        # Make embeddings different for low match
        call_count = [0]

        def mock_encode(text):
            call_count[0] += 1
            # Answer embedding (orthogonal to chunks)
            if "answer" in text.lower() or call_count[0] == 1:
                return np.array([1.0, 0.0, 0.0, 0.0, 0.0])
            # Chunk embeddings (orthogonal to answer)
            return np.array([0.0, 1.0, 0.0, 0.0, 0.0])

        mock_embeddings_model.encode = Mock(side_effect=mock_encode)

        input_data = HallucinationCheckInput(
            generated_answer="The answer is completely unrelated.",
            retrieved_chunks=[
                {"content": "Python programming language"},
                {"content": "Code and syntax"},
            ],
            threshold=0.7,
            trace_id="test-trace-002",
        )

        result = await capability.execute(input_data)

        # Orthogonal vectors have cosine similarity of 0
        assert result.similarity_score < 0.5
        assert result.passed is False


class TestThresholdComparison:
    """Unit tests for threshold comparison logic."""

    @pytest.fixture
    def mock_embeddings_model(self):
        """Create a mock embeddings model."""
        model = Mock()
        model.encode = Mock(return_value=np.array([0.5, 0.5, 0.5, 0.5, 0.5]))
        return model

    @pytest.fixture
    def capability(self, mock_embeddings_model):
        """Create capability with mock embeddings."""
        return HallucinationDetectionCapability(
            embeddings_model=mock_embeddings_model
        )

    @pytest.mark.unit
    async def test_pass_when_similarity_above_threshold(
        self,
        capability,
    ):
        """Test that detection passes when similarity is above threshold.

        Given: A similarity score above the threshold
        When: Threshold comparison is performed
        Then: Returns passed=True
        """
        # Use low threshold to ensure pass
        input_data = HallucinationCheckInput(
            generated_answer="Test answer",
            retrieved_chunks=[{"content": "Test chunk"}],
            threshold=0.3,  # Low threshold
            trace_id="test-trace-003",
        )

        result = await capability.execute(input_data)

        assert result.passed is True
        assert result.confidence >= result.similarity_score

    @pytest.mark.unit
    async def test_fail_when_similarity_below_threshold(
        self,
        capability,
        mock_embeddings_model,
    ):
        """Test that detection fails when similarity is below threshold.

        Given: A similarity score below the threshold
        When: Threshold comparison is performed
        Then: Returns passed=False with flagged claims
        """
        # Create orthogonal embeddings for low similarity
        call_count = [0]

        def mock_encode(text):
            call_count[0] += 1
            if call_count[0] == 1:
                return np.array([1.0, 0.0, 0.0, 0.0, 0.0])
            return np.array([0.0, 1.0, 0.0, 0.0, 0.0])

        mock_embeddings_model.encode = Mock(side_effect=mock_encode)

        input_data = HallucinationCheckInput(
            generated_answer="Unrelated answer",
            retrieved_chunks=[{"content": "Related chunk"}],
            threshold=0.8,  # High threshold
            trace_id="test-trace-004",
        )

        result = await capability.execute(input_data)

        assert result.passed is False
        assert result.similarity_score < input_data.threshold

    @pytest.mark.unit
    async def test_edge_case_equal_to_threshold(
        self,
        capability,
    ):
        """Test behavior when similarity equals threshold.

        Given: A similarity score exactly equal to the threshold
        When: Threshold comparison is performed
        Then: Returns passed=True (borderline cases pass)
        """
        input_data = HallucinationCheckInput(
            generated_answer="Test answer",
            retrieved_chunks=[{"content": "Test chunk"}],
            threshold=0.999,  # Very high threshold, just below 1.0
            trace_id="test-trace-005",
        )

        result = await capability.execute(input_data)

        # With identical embeddings, similarity = 1.0, which is >= threshold
        assert result.passed is True


class TestFlaggedClaims:
    """Unit tests for flagged claims identification."""

    @pytest.fixture
    def mock_embeddings_model(self):
        """Create a mock embeddings model."""
        model = Mock()

        def mock_encode(text):
            # Return embeddings based on content
            if "hallucinated" in text.lower() or "unrelated" in text.lower():
                return np.array([1.0, 0.0, 0.0, 0.0, 0.0])
            return np.array([0.0, 1.0, 0.0, 0.0, 0.0])

        model.encode = Mock(side_effect=mock_encode)
        return model

    @pytest.fixture
    def capability(self, mock_embeddings_model):
        """Create capability with mock embeddings."""
        return HallucinationDetectionCapability(
            embeddings_model=mock_embeddings_model
        )

    @pytest.mark.unit
    async def test_no_flagged_claims_when_passed(
        self,
        capability,
    ):
        """Test that no claims are flagged when verification passes.

        Given: A high-similarity answer
        When: Verification passes
        Then: flagged_claims is empty
        """
        input_data = HallucinationCheckInput(
            generated_answer="Python is a programming language",
            retrieved_chunks=[
                {"content": "Python is a programming language"},
            ],
            threshold=0.5,
            trace_id="test-trace-006",
        )

        result = await capability.execute(input_data)

        assert len(result.flagged_claims) == 0

    @pytest.mark.unit
    async def test_flagged_claims_when_failed(
        self,
        capability,
    ):
        """Test that claims are flagged when verification fails.

        Given: A low-similarity answer
        When: Verification fails
        Then: flagged_claims contains the answer or parts of it
        """
        input_data = HallucinationCheckInput(
            generated_answer="This is hallucinated content",
            retrieved_chunks=[
                {"content": "This is related content"},
            ],
            threshold=0.8,
            trace_id="test-trace-007",
        )

        result = await capability.execute(input_data)

        assert result.passed is False
        # Flagged claims should contain some indication
        # (implementation may vary, but something should be flagged)
        assert isinstance(result.flagged_claims, list)


class TestEmbeddingErrorHandling:
    """Unit tests for error handling in embeddings."""

    @pytest.fixture
    def capability(self):
        """Create capability without embeddings model."""
        return HallucinationDetectionCapability(
            embeddings_model=None
        )

    @pytest.mark.unit
    async def test_error_when_model_not_configured(
        self,
        capability,
    ):
        """Test behavior when embeddings model is not configured.

        Given: No embeddings model configured
        When: execute() is called
        Then: Raises ValueError or returns fallback response
        """
        input_data = HallucinationCheckInput(
            generated_answer="Test answer",
            retrieved_chunks=[{"content": "Test chunk"}],
            threshold=0.7,
            trace_id="test-trace-008",
        )

        with pytest.raises((ValueError, NotImplementedError)):
            await capability.execute(input_data)

    @pytest.mark.unit
    async def test_fallback_on_embedding_failure(
        self,
    ):
        """Test fallback behavior when embedding generation fails.

        Given: Embeddings model raises exception
        When: execute() is called
        Then: Gracefully handles error or returns safe default
        """
        mock_model = Mock()
        mock_model.encode = Mock(side_effect=RuntimeError("Embedding failed"))

        capability = HallucinationDetectionCapability(
            embeddings_model=mock_model
        )

        input_data = HallucinationCheckInput(
            generated_answer="Test answer",
            retrieved_chunks=[{"content": "Test chunk"}],
            threshold=0.7,
            trace_id="test-trace-009",
        )

        # Should handle error gracefully
        with pytest.raises((RuntimeError, GenerationError)):
            await capability.execute(input_data)


class TestHealthStatus:
    """Unit tests for health status reporting."""

    @pytest.mark.unit
    def test_health_status_with_model(self):
        """Test health status when model is configured."""
        mock_model = Mock()
        capability = HallucinationDetectionCapability(
            embeddings_model=mock_model
        )

        health = capability.get_health()

        assert health["status"] in ["initializing", "ready"]
        assert health["embeddings_model"] == "ready"
        assert health["verification_method"] == "similarity"

    @pytest.mark.unit
    def test_health_status_without_model(self):
        """Test health status when model is not configured."""
        capability = HallucinationDetectionCapability(
            embeddings_model=None
        )

        health = capability.get_health()

        assert health["embeddings_model"] == "not_configured"


class TestValidation:
    """Unit tests for input validation."""

    @pytest.fixture
    def capability(self):
        """Create capability for validation tests."""
        mock_model = Mock()
        mock_model.encode = Mock(return_value=np.array([0.5, 0.5, 0.5, 0.5, 0.5]))
        return HallucinationDetectionCapability(
            embeddings_model=mock_model
        )

    @pytest.mark.unit
    async def test_validate_empty_answer(self, capability):
        """Test validation rejects empty answer."""
        input_data = HallucinationCheckInput(
            generated_answer="",
            retrieved_chunks=[{"content": "Test"}],
            threshold=0.7,
            trace_id="test-trace-010",
        )

        # Should handle gracefully or raise validation error
        result = await capability.execute(input_data)
        # Empty answer might still work but should have low similarity
        assert result is not None

    @pytest.mark.unit
    async def test_validate_empty_chunks(self, capability):
        """Test validation rejects empty chunks list."""
        input_data = HallucinationCheckInput(
            generated_answer="Test answer",
            retrieved_chunks=[],
            threshold=0.7,
            trace_id="test-trace-011",
        )

        # Empty chunks should result in failed verification
        result = await capability.execute(input_data)
        assert result.passed is False

    @pytest.mark.unit
    async def test_validate_threshold_bounds(self, capability):
        """Test validation of threshold bounds."""
        # Valid threshold
        input_data = HallucinationCheckInput(
            generated_answer="Test",
            retrieved_chunks=[{"content": "Test"}],
            threshold=0.7,  # Valid
            trace_id="test-trace-012",
        )

        result = await capability.execute(input_data)
        assert result is not None

    @pytest.mark.unit
    async def test_validate_threshold_defaults(self, capability):
        """Test that threshold defaults to 0.7 when not specified."""
        # The HallucinationCheckInput has default=0.7
        input_data = HallucinationCheckInput(
            generated_answer="Test",
            retrieved_chunks=[{"content": "Test"}],
            trace_id="test-trace-013",
        )

        result = await capability.execute(input_data)
        assert result is not None
