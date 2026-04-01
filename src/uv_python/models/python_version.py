"""
Python version data model.

This module provides the PythonVersion dataclass for representing
available Python releases from python.org and GitHub.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from packaging.version import Version


@dataclass(frozen=True)
class PythonVersion:
    """
    Represents a specific Python release available for installation.

    This dataclass captures information about a Python version including
    its version string, release status, download URLs, and checksums.

    Attributes:
        version: Version string (e.g., "3.11.8").
        major: Major version number (e.g., 3).
        minor: Minor version number (e.g., 11).
        patch: Patch version number (e.g., 8).
        release_status: "stable", "pre-release", or "dev".
        download_url: URL to download binary archive.
        checksum: SHA256 checksum of downloaded file.
        file_size: Size in bytes.
        published_at: Release publication date.
        python_org_id: Optional python.org API ID.
        platforms: List of supported platforms.
    """

    version: str
    major: int
    minor: int
    patch: int
    release_status: str
    download_url: str
    checksum: str
    file_size: int
    published_at: datetime
    python_org_id: Optional[int]
    platforms: List[str]

    def __post_init__(self) -> None:
        """Validate PythonVersion fields after initialization."""
        # Validate version string
        try:
            Version(self.version)
        except ValueError as e:
            raise ValueError(f"Invalid version string '{self.version}': {e}")

        # Validate release status
        valid_statuses = {"stable", "pre-release", "dev"}
        if self.release_status not in valid_statuses:
            raise ValueError(f"Invalid release_status '{self.release_status}'. Must be one of: {valid_statuses}")

        # Validate checksum length (SHA256 = 64 hex chars)
        if len(self.checksum) != 64:
            raise ValueError(f"Invalid checksum length {len(self.checksum)}. Expected 64 for SHA256")

        try:
            int(self.checksum, 16)
        except ValueError:
            raise ValueError("Checksum must be 64 hexadecimal characters")

        # Validate file size
        if self.file_size <= 0:
            raise ValueError(f"Invalid file_size {self.file_size}. Must be positive")

        # Validate URL protocol
        if not self.download_url.startswith("https://"):
            raise ValueError(f"Invalid download_url protocol. Must use HTTPS: {self.download_url}")

        # Validate platform list
        valid_platforms = {"linux", "macos", "windows"}
        for platform in self.platforms:
            if platform not in valid_platforms:
                raise ValueError(f"Invalid platform '{platform}'. Must be one of: {valid_platforms}")

    @property
    def is_stable(self) -> bool:
        """Check if this is a stable release."""
        return self.release_status == "stable"

    @property
    def is_prerelease(self) -> bool:
        """Check if this is a pre-release version."""
        return self.release_status == "pre-release"

    @property
    def is_dev(self) -> bool:
        """Check if this is a dev version."""
        return self.release_status == "dev"

    @property
    def version_tuple(self) -> tuple[int, int, int]:
        """Get version as a tuple for comparison."""
        return (self.major, self.minor, self.patch)

    def __lt__(self, other: "PythonVersion") -> bool:
        """Compare versions for sorting."""
        return self.version_tuple < other.version_tuple

    def __le__(self, other: "PythonVersion") -> bool:
        """Compare versions for sorting."""
        return self.version_tuple <= other.version_tuple

    def __gt__(self, other: "PythonVersion") -> bool:
        """Compare versions for sorting."""
        return self.version_tuple > other.version_tuple

    def __ge__(self, other: "PythonVersion") -> bool:
        """Compare versions for sorting."""
        return self.version_tuple >= other.version_tuple

    def __eq__(self, other: object) -> bool:
        """Check version equality."""
        if not isinstance(other, PythonVersion):
            return NotImplemented
        return self.version == other.version

    def __hash__(self) -> int:
        """Return hash of version string."""
        return hash(self.version)

    def __str__(self) -> str:
        """Return version string representation."""
        return self.version

    def to_dict(self) -> dict:
        """
        Convert PythonVersion to dictionary.

        Returns:
            Dictionary representation of this PythonVersion.
        """
        return {
            "version": self.version,
            "major": self.major,
            "minor": self.minor,
            "patch": self.patch,
            "release_status": self.release_status,
            "download_url": self.download_url,
            "checksum": self.checksum,
            "file_size": self.file_size,
            "published_at": self.published_at.isoformat(),
            "python_org_id": self.python_org_id,
            "platforms": self.platforms,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PythonVersion":
        """
        Create PythonVersion from dictionary.

        Args:
            data: Dictionary containing PythonVersion data.

        Returns:
            New PythonVersion instance.
        """
        published_at = data["published_at"]
        if isinstance(published_at, str):
            published_at = datetime.fromisoformat(published_at.replace("Z", "+00:00"))

        return cls(
            version=data["version"],
            major=data["major"],
            minor=data["minor"],
            patch=data["patch"],
            release_status=data["release_status"],
            download_url=data["download_url"],
            checksum=data["checksum"],
            file_size=data["file_size"],
            published_at=published_at,
            python_org_id=data.get("python_org_id"),
            platforms=data.get("platforms", []),
        )

    @classmethod
    def create(
        cls,
        version: str,
        download_url: str,
        checksum: str,
        file_size: int,
        published_at: datetime,
        release_status: str = "stable",
        python_org_id: Optional[int] = None,
        platforms: Optional[List[str]] = None,
    ) -> "PythonVersion":
        """
        Create a PythonVersion with automatic version parsing.

        Args:
            version: Version string (e.g., "3.11.8").
            download_url: URL to download binary.
            checksum: SHA256 checksum.
            file_size: File size in bytes.
            published_at: Publication date.
            release_status: Release status.
            python_org_id: Optional python.org ID.
            platforms: Supported platforms.

        Returns:
            New PythonVersion instance.
        """
        parsed = Version(version)

        # Determine release status from version string
        if release_status == "stable":
            if parsed.is_prerelease or parsed.is_devrelease:
                release_status = "pre-release"

        # Determine platforms from download URL if not provided
        if platforms is None:
            platforms = []
            url_lower = download_url.lower()
            if "linux" in url_lower:
                platforms.append("linux")
            elif "macos" in url_lower or "osx" in url_lower:
                platforms.append("macos")
            elif "windows" in url_lower or "win" in url_lower:
                platforms.append("windows")

        return cls(
            version=version,
            major=parsed.major,
            minor=parsed.minor,
            parsed.micro,
            release_status=release_status,
            download_url=download_url,
            checksum=checksum,
            file_size=file_size,
            published_at=published_at,
            python_org_id=python_org_id,
            platforms=platforms,
        )
