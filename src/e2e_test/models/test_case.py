"""
Test case model representing a single E2E test definition.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class TestCase(BaseModel):
    """A single test case definition.

    Contains the question to ask RAG Service, optional expected answer,
    and optional source document references for validation.
    """

    id: str = Field(..., description="Unique test identifier (Python variable name)")
    question: str = Field(..., min_length=1, description="Question to submit to RAG Service")
    expected_answer: Optional[str] = Field(None, max_length=10000, description="Expected answer for similarity comparison")
    source_docs: List[str] = Field(default_factory=list, description="Expected document IDs to be retrieved")
    tags: List[str] = Field(default_factory=list, description="Tags for filtering and grouping")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional test metadata")

    @field_validator("id")
    @classmethod
    def id_must_be_valid(cls, v: str) -> str:
        """Validate test ID follows Python variable naming rules.

        Args:
            v: Test ID value

        Returns:
            Validated test ID

        Raises:
            ValueError: If ID is invalid
        """
        if not v or v.isspace():
            raise ValueError("Test ID cannot be empty")

        # Check Python variable name pattern
        if not (v[0].isalpha() or v[0] == "_"):
            raise ValueError(f"Test ID must start with letter or underscore: {v}")

        for char in v:
            if not (char.isalnum() or char == "_"):
                raise ValueError(f"Test ID must contain only letters, numbers, and underscores: {v}")

        return v

    @field_validator("question")
    @classmethod
    def question_must_not_be_empty(cls, v: str) -> str:
        """Validate question is not just whitespace.

        Args:
            v: Question value

        Returns:
            Validated question

        Raises:
            ValueError: If question is empty
        """
        if not v or v.isspace():
            raise ValueError("Question cannot be empty")
        return v.strip()

    @property
    def has_expected_answer(self) -> bool:
        """Check if test has an expected answer defined.

        Returns:
            True if expected_answer is set and not empty
        """
        return bool(self.expected_answer and self.expected_answer.strip())

    @property
    def has_source_docs(self) -> bool:
        """Check if test has source document expectations.

        Returns:
            True if source_docs list is not empty
        """
        return len(self.source_docs) > 0

    @property
    def is_basic(self) -> bool:
        """Check if this is a basic test (no expectations).

        Returns:
            True if test has no expected_answer or source_docs
        """
        return not (self.has_expected_answer or self.has_source_docs)
