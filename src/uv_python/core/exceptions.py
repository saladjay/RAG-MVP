"""
Custom exception classes for uv_python.

This module defines the exception hierarchy used throughout the application.
All exceptions inherit from UVPythonError for consistent error handling.
"""

from typing import Optional


class UVPythonError(Exception):
    """
    Base exception for all uv_python errors.

    This exception should be used as the base class for all custom exceptions
    in the application, enabling consistent error handling and user-friendly
    error messages.

    Attributes:
        message: Human-readable error message.
        suggestion: Optional suggestion for resolving the error.
        error_code: Optional error code for documentation lookup.
    """

    def __init__(
        self,
        message: str,
        suggestion: Optional[str] = None,
        error_code: Optional[str] = None,
    ) -> None:
        """
        Initialize a UVPythonError.

        Args:
            message: Human-readable error message.
            suggestion: Optional suggestion for resolving the error.
            error_code: Optional error code for documentation lookup.
        """
        super().__init__(message)
        self.message = message
        self.suggestion = suggestion
        self.error_code = error_code

    def __str__(self) -> str:
        """Return formatted error message."""
        parts = [f"Error: {self.message}"]
        if self.suggestion:
            parts.append(f"\nSuggestion: {self.suggestion}")
        if self.error_code:
            parts.append(f"\nError Code: {self.error_code}")
        return "".join(parts)


class VersionNotFoundError(UVPythonError):
    """
    Exception raised when a requested Python version cannot be found.

    This occurs when the user requests a version that doesn't exist in
    the available Python releases.
    """

    def __init__(self, version: str, available_range: Optional[str] = None) -> None:
        """
        Initialize VersionNotFoundError.

        Args:
            version: The requested version that was not found.
            available_range: Optional description of available versions.
        """
        message = f"Python version '{version}' not found"
        suggestion = "Run 'uv python list' to see available versions"
        if available_range:
            message += f" (Available: {available_range})"
        super().__init__(message, suggestion, "ERR-001")


class DownloadFailedError(UVPythonError):
    """
    Exception raised when a Python download fails.

    This occurs when downloading a Python version fails after all
    retry attempts.
    """

    def __init__(
        self,
        version: str,
        reason: str,
        attempts: int,
    ) -> None:
        """
        Initialize DownloadFailedError.

        Args:
            version: The Python version that failed to download.
            reason: The reason for the download failure.
            attempts: Number of download attempts made.
        """
        message = f"Failed to download Python {version} after {attempts} attempts: {reason}"
        suggestion = "Check your internet connection and try again"
        super().__init__(message, suggestion, "ERR-002")


class ChecksumMismatchError(UVPythonError):
    """
    Exception raised when downloaded file checksum doesn't match expected.

    This indicates either file corruption or tampering.
    """

    def __init__(
        self,
        version: str,
        expected: Optional[str] = None,
        actual: Optional[str] = None,
    ) -> None:
        """
        Initialize ChecksumMismatchError.

        Args:
            version: The Python version with checksum mismatch.
            expected: Expected checksum value.
            actual: Actual checksum value computed.
        """
        message = f"Checksum mismatch for Python {version}"
        if expected and actual:
            message += f" (expected: {expected[:16]}..., got: {actual[:16]}...)"
        suggestion = "Reinstall with --force to re-download"
        super().__init__(message, suggestion, "ERR-003")


class InstallationError(UVPythonError):
    """
    Exception raised when Python installation fails.

    This occurs when extracting, setting up, or verifying a Python
    installation fails.
    """

    def __init__(self, version: str, reason: str) -> None:
        """
        Initialize InstallationError.

        Args:
            version: The Python version that failed to install.
            reason: The reason for the installation failure.
        """
        message = f"Failed to install Python {version}: {reason}"
        suggestion = "Check disk space and permissions, then retry"
        super().__init__(message, suggestion, "ERR-004")


class ConfigurationError(UVPythonError):
    """
    Exception raised when configuration is invalid or cannot be loaded.

    This occurs when configuration files are missing, malformed, or
    contain invalid values.
    """

    def __init__(self, reason: str) -> None:
        """
        Initialize ConfigurationError.

        Args:
            reason: The reason for the configuration error.
        """
        message = f"Configuration error: {reason}"
        suggestion = "Check your config file at ~/.config/uv-python/config.toml"
        super().__init__(message, suggestion, "ERR-005")


class VersionResolutionError(UVPythonError):
    """
    Exception raised when a version requirement cannot be resolved.

    This occurs when semantic version matching fails to find a
    compatible Python version.
    """

    def __init__(self, requirement: str, available_count: int = 0) -> None:
        """
        Initialize VersionResolutionError.

        Args:
            requirement: The version requirement that couldn't be resolved.
            available_count: Number of available versions checked.
        """
        message = f"Cannot resolve version requirement: '{requirement}'"
        if available_count > 0:
            message += f" (checked {available_count} available versions)"
        suggestion = "Run 'uv python list' to see available versions"
        super().__init__(message, suggestion, "ERR-006")


class VerificationError(UVPythonError):
    """
    Exception raised when Python installation verification fails.

    This occurs when a previously installed Python version is found
    to be corrupted or non-functional.
    """

    def __init__(self, version: str, reason: str) -> None:
        """
        Initialize VerificationError.

        Args:
            version: The Python version that failed verification.
            reason: The reason for verification failure.
        """
        message = f"Python {version} verification failed: {reason}"
        suggestion = "Reinstall with --force to fix the installation"
        super().__init__(message, suggestion, "ERR-007")


class APIClientError(UVPythonError):
    """
    Exception raised when API client requests fail.

    This occurs when python.org or GitHub API requests fail due to
    network issues or API errors.
    """

    def __init__(self, source: str, reason: str) -> None:
        """
        Initialize APIClientError.

        Args:
            source: The API source that failed (e.g., "python.org", "GitHub").
            reason: The reason for the API failure.
        """
        message = f"API request to {source} failed: {reason}"
        suggestion = "Check your internet connection and try again later"
        super().__init__(message, suggestion, "ERR-008")


class ProjectDetectionError(UVPythonError):
    """
    Exception raised when project configuration cannot be detected.

    This occurs when .python-version or pyproject.toml files are
    malformed or missing.
    """

    def __init__(self, path: str, reason: str) -> None:
        """
        Initialize ProjectDetectionError.

        Args:
            path: The project path where detection failed.
            reason: The reason for detection failure.
        """
        message = f"Failed to detect project configuration at {path}: {reason}"
        suggestion = "Ensure .python-version or pyproject.toml exists and is valid"
        super().__init__(message, suggestion, "ERR-009")


class UninstallationError(UVPythonError):
    """
    Exception raised when Python uninstallation fails.

    This occurs when removing a Python installation fails due to
    permissions or file system issues.
    """

    def __init__(self, version: str, reason: str) -> None:
        """
        Initialize UninstallationError.

        Args:
            version: The Python version that failed to uninstall.
            reason: The reason for uninstallation failure.
        """
        message = f"Failed to uninstall Python {version}: {reason}"
        suggestion = "Check file permissions and ensure no processes are using this Python"
        super().__init__(message, suggestion, "ERR-010")
