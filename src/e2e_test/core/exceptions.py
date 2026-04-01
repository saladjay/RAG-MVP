"""
Exception hierarchy for E2E Test Framework.

All custom exceptions inherit from E2ETestError for consistent error handling.
"""


class E2ETestError(Exception):
    """Base exception for E2E Test Framework.

    All framework-specific exceptions inherit from this class.
    """

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        """Initialize exception with message and optional details.

        Args:
            message: Human-readable error message
            details: Additional error context for debugging
        """
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class RAGConnectionError(E2ETestError):
    """Network connection failure when contacting RAG Service."""

    def __init__(self, message: str, *, url: str | None = None, **details) -> None:
        """Initialize connection error.

        Args:
            message: Error message
            url: RAG Service URL that failed
            **details: Additional context
        """
        if url:
            details["url"] = url
        super().__init__(message, details=details)


class RAGTimeoutError(E2ETestError):
    """Request timeout when waiting for RAG Service response."""

    def __init__(self, message: str, *, timeout_seconds: int | None = None, **details) -> None:
        """Initialize timeout error.

        Args:
            message: Error message
            timeout_seconds: Configured timeout that was exceeded
            **details: Additional context
        """
        if timeout_seconds:
            details["timeout_seconds"] = timeout_seconds
        super().__init__(message, details=details)


class RAGServerError(E2ETestError):
    """5xx server error response from RAG Service."""

    def __init__(self, message: str, *, status_code: int | None = None, **details) -> None:
        """Initialize server error.

        Args:
            message: Error message
            status_code: HTTP status code received
            **details: Additional context
        """
        if status_code:
            details["status_code"] = status_code
        super().__init__(message, details=details)


class RAGClientError(E2ETestError):
    """4xx client error response from RAG Service."""

    def __init__(self, message: str, *, status_code: int | None = None, **details) -> None:
        """Initialize client error.

        Args:
            message: Error message
            status_code: HTTP status code received
            **details: Additional context
        """
        if status_code:
            details["status_code"] = status_code
        super().__init__(message, details=details)


class TestFileError(E2ETestError):
    """Error parsing or validating test file."""

    def __init__(self, message: str, *, file_path: str | None = None, line_number: int | None = None, details: dict | None = None, **kwargs) -> None:
        """Initialize test file error.

        Args:
            message: Error message
            file_path: Path to file that failed
            line_number: Line number where error occurred
            details: Additional context dictionary
            **kwargs: Additional context (merged into details)
        """
        if details is None:
            details = {}
        if file_path:
            details["file_path"] = file_path
        if line_number:
            details["line_number"] = line_number
        details.update(kwargs)
        super().__init__(message, details=details)


class TestValidationError(E2ETestError):
    """Error validating test case data."""

    def __init__(self, message: str, *, test_id: str | None = None, **details) -> None:
        """Initialize validation error.

        Args:
            message: Error message
            test_id: Test case ID that failed validation
            **details: Additional context
        """
        if test_id:
            details["test_id"] = test_id
        super().__init__(message, details=details)
