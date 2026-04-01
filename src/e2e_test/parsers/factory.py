"""
Parser factory for automatic format detection and instantiation.

Detects file format based on extension and returns the appropriate parser.
"""

from pathlib import Path
from typing import Optional

from e2e_test.models.file_format import FileFormat
from e2e_test.parsers.base import Parser
from e2e_test.parsers.json_parser import JSONParser
from e2e_test.parsers.csv_parser import CSVParser
from e2e_test.parsers.yaml_parser import YAMLParser
from e2e_test.parsers.md_parser import MDParser
from e2e_test.core.exceptions import TestFileError


class ParserFactory:
    """Factory for creating appropriate parsers based on file format."""

    # Mapping of file formats to parser classes
    PARSERS = {
        FileFormat.JSON: JSONParser,
        FileFormat.YAML: YAMLParser,
        FileFormat.YML: YAMLParser,
        FileFormat.CSV: CSVParser,
        FileFormat.MARKDOWN: MDParser,
        FileFormat.MD: MDParser,
    }

    @classmethod
    def create_parser(cls, file_path: Path) -> Parser:
        """Create appropriate parser for the given file.

        Args:
            file_path: Path to test file

        Returns:
            Parser instance for the file's format

        Raises:
            TestFileError: If file format is not supported
        """
        try:
            file_format = FileFormat.from_path(file_path)
        except ValueError as e:
            raise TestFileError(
                str(e),
                file_path=str(file_path)
            ) from e

        parser_class = cls.PARSERS.get(file_format)
        if parser_class is None:
            raise TestFileError(
                f"No parser available for format: {file_format}",
                file_path=str(file_path),
                details={"format": str(file_format)}
            )

        return parser_class()

    @classmethod
    def get_supported_extensions(cls) -> list[str]:
        """Get list of supported file extensions.

        Returns:
            List of supported file extensions (with dots)
        """
        return [".json", ".csv", ".yaml", ".yml", ".md", ".markdown"]

    @classmethod
    def is_supported(cls, file_path: Path) -> bool:
        """Check if file format is supported.

        Args:
            file_path: Path to check

        Returns:
            True if format is supported, False otherwise
        """
        return FileFormat.is_supported(file_path)
