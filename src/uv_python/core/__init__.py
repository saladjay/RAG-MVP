"""
Core utilities for uv_python.

This module provides foundational components including exception handling,
logging configuration, and shared utilities.
"""

from uv_python.core.exceptions import (
    UVPythonError,
    VersionNotFoundError,
    DownloadFailedError,
    ChecksumMismatchError,
    InstallationError,
    ConfigurationError,
)

__all__ = [
    "UVPythonError",
    "VersionNotFoundError",
    "DownloadFailedError",
    "ChecksumMismatchError",
    "InstallationError",
    "ConfigurationError",
]
