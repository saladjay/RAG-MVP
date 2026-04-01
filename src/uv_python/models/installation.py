"""
Installation data model.

This module provides the Installation dataclass for representing
Python installations on the local system.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from packaging.version import Version


class ValidationStatus(Enum):
    """Installation validation status."""
    PENDING = "pending"
    VALID = "valid"
    INVALID = "invalid"


@dataclass
class Installation:
    """
    Represents a Python installation on the local system.

    This dataclass captures information about an installed Python version
    including its location, validation status, and metadata.

    Attributes:
        version: Installed Python version (e.g., "3.11.8").
        install_path: Installation directory path.
        installed_at: Installation timestamp.
        platform: Platform identifier (linux, macos, windows).
        architecture: CPU architecture (x86_64, arm64, etc.).
        validation_status: Current validation status.
        binary_path: Path to Python executable.
        last_verified: Last verification timestamp.
        checksum_verified: Whether checksum was verified during installation.
    """

    version: str
    install_path: Path
    installed_at: datetime
    platform: str
    architecture: str
    validation_status: ValidationStatus
    binary_path: Path
    last_verified: Optional[datetime]
    checksum_verified: bool

    def __post_init__(self) -> None:
        """Validate Installation fields after initialization."""
        # Validate version string
        try:
            Version(self.version)
        except ValueError as e:
            raise ValueError(f"Invalid version string '{self.version}': {e}")

        # Validate paths
        if not isinstance(self.install_path, Path):
            self.install_path = Path(self.install_path)
        if not isinstance(self.binary_path, Path):
            self.binary_path = Path(self.binary_path)

        # Validate validation status
        if not isinstance(self.validation_status, ValidationStatus):
            try:
                self.validation_status = ValidationStatus(self.validation_status)
            except ValueError:
                raise ValueError(f"Invalid validation_status '{self.validation_status}'")

        # Validate platform
        valid_platforms = {"linux", "macos", "windows"}
        if self.platform not in valid_platforms:
            raise ValueError(f"Invalid platform '{self.platform}'. Must be one of: {valid_platforms}")

        # Validate installed_at is not in future
        if self.installed_at > datetime.now():
            raise ValueError("installed_at cannot be in the future")

    @property
    def is_valid(self) -> bool:
        """Check if installation is valid."""
        return self.validation_status == ValidationStatus.VALID

    @property
    def is_invalid(self) -> bool:
        """Check if installation is invalid."""
        return self.validation_status == ValidationStatus.INVALID

    @property
    def is_pending(self) -> bool:
        """Check if installation is pending verification."""
        return self.validation_status == ValidationStatus.PENDING

    def mark_valid(self) -> None:
        """Mark installation as valid."""
        self.validation_status = ValidationStatus.VALID
        self.last_verified = datetime.now()

    def mark_invalid(self) -> None:
        """Mark installation as invalid."""
        self.validation_status = ValidationStatus.INVALID
        self.last_verified = datetime.now()

    def mark_pending(self) -> None:
        """Mark installation as pending verification."""
        self.validation_status = ValidationStatus.PENDING

    def to_dict(self) -> dict:
        """
        Convert Installation to dictionary.

        Returns:
            Dictionary representation of this Installation.
        """
        return {
            "version": self.version,
            "install_path": str(self.install_path),
            "installed_at": self.installed_at.isoformat(),
            "platform": self.platform,
            "architecture": self.architecture,
            "validation_status": self.validation_status.value,
            "binary_path": str(self.binary_path),
            "last_verified": self.last_verified.isoformat() if self.last_verified else None,
            "checksum_verified": self.checksum_verified,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Installation":
        """
        Create Installation from dictionary.

        Args:
            data: Dictionary containing Installation data.

        Returns:
            New Installation instance.
        """
        installed_at = data["installed_at"]
        if isinstance(installed_at, str):
            installed_at = datetime.fromisoformat(installed_at.replace("Z", "+00:00"))

        last_verified = data.get("last_verified")
        if last_verified and isinstance(last_verified, str):
            last_verified = datetime.fromisoformat(last_verified.replace("Z", "+00:00"))

        validation_status = data.get("validation_status", "pending")
        if isinstance(validation_status, str):
            validation_status = ValidationStatus(validation_status)

        return cls(
            version=data["version"],
            install_path=Path(data["install_path"]),
            installed_at=installed_at,
            platform=data["platform"],
            architecture=data["architecture"],
            validation_status=validation_status,
            binary_path=Path(data["binary_path"]),
            last_verified=last_verified,
            checksum_verified=data.get("checksum_verified", False),
        )

    def save_metadata(self, path: Optional[Path] = None) -> None:
        """
        Save installation metadata to JSON file.

        Args:
            path: Optional path to metadata file. Defaults to install_path/.uv-python.json.
        """
        if path is None:
            path = self.install_path / ".uv-python.json"

        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_metadata(cls, path: Path) -> Optional["Installation"]:
        """
        Load installation metadata from JSON file.

        Args:
            path: Path to metadata file.

        Returns:
            Installation instance or None if file doesn't exist.
        """
        if not path.exists():
            return None

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return cls.from_dict(data)

    def __str__(self) -> str:
        """Return string representation."""
        status_symbol = {
            ValidationStatus.VALID: "✓",
            ValidationStatus.INVALID: "✗",
            ValidationStatus.PENDING: "⏳",
        }
        return f"{self.version} [{status_symbol.get(self.validation_status, '?')}] {self.platform}/{self.architecture}"

    def __eq__(self, other: object) -> bool:
        """Check equality based on version and install path."""
        if not isinstance(other, Installation):
            return NotImplemented
        return self.version == other.version and self.install_path == other.install_path

    def __hash__(self) -> int:
        """Return hash based on version and install path."""
        return hash((self.version, str(self.install_path)))
