"""
YAML parser for test files.

Uses pyyaml to parse YAML files containing test case lists.
Supports both list format and dict with 'tests' key.
"""

import yaml
from pathlib import Path
from typing import Any, Dict, List

from e2e_test.models.test_case import TestCase
from e2e_test.parsers.base import Parser
from e2e_test.core.exceptions import TestFileError


class YAMLParser(Parser):
    """Parser for YAML test files.

    Expects a list of test case objects, or a dict with 'tests' key containing the list.
    """

    def parse(self, file_path: Path) -> List[TestCase]:
        """Parse YAML test file.

        Args:
            file_path: Path to YAML test file

        Returns:
            List of test cases

        Raises:
            TestFileError: If file cannot be parsed or validation fails
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise TestFileError(
                f"Invalid YAML format: {e}",
                file_path=str(file_path),
                details={"yaml_error": str(e)}
            ) from e
        except FileNotFoundError as e:
            raise TestFileError(
                f"File not found: {file_path}",
                file_path=str(file_path)
            ) from e
        except Exception as e:
            raise TestFileError(
                f"Error reading YAML file: {e}",
                file_path=str(file_path)
            ) from e

        if data is None:
            raise TestFileError(
                "YAML file is empty",
                file_path=str(file_path)
            )

        # Support both list format and dict with 'tests' key
        if isinstance(data, dict):
            if "tests" in data:
                test_data = data["tests"]
            else:
                raise TestFileError(
                    "YAML root is a dict but missing 'tests' key",
                    file_path=str(file_path),
                    details={"available_keys": list(data.keys())}
                )
        elif isinstance(data, list):
            test_data = data
        else:
            raise TestFileError(
                f"YAML root must be a list or dict with 'tests' key, got {type(data).__name__}",
                file_path=str(file_path)
            )

        if not test_data:
            raise TestFileError(
                "YAML test file contains no test cases",
                file_path=str(file_path)
            )

        # Parse each test case
        test_cases = []
        for idx, item in enumerate(test_data, start=1):
            try:
                test_case = self._parse_test_case(item, idx, file_path)
                test_cases.append(test_case)
            except Exception as e:
                raise TestFileError(
                    f"Error parsing test case at index {idx}: {e}",
                    file_path=str(file_path),
                    details={"index": idx, "raw_data": item}
                ) from e

        return test_cases

    def _parse_test_case(self, data: Any, index: int, file_path: Path) -> TestCase:
        """Parse a single test case from YAML data.

        Args:
            data: Dictionary containing test case data
            index: Index in the array (for error reporting)
            file_path: Path to file (for error reporting)

        Returns:
            TestCase instance

        Raises:
            ValueError: If validation fails
        """
        if not isinstance(data, dict):
            raise ValueError(f"Test case at index {index} must be an object/dict, got {type(data).__name__}")

        # Validate required fields
        if "id" not in data:
            raise ValueError(f"Test case at index {index} missing required field: 'id'")
        if "question" not in data:
            raise ValueError(f"Test case at index {index} missing required field: 'question'")

        # Extract fields with defaults
        test_id = str(data["id"])
        question = str(data["question"])
        expected_answer = data.get("expected_answer")
        source_docs = data.get("source_docs", [])
        tags = data.get("tags", [])
        metadata = data.get("metadata", {})

        # Ensure lists
        if not isinstance(source_docs, list):
            source_docs = [source_docs]
        if not isinstance(tags, list):
            tags = [tags]

        # Build TestCase with Pydantic validation
        try:
            return TestCase(
                id=test_id,
                question=question,
                expected_answer=expected_answer,
                source_docs=source_docs,
                tags=tags,
                metadata=metadata
            )
        except Exception as e:
            raise ValueError(f"Test case '{test_id}' validation failed: {e}") from e
