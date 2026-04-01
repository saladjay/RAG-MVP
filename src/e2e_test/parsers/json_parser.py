"""
JSON parser for test files.

Expects a JSON array of test case objects with fields:
id, question, expected_answer (optional), source_docs (optional), tags (optional), metadata (optional)
"""

import json
from pathlib import Path
from typing import Any, Dict, List

from e2e_test.models.test_case import TestCase
from e2e_test.parsers.base import Parser
from e2e_test.core.exceptions import TestFileError


class JSONParser(Parser):
    """Parser for JSON test files.

    Expects a JSON array of test case objects at the root level.
    """

    def parse(self, file_path: Path) -> List[TestCase]:
        """Parse JSON test file.

        Args:
            file_path: Path to JSON test file

        Returns:
            List of test cases

        Raises:
            TestFileError: If file cannot be parsed or validation fails
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise TestFileError(
                f"Invalid JSON format: {e.msg}",
                file_path=str(file_path),
                line_number=e.lineno,
                details={"column": e.colno, "position": e.pos}
            ) from e
        except FileNotFoundError as e:
            raise TestFileError(
                f"File not found: {file_path}",
                file_path=str(file_path)
            ) from e
        except Exception as e:
            raise TestFileError(
                f"Error reading file: {e}",
                file_path=str(file_path)
            ) from e

        # Validate root is a list
        if not isinstance(data, list):
            raise TestFileError(
                f"JSON root must be an array of test cases, got {type(data).__name__}",
                file_path=str(file_path)
            )

        if not data:
            raise TestFileError(
                "JSON test file is empty (no test cases found)",
                file_path=str(file_path)
            )

        # Parse each test case
        test_cases = []
        for idx, item in enumerate(data, start=1):
            try:
                test_case = self._parse_test_case(item, idx)
                test_cases.append(test_case)
            except Exception as e:
                raise TestFileError(
                    f"Error parsing test case at index {idx}: {e}",
                    file_path=str(file_path),
                    line_number=idx,
                    details={"index": idx, "raw_data": item}
                ) from e

        return test_cases

    def _parse_test_case(self, data: Dict[str, Any], index: int) -> TestCase:
        """Parse a single test case from JSON data.

        Args:
            data: Dictionary containing test case data
            index: Index in the array (for error reporting)

        Returns:
            TestCase instance

        Raises:
            ValueError: If required fields are missing or invalid
        """
        if not isinstance(data, dict):
            raise ValueError(f"Test case at index {index} must be an object, got {type(data).__name__}")

        # Validate required fields
        if "id" not in data:
            raise ValueError(f"Test case at index {index} missing required field: 'id'")
        if "question" not in data:
            raise ValueError(f"Test case at index {index} missing required field: 'question'")

        # Build test case with Pydantic validation
        try:
            return TestCase(
                id=str(data["id"]),
                question=str(data["question"]),
                expected_answer=data.get("expected_answer"),
                source_docs=data.get("source_docs", []),
                tags=data.get("tags", []),
                metadata=data.get("metadata", {})
            )
        except Exception as e:
            raise ValueError(f"Test case '{data.get('id', f'index_{index}')}' validation failed: {e}") from e
