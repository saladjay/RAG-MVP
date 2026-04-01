"""
Base parser interface for test file formats.

All parsers must inherit from Parser and implement the parse() method.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from e2e_test.models.test_case import TestCase
from e2e_test.core.exceptions import TestFileError


class Parser(ABC):
    """Abstract base class for test file parsers.

    Each supported format (JSON, CSV, YAML, Markdown) has its own parser
    implementation that inherits from this class.
    """

    @abstractmethod
    def parse(self, file_path: Path) -> List[TestCase]:
        """Parse test file and return list of test cases.

        Args:
            file_path: Path to test file

        Returns:
            List of parsed test cases

        Raises:
            TestFileError: If file cannot be parsed or is invalid
        """
        pass

    def _validate_unique_ids(self, test_cases: List[TestCase]) -> None:
        """Validate that all test IDs are unique within the file.

        Args:
            test_cases: List of parsed test cases

        Raises:
            TestFileError: If duplicate test IDs are found
        """
        seen_ids = set()
        duplicates = set()

        for test_case in test_cases:
            if test_case.id in seen_ids:
                duplicates.add(test_case.id)
            seen_ids.add(test_case.id)

        if duplicates:
            raise TestFileError(
                f"Duplicate test IDs found: {', '.join(sorted(duplicates))}",
                details={"duplicate_ids": sorted(duplicates)}
            )

    def _validate_test_cases(self, test_cases: List[TestCase]) -> None:
        """Validate all test cases pass Pydantic validation.

        Args:
            test_cases: List of parsed test cases

        Raises:
            TestFileError: If any test case fails validation
        """
        # Pydantic validation happens automatically during model creation
        # This method is for any additional validation needed by subclasses
        pass

    def parse_and_validate(self, file_path: Path) -> List[TestCase]:
        """Parse file and perform full validation.

        Args:
            file_path: Path to test file

        Returns:
            List of validated test cases

        Raises:
            TestFileError: If file cannot be parsed or validation fails
        """
        test_cases = self.parse(file_path)
        self._validate_unique_ids(test_cases)
        self._validate_test_cases(test_cases)
        return test_cases
