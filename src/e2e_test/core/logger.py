"""
Structured logger for E2E Test Framework.

Provides JSON-formatted logging with trace ID support for observability.
"""

import logging
import sys
from pathlib import Path
from typing import Any

from pythonjsonlogger import jsonlogger

from e2e_test.core.exceptions import E2ETestError


class E2ETestLogger:
    """Structured logger for E2E Test Framework."""

    _instance: "E2ETestLogger | None" = None
    _logger: logging.Logger

    def __new__(cls) -> "E2ETestLogger":
        """Singleton pattern for consistent logging."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._setup_logger()
        return cls._instance

    def _setup_logger(self) -> None:
        """Configure the JSON logger."""
        self._logger = logging.getLogger("e2e_test")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False

        # Remove existing handlers
        self._logger.handlers.clear()

        # Console handler with JSON formatter
        handler = logging.StreamHandler(sys.stdout)
        formatter = jsonlogger.JsonFormatter(
            "%(asctime)s %(name)s %(levelname)s %(message)s",
            timestamp=True
        )
        handler.setFormatter(formatter)
        self._logger.addHandler(handler)

    def _format_context(self, extra: dict[str, Any] | None) -> dict[str, Any]:
        """Format extra context with standard fields."""
        if extra is None:
            extra = {}
        return {"event": "e2e_test", **extra}

    def info(self, message: str, **extra: Any) -> None:
        """Log info message.

        Args:
            message: Log message
            **extra: Additional context fields
        """
        self._logger.info(message, extra=self._format_context(extra))

    def warning(self, message: str, **extra: Any) -> None:
        """Log warning message.

        Args:
            message: Log message
            **extra: Additional context fields
        """
        self._logger.warning(message, extra=self._format_context(extra))

    def error(self, message: str, *, exc_info: bool = False, **extra: Any) -> None:
        """Log error message.

        Args:
            message: Log message
            exc_info: Include exception traceback
            **extra: Additional context fields
        """
        self._logger.error(message, extra=self._format_context(extra), exc_info=exc_info)

    def debug(self, message: str, **extra: Any) -> None:
        """Log debug message.

        Args:
            message: Log message
            **extra: Additional context fields
        """
        self._logger.debug(message, extra=self._format_context(extra))

    def test_start(self, test_id: str, question: str, **extra: Any) -> None:
        """Log test execution start.

        Args:
            test_id: Test case identifier
            question: Test question being asked
            **extra: Additional context
        """
        self.info(f"Starting test: {test_id}", test_id=test_id, question=question[:100] + "..." if len(question) > 100 else question, **extra)

    def test_complete(self, test_id: str, status: str, similarity: float | None = None, **extra: Any) -> None:
        """Log test completion.

        Args:
            test_id: Test case identifier
            status: Test result status (passed, failed, error)
            similarity: Similarity score if available
            **extra: Additional context
        """
        context = {"test_id": test_id, "status": status, **extra}
        if similarity is not None:
            context["similarity_score"] = similarity
        self.info(f"Test complete: {test_id} - {status}", **context)

    def test_error(self, test_id: str, error_message: str, **extra: Any) -> None:
        """Log test error.

        Args:
            test_id: Test case identifier
            error_message: Error description
            **extra: Additional context
        """
        self.error(f"Test error: {test_id}", test_id=test_id, error=error_message, **extra)

    def suite_start(self, suite_name: str, total_tests: int, **extra: Any) -> None:
        """Log test suite start.

        Args:
            suite_name: Name of test suite/file
            total_tests: Number of tests to run
            **extra: Additional context
        """
        self.info(f"Starting test suite: {suite_name}", suite_name=suite_name, total_tests=total_tests, **extra)

    def suite_complete(self, suite_name: str, passed: int, failed: int, errors: int, duration_ms: float, **extra: Any) -> None:
        """Log test suite completion.

        Args:
            suite_name: Name of test suite/file
            passed: Number of passed tests
            failed: Number of failed tests
            errors: Number of errored tests
            duration_ms: Total execution time in milliseconds
            **extra: Additional context
        """
        self.info(
            f"Test suite complete: {suite_name}",
            suite_name=suite_name,
            passed=passed,
            failed=failed,
            errors=errors,
            duration_ms=duration_ms,
            **extra
        )


# Global logger instance
def get_logger() -> E2ETestLogger:
    """Get the global E2E Test Framework logger.

    Returns:
        Singleton logger instance
    """
    return E2ETestLogger()
