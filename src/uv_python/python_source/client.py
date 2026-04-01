"""
Python source API client for fetching available Python versions.

This module provides integration with python.org API and GitHub releases API
to discover and retrieve Python version information.
"""

import platform
from datetime import datetime
from typing import List, Optional

import requests
from packaging.version import Version

from uv_python.core.exceptions import APIClientError
from uv_python.core.logger import get_logger
from uv_python.models.python_version import PythonVersion


logger = get_logger(__name__)


class PythonSourceClient:
    """
    Client for fetching Python version information from multiple sources.

    This client supports multiple API sources with automatic fallback:
    1. python.org API (primary)
    2. GitHub releases API (fallback)

    Attributes:
        timeout: Request timeout in seconds.
        session: Requests session for connection pooling.
        sources: List of configured API sources.
    """

    PYTHON_ORG_API = "https://www.python.org/api/v2/downloads/"
    GITHUB_API = "https://api.github.com/repos/python/cpython/releases"

    def __init__(self, timeout: int = 5) -> None:
        """
        Initialize PythonSourceClient.

        Args:
            timeout: Request timeout in seconds.
        """
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "uv-python/0.1.0",
        })

    def list_versions(
        self,
        include_prerelease: bool = False,
        platform: Optional[str] = None,
    ) -> List[PythonVersion]:
        """
        List available Python versions from all sources.

        Tries each source in order until one succeeds.

        Args:
            include_prerelease: Include pre-release versions.
            platform: Filter by platform (linux, macos, windows).

        Returns:
            List of available PythonVersion objects.

        Raises:
            APIClientError: If all sources fail.
        """
        sources_to_try = [
            ("python_org", self._fetch_from_python_org),
            ("github", self._fetch_from_github),
        ]

        last_error = None
        for source_name, fetch_func in sources_to_try:
            try:
                logger.debug(f"Fetching versions from {source_name}")
                versions = fetch_func(include_prerelease, platform)
                logger.info(f"Found {len(versions)} versions from {source_name}")
                return versions
            except Exception as e:
                logger.warning(f"Failed to fetch from {source_name}: {e}")
                last_error = e

        # All sources failed
        raise APIClientError(
            "all sources",
            f"Failed after trying {len(sources_to_try)} sources. Last error: {last_error}",
        )

    def _fetch_from_python_org(
        self,
        include_prerelease: bool,
        platform: Optional[str],
    ) -> List[PythonVersion]:
        """
        Fetch versions from python.org API.

        Args:
            include_prerelease: Include pre-release versions.
            platform: Filter by platform.

        Returns:
            List of PythonVersion objects.

        Raises:
            APIClientError: If request fails.
        """
        try:
            response = self.session.get(
                self.PYTHON_ORG_API,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            raise APIClientError("python.org", str(e))

        try:
            data = response.json()
        except ValueError as e:
            raise APIClientError("python.org", f"Invalid JSON response: {e}")

        versions = []
        current_platform = platform or self._get_current_platform()

        for release in data.get("releases", []):
            version_data = self._parse_python_org_release(release, current_platform)

            if version_data is None:
                continue

            # Filter pre-releases if not requested
            if not include_prerelease and version_data["is_prerelease"]:
                continue

            try:
                versions.append(PythonVersion(
                    version=version_data["version"],
                    major=version_data["major"],
                    minor=version_data["minor"],
                    patch=version_data["patch"],
                    release_status="pre-release" if version_data["is_prerelease"] else "stable",
                    download_url=version_data["download_url"],
                    checksum=version_data["checksum"],
                    file_size=version_data["file_size"],
                    published_at=datetime.fromisoformat(
                        version_data["release_date"].replace("Z", "+00:00")
                    ),
                    python_org_id=version_data.get("id"),
                    platforms=version_data["platforms"],
                ))
            except (ValueError, KeyError) as e:
                logger.debug(f"Skipping invalid version data: {e}")
                continue

        return versions

    def _fetch_from_github(
        self,
        include_prerelease: bool,
        platform: Optional[str],
    ) -> List[PythonVersion]:
        """
        Fetch versions from GitHub releases API.

        Args:
            include_prerelease: Include pre-release versions.
            platform: Filter by platform.

        Returns:
            List of PythonVersion objects.

        Raises:
            APIClientError: If request fails.
        """
        try:
            response = self.session.get(
                self.GITHUB_API,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            raise APIClientError("GitHub", str(e))

        try:
            releases = response.json()
        except ValueError as e:
            raise APIClientError("GitHub", f"Invalid JSON response: {e}")

        versions = []
        current_platform = platform or self._get_current_platform()

        for release in releases[:100]:  # Limit to recent releases
            if release.get("draft") or release.get("prerelease", False):
                if not include_prerelease:
                    continue

            tag_name = release.get("tag_name", "")
            if not tag_name.startswith("v"):
                continue

            version_str = tag_name[1:]  # Remove 'v' prefix

            try:
                Version(version_str)  # Validate version
            except ValueError:
                continue

            # Parse release date
            published_at = release.get("published_at", "")
            try:
                published_date = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            except ValueError:
                published_date = datetime.now()

            # Find appropriate asset for current platform
            asset = self._find_github_asset(release.get("assets", []), current_platform)
            if not asset:
                continue

            try:
                parsed_version = Version(version_str)
                versions.append(PythonVersion(
                    version=version_str,
                    major=parsed_version.major,
                    minor=parsed_version.minor,
                    patch=parsed_version.micro,
                    release_status="pre-release" if release.get("prerelease") else "stable",
                    download_url=asset["browser_download_url"],
                    checksum="",  # GitHub doesn't provide checksums
                    file_size=asset.get("size", 0),
                    published_at=published_date,
                    python_org_id=None,
                    platforms=[current_platform],
                ))
            except (ValueError, KeyError) as e:
                logger.debug(f"Skipping invalid version data: {e}")
                continue

        return versions

    def _parse_python_org_release(self, release: dict, platform: str) -> Optional[dict]:
        """
        Parse a python.org API release response.

        Args:
            release: Release data from API.
            platform: Target platform.

        Returns:
            Parsed version data or None if not applicable.
        """
        version_str = release.get("version", "")
        if not version_str:
            return None

        try:
            parsed_version = Version(version_str)
        except ValueError:
            return None

        # Find appropriate file for platform
        file_data = None
        for file_info in release.get("files", []):
            file_platform = self._detect_file_platform(file_info.get("filename", ""))
            if file_platform == platform:
                file_data = file_info
                break

        if not file_data:
            return None

        return {
            "version": version_str,
            "major": parsed_version.major,
            "minor": parsed_version.minor,
            "patch": parsed_version.micro,
            "is_prerelease": parsed_version.is_prerelease or parsed_version.is_devrelease,
            "download_url": file_data.get("url", ""),
            "checksum": file_data.get("sha256", ""),
            "file_size": file_data.get("size", 0),
            "release_date": release.get("release_date", ""),
            "id": release.get("id"),
            "platforms": [platform],
        }

    def _find_github_asset(self, assets: List[dict], platform: str) -> Optional[dict]:
        """
        Find appropriate GitHub asset for platform.

        Args:
            assets: List of GitHub release assets.
            platform: Target platform.

        Returns:
            Matching asset or None.
        """
        platform_keywords = {
            "linux": ["linux", "manylinux"],
            "macos": ["macos", "osx", "darwin"],
            "windows": ["windows", "win", "amd64", "x86_64"],
        }

        keywords = platform_keywords.get(platform, [])

        for asset in assets:
            name = asset.get("name", "").lower()
            if any(kw in name for kw in keywords):
                return asset

        return None

    def _detect_file_platform(self, filename: str) -> Optional[str]:
        """
        Detect platform from filename.

        Args:
            filename: Name of the file.

        Returns:
            Platform string or None.
        """
        filename_lower = filename.lower()

        if "linux" in filename_lower:
            return "linux"
        elif "macos" in filename_lower or "osx" in filename_lower or "darwin" in filename_lower:
            return "macos"
        elif "windows" in filename_lower or "win" in filename_lower:
            return "windows"

        return None

    def _get_current_platform(self) -> str:
        """Get current platform identifier."""
        system = platform.system().lower()

        if system == "linux":
            return "linux"
        elif system == "darwin":
            return "macos"
        elif system == "windows":
            return "windows"

        return "linux"  # Default fallback

    def close(self) -> None:
        """Close the HTTP session."""
        self.session.close()

    def __enter__(self) -> "PythonSourceClient":
        """Context manager entry."""
        return self

    def __exit__(self, *args) -> None:
        """Context manager exit."""
        self.close()
