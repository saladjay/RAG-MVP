"""
File format enums for test file parsing.
"""

from enum import Enum
from pathlib import Path


class FileFormat(str, Enum):
    """Supported test file formats."""

    JSON = "json"
    CSV = "csv"
    YAML = "yaml"
    YML = "yml"
    MARKDOWN = "markdown"
    MD = "md"

    @classmethod
    def from_path(cls, path: Path) -> "FileFormat":
        """Detect file format from file extension.

        Args:
            path: Path to test file

        Returns:
            Detected FileFormat

        Raises:
            ValueError: If extension is not supported
        """
        suffix = path.suffix.lstrip(".").lower()

        mapping = {
            "json": cls.JSON,
            "csv": cls.CSV,
            "yaml": cls.YAML,
            "yml": cls.YML,
            "md": cls.MD,
            "markdown": cls.MARKDOWN,
        }

        if suffix not in mapping:
            raise ValueError(
                f"Unsupported file extension: .{suffix}. "
                f"Supported formats: {', '.join(set(mapping.keys()))}"
            )

        return mapping[suffix]

    @classmethod
    def is_supported(cls, path: Path) -> bool:
        """Check if file format is supported.

        Args:
            path: Path to test file

        Returns:
            True if file extension is supported
        """
        try:
            cls.from_path(path)
            return True
        except ValueError:
            return False

    @property
    def is_json(self) -> bool:
        """Check if format is JSON."""
        return self == self.JSON

    @property
    def is_csv(self) -> bool:
        """Check if format is CSV."""
        return self == self.CSV

    @property
    def is_yaml(self) -> bool:
        """Check if format is YAML."""
        return self in (self.YAML, self.YML)

    @property
    def is_markdown(self) -> bool:
        """Check if format is Markdown."""
        return self in (self.MARKDOWN, self.MD)
