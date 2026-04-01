"""
CSV parser for test files.

Expects CSV with columns: id, question, expected_answer, source_docs, tags
Uses Python's csv module to handle quoted fields and multi-line values.
"""

import csv
from pathlib import Path
from typing import List

from e2e_test.models.test_case import TestCase
from e2e_test.parsers.base import Parser
from e2e_test.core.exceptions import TestFileError


class CSVParser(Parser):
    """Parser for CSV test files.

    Expects a header row with column names, followed by one row per test case.
    """

    # Expected CSV columns
    REQUIRED_COLUMNS = {"id", "question"}
    OPTIONAL_COLUMNS = {"expected_answer", "source_docs", "tags"}

    def parse(self, file_path: Path) -> List[TestCase]:
        """Parse CSV test file.

        Args:
            file_path: Path to CSV test file

        Returns:
            List of test cases

        Raises:
            TestFileError: If file cannot be parsed or validation fails
        """
        try:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
        except FileNotFoundError as e:
            raise TestFileError(
                f"File not found: {file_path}",
                file_path=str(file_path)
            ) from e
        except Exception as e:
            raise TestFileError(
                f"Error reading CSV file: {e}",
                file_path=str(file_path)
            ) from e

        if not rows:
            raise TestFileError(
                "CSV test file is empty (no data rows found)",
                file_path=str(file_path)
            )

        # Validate header
        if not reader.fieldnames:
            raise TestFileError(
                "CSV file has no header row",
                file_path=str(file_path)
            )

        missing_cols = self.REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing_cols:
            raise TestFileError(
                f"CSV missing required columns: {', '.join(missing_cols)}",
                file_path=str(file_path),
                details={"missing_columns": sorted(missing_cols)}
            )

        # Parse each row
        test_cases = []
        for idx, row in enumerate(rows, start=2):  # Row 2 is first data row (after header)
            try:
                test_case = self._parse_row(row, idx, file_path)
                test_cases.append(test_case)
            except Exception as e:
                raise TestFileError(
                    f"Error parsing test case at row {idx}: {e}",
                    file_path=str(file_path),
                    line_number=idx,
                    details={"row": row, "row_number": idx}
                ) from e

        return test_cases

    def _parse_row(self, row: dict, row_number: int, file_path: Path) -> TestCase:
        """Parse a single CSV row into a TestCase.

        Args:
            row: Dictionary of column values
            row_number: Row number (for error reporting)
            file_path: Path to file (for error reporting)

        Returns:
            TestCase instance

        Raises:
            ValueError: If validation fails
        """
        # Extract required fields
        test_id = row.get("id", "").strip()
        question = row.get("question", "").strip()

        if not test_id:
            raise ValueError(f"Row {row_number}: 'id' column is empty")
        if not question:
            raise ValueError(f"Row {row_number}: 'question' column is empty")

        # Extract optional fields
        expected_answer = row.get("expected_answer", "").strip()
        expected_answer = expected_answer if expected_answer else None

        source_docs_str = row.get("source_docs", "").strip()
        source_docs = []
        if source_docs_str:
            # Support both semicolon and comma separators
            for separator in [";", ","]:
                if separator in source_docs_str:
                    source_docs = [doc.strip() for doc in source_docs_str.split(separator) if doc.strip()]
                    break
            else:
                source_docs = [source_docs_str]

        tags_str = row.get("tags", "").strip()
        tags = []
        if tags_str:
            # Support both semicolon and comma separators
            for separator in [";", ","]:
                if separator in tags_str:
                    tags = [tag.strip() for tag in tags_str.split(separator) if tag.strip()]
                    break
            else:
                tags = [tags_str]

        # Build TestCase with Pydantic validation
        return TestCase(
            id=test_id,
            question=question,
            expected_answer=expected_answer,
            source_docs=source_docs,
            tags=tags
        )
