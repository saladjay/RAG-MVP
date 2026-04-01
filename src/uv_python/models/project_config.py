"""
Project configuration data model.

This module provides the ProjectConfiguration dataclass for representing
project-specific Python version requirements.
"""

import tomllib
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from packaging.specifiers import SpecifierSet
from packaging.version import Version


class ConfigSource(Enum):
    """Project configuration source type."""
    PYTHON_VERSION = "python-version"
    PYPROJECT_TOML = "pyproject.toml"
    NONE = "none"


@dataclass
class ProjectConfiguration:
    """
    Represents project-specific Python version requirements.

    This dataclass captures information about a project's Python version
    requirements, including the configuration source and version range.

    Attributes:
        project_path: Path to project directory.
        config_source: Source of configuration (python-version, pyproject.toml, none).
        required_version: Explicit version requirement (e.g., "3.11.8").
        version_range: Semantic version range (e.g., ">=3.11,<3.12").
        detected_at: When config was detected.
        is_valid: Whether config is valid.
    """

    project_path: Path
    config_source: ConfigSource
    required_version: Optional[str]
    version_range: Optional[SpecifierSet]
    detected_at: datetime
    is_valid: bool

    def __post_init__(self) -> None:
        """Validate ProjectConfiguration fields after initialization."""
        # Validate project path
        if not isinstance(self.project_path, Path):
            self.project_path = Path(self.project_path)

        # Validate config source
        if not isinstance(self.config_source, ConfigSource):
            try:
                self.config_source = ConfigSource(self.config_source)
            except ValueError:
                raise ValueError(f"Invalid config_source '{self.config_source}'")

        # Validate version string if present
        if self.required_version is not None:
            try:
                Version(self.required_version)
            except ValueError:
                # Might be a version range, try that
                try:
                    SpecifierSet(self.required_version)
                except ValueError as e:
                    raise ValueError(f"Invalid required_version '{self.required_version}': {e}")

        # Validate version range if present
        if self.version_range is not None and not isinstance(self.version_range, SpecifierSet):
            if isinstance(self.version_range, str):
                self.version_range = SpecifierSet(self.version_range)
            else:
                raise ValueError("version_range must be a SpecifierSet or string")

    @property
    def has_python_version_file(self) -> bool:
        """Check if .python-version file exists."""
        return self.config_source == ConfigSource.PYTHON_VERSION

    @property
    def has_pyproject_toml(self) -> bool:
        """Check if pyproject.toml is the config source."""
        return self.config_source == ConfigSource.PYPROJECT_TOML

    @property
    def version_specifier(self) -> Optional[str]:
        """Get the version specifier as a string."""
        if self.required_version:
            return self.required_version
        if self.version_range:
            return str(self.version_range)
        return None

    def satisfies_version(self, version: str) -> bool:
        """
        Check if a version satisfies the project requirements.

        Args:
            version: Version string to check.

        Returns:
            True if version satisfies requirements, False otherwise.
        """
        if not self.is_valid:
            return False

        # No requirement means any version is OK
        if self.required_version is None and self.version_range is None:
            return True

        try:
            v = Version(version)
        except ValueError:
            return False

        # Check exact version match
        if self.required_version:
            try:
                required = Version(self.required_version)
                return v == required
            except ValueError:
                # Not an exact version, might be a specifier
                pass

        # Check version range
        if self.version_range:
            return v in self.version_range

        # Try to parse required_version as a specifier
        if self.required_version:
            try:
                spec = SpecifierSet(self.required_version)
                return v in spec
            except ValueError:
                return False

        return True

    @classmethod
    def detect(cls, project_path: Path) -> "ProjectConfiguration":
        """
        Detect project configuration from directory.

        Args:
            project_path: Path to project directory.

        Returns:
            ProjectConfiguration instance.
        """
        detected_at = datetime.now()

        # Check .python-version first (more explicit)
        python_version_file = project_path / ".python-version"
        if python_version_file.exists():
            try:
                version_str = python_version_file.read_text().strip()
                # Validate it's a valid version
                try:
                    Version(version_str)
                    required_version = version_str
                    version_range = None
                    is_valid = True
                except ValueError:
                    # Might be a version range
                    try:
                        version_range = SpecifierSet(version_str)
                        required_version = version_str
                        is_valid = True
                    except ValueError:
                        required_version = version_str
                        version_range = None
                        is_valid = False

                return cls(
                    project_path=project_path,
                    config_source=ConfigSource.PYTHON_VERSION,
                    required_version=required_version,
                    version_range=version_range,
                    detected_at=detected_at,
                    is_valid=is_valid,
                )
            except OSError:
                pass

        # Check pyproject.toml
        pyproject_file = project_path / "pyproject.toml"
        if pyproject_file.exists():
            try:
                with open(pyproject_file, "rb") as f:
                    data = tomllib.load(f)

                requires_python = data.get("project", {}).get("requires-python")
                if requires_python:
                    try:
                        version_range = SpecifierSet(requires_python)
                        return cls(
                            project_path=project_path,
                            config_source=ConfigSource.PYPROJECT_TOML,
                            required_version=requires_python,
                            version_range=version_range,
                            detected_at=detected_at,
                            is_valid=True,
                        )
                    except ValueError:
                        return cls(
                            project_path=project_path,
                            config_source=ConfigSource.PYPROJECT_TOML,
                            required_version=requires_python,
                            version_range=None,
                            detected_at=detected_at,
                            is_valid=False,
                        )
            except (OSError, tomllib.TOMLDecodeError):
                pass

        # No configuration found
        return cls(
            project_path=project_path,
            config_source=ConfigSource.NONE,
            required_version=None,
            version_range=None,
            detected_at=detected_at,
            is_valid=True,
        )

    @classmethod
    def from_python_version_file(cls, project_path: Path, version: str) -> "ProjectConfiguration":
        """
        Create ProjectConfiguration from .python-version file content.

        Args:
            project_path: Path to project directory.
            version: Version string from file.

        Returns:
            ProjectConfiguration instance.
        """
        try:
            Version(version)
            return cls(
                project_path=project_path,
                config_source=ConfigSource.PYTHON_VERSION,
                required_version=version,
                version_range=None,
                detected_at=datetime.now(),
                is_valid=True,
            )
        except ValueError:
            return cls(
                project_path=project_path,
                config_source=ConfigSource.PYTHON_VERSION,
                required_version=version,
                version_range=None,
                detected_at=datetime.now(),
                is_valid=False,
            )

    @classmethod
    def from_pyproject_toml(cls, project_path: Path, requires_python: str) -> "ProjectConfiguration":
        """
        Create ProjectConfiguration from pyproject.toml content.

        Args:
            project_path: Path to project directory.
            requires_python: requires-python value from pyproject.toml.

        Returns:
            ProjectConfiguration instance.
        """
        try:
            version_range = SpecifierSet(requires_python)
            return cls(
                project_path=project_path,
                config_source=ConfigSource.PYPROJECT_TOML,
                required_version=requires_python,
                version_range=version_range,
                detected_at=datetime.now(),
                is_valid=True,
            )
        except ValueError:
            return cls(
                project_path=project_path,
                config_source=ConfigSource.PYPROJECT_TOML,
                required_version=requires_python,
                version_range=None,
                detected_at=datetime.now(),
                is_valid=False,
            )

    def to_dict(self) -> dict:
        """
        Convert ProjectConfiguration to dictionary.

        Returns:
            Dictionary representation.
        """
        return {
            "project_path": str(self.project_path),
            "config_source": self.config_source.value,
            "required_version": self.required_version,
            "version_range": str(self.version_range) if self.version_range else None,
            "detected_at": self.detected_at.isoformat(),
            "is_valid": self.is_valid,
        }

    def __str__(self) -> str:
        """Return string representation."""
        if self.config_source == ConfigSource.NONE:
            return f"No config ({self.project_path})"
        return f"{self.config_source.value}: {self.version_specifier or 'any'} ({self.project_path})"
