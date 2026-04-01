"""
Markdown parser for test files.

Extracts test cases from markdown files by parsing YAML code blocks.
Supports fenced code blocks with yaml syntax.
"""

import re
from pathlib import Path
from typing import Any, Dict, List

import yaml

from e2e_test.models.test_case import TestCase
from e2e_test.parsers.base import Parser
from e2e_test.core.exceptions import TestFileError


class MDParser(Parser):
    """Parser for Markdown test files.

    Extracts test cases from YAML code blocks within the markdown.
    Each code block should contain YAML test case definitions.
    """

    # Pattern to match fenced code blocks with yaml syntax
    # Matches opening ```yaml and closing ``` fences
    YAML_BLOCK_PATTERN = re.compile(
        r'```yaml\s*\n([\s\S]*?)\n```',
        re.DOTALL | re.MULTILINE
    )

    # Alternative pattern for indented code blocks
    INDENTED_BLOCK_PATTERN = re.compile(
        r'(?:^|\n)(\t+| {4})(?:```)?(?:yaml)?\s*\n((?:[^\n]*\n)+?)(?=\n(?:\1|$))',
        re.MULTILINE
    )

    def parse(self, file_path: Path) -> List[TestCase]:
        """Parse Markdown test file.

        Args:
            file_path: Path to Markdown test file

        Returns:
            List of test cases

        Raises:
            TestFileError: If file cannot be parsed or validation fails
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except FileNotFoundError as e:
            raise TestFileError(
                f"File not found: {file_path}",
                file_path=str(file_path)
            ) from e
        except Exception as e:
            raise TestFileError(
                f"Error reading Markdown file: {e}",
                file_path=str(file_path)
            ) from e

        # Extract YAML code blocks
        yaml_blocks = self._extract_yaml_blocks(content, file_path)

        if not yaml_blocks:
            raise TestFileError(
                "No YAML code blocks found in markdown file",
                file_path=str(file_path),
                hint="Use ```yaml fenced code blocks for test cases"
            )

        # Parse each YAML block
        test_cases = []
        for idx, (block_content, block_start_line) in enumerate(yaml_blocks, start=1):
            try:
                # Parse YAML content
                data = yaml.safe_load(block_content)

                if not data:
                    continue  # Skip empty blocks

                # Handle both list and single test case
                if isinstance(data, list):
                    items = data
                elif isinstance(data, dict):
                    # Check if it has a 'tests' key
                    if "tests" in data:
                        items = data["tests"]
                    else:
                        # Single test case as dict
                        items = [data]
                else:
                    raise ValueError(
                        f"YAML block must be a list, dict with 'tests', or single test case, got {type(data).__name__}"
                    )

                # Parse each test case in the block
                for item in items:
                    if not isinstance(item, dict):
                        raise ValueError(f"Test case must be a dict, got {type(item).__name__}")

                    test_case = self._parse_test_case(item, idx, block_start_line, file_path)
                    test_cases.append(test_case)

            except yaml.YAMLError as e:
                raise TestFileError(
                    f"Invalid YAML in code block at position {idx}: {e}",
                    file_path=str(file_path),
                    details={"block_number": idx, "yaml_error": str(e)}
                ) from e
            except Exception as e:
                raise TestFileError(
                    f"Error parsing test case in block at position {idx}: {e}",
                    file_path=str(file_path),
                    details={"block_number": idx}
                ) from e

        return test_cases

    def _extract_yaml_blocks(self, content: str, file_path: Path) -> List[tuple[str, int]]:
        """Extract YAML code blocks from markdown content.

        Args:
            content: Markdown file content
            file_path: Path to file (for error reporting)

        Returns:
            List of (block_content, start_line_number) tuples
        """
        # Use line-by-line parsing for more reliable block extraction
        blocks = []
        lines = content.split('\n')
        current_block = []
        block_start = 0
        in_yaml_block = False

        for line_num, line in enumerate(lines, start=1):
            stripped = line.strip()

            # Check for code block start (```yaml)
            if stripped.startswith("```yaml") and not in_yaml_block:
                in_yaml_block = True
                block_start = line_num
                continue

            # Check for code block end (just ```, not ```yaml)
            if stripped.startswith("```") and in_yaml_block:
                in_yaml_block = False
                if current_block:
                    block_content = "\n".join(current_block).strip()
                    # Only add non-empty blocks
                    if block_content:
                        blocks.append((block_content, block_start))
                    current_block = []
                continue

            # Collect block content
            if in_yaml_block:
                current_block.append(line)

        return blocks

    def _parse_test_case(self, data: Dict[str, Any], block_index: int, block_start: int, file_path: Path) -> TestCase:
        """Parse a single test case from YAML data.

        Args:
            data: Dictionary containing test case data
            block_index: Block index (for error reporting)
            block_start: Starting line number of the block
            file_path: Path to file (for error reporting)

        Returns:
            TestCase instance

        Raises:
            ValueError: If validation fails
        """
        # Validate required fields
        if "id" not in data:
            raise ValueError(f"Test case in block {block_index} (line ~{block_start}) missing required field: 'id'")
        if "question" not in data:
            raise ValueError(f"Test case in block {block_index} (line ~{block_start}) missing required field: 'question'")

        # Extract fields
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
            raise ValueError(f"Test case '{test_id}' in block {block_index} (line ~{block_start}) validation failed: {e}") from e
