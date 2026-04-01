"""
Structured logging with trace_id injection for Prompt Management Service.

This module provides a centralized logging configuration with:
- JSON formatter for structured logging
- Trace ID injection via ContextVar for request tracking
- Configurable log levels from environment
- Support for both sync and async contexts

Usage:
    from prompt_service.core.logger import get_logger, set_trace_id

    logger = get_logger(__name__)
    set_trace_id("abc-123-def")
    logger.info("Processing request")  # Includes trace_id in output
"""

import logging
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Dict, Optional

from pythonjsonlogger import jsonlogger

# Context variable for trace_id propagation across async boundaries
_trace_id_ctx: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)


class ContextFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with trace_id injection.

    Extends the standard JSON formatter to automatically inject
    the current trace_id from the context variable into each log record.
    """

    def add_fields(
        self,
        log_record: Dict[str, Any],
        record: logging.LogRecord,
        message_dict: Dict[str, Any],
    ) -> None:
        """Add custom fields to the log record.

        Args:
            log_record: The log record dictionary to populate
            record: The Python logging record
            message_dict: Additional message fields
        """
        super().add_fields(log_record, record, message_dict)

        # Add trace_id from context if available
        trace_id = _trace_id_ctx.get()
        if trace_id:
            log_record["trace_id"] = trace_id

        # Add timestamp if not present
        if "timestamp" not in log_record:
            log_record["timestamp"] = datetime.utcnow().isoformat()

        # Add service name
        log_record["service"] = "prompt-service"


def setup_logging(
    level: str = "INFO",
    log_format: str = "json",
) -> None:
    """Configure the root logger with structured JSON output.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Output format ('json' or 'text')
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)

    # Set formatter
    if log_format.lower() == "json":
        formatter = ContextFormatter(
            fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)8s] %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the specified name.

    Args:
        name: Logger name (typically __name__ of the calling module)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def set_trace_id(trace_id: Optional[str]) -> None:
    """Set the trace_id for the current context.

    The trace_id will be included in all log messages within
    this context (including async tasks).

    Args:
        trace_id: The trace identifier to set, or None to clear
    """
    _trace_id_ctx.set(trace_id)


def get_trace_id() -> Optional[str]:
    """Get the current trace_id from context.

    Returns:
        The current trace_id or None if not set
    """
    return _trace_id_ctx.get()


@contextmanager
def trace_context(trace_id: str):
    """Context manager for setting trace_id in a block.

    Args:
        trace_id: The trace identifier to use in this context

    Yields:
        None

    Example:
        with trace_context("abc-123"):
            logger.info("This log includes trace_id")
    """
    token = _trace_id_ctx.set(trace_id)
    try:
        yield
    finally:
        _trace_id_ctx.reset(token)


class LoggerAdapter:
    """Logger adapter that automatically includes trace_id.

    This adapter wraps the standard logger to provide additional
    convenience methods for structured logging with context.
    """

    def __init__(self, name: str):
        """Initialize the logger adapter.

        Args:
            name: Logger name (typically __name__)
        """
        self._logger = get_logger(name)

    def _log_with_context(
        self,
        level: int,
        msg: str,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Log a message with current context.

        Args:
            level: Logging level
            msg: Log message
            *args: Additional format arguments
            **kwargs: Additional context to include in log
        """
        extra = kwargs.pop("extra", {})

        # Add trace_id to extra context if not present
        if "trace_id" not in extra:
            trace_id = get_trace_id()
            if trace_id:
                extra["trace_id"] = trace_id

        kwargs["extra"] = extra
        self._logger.log(level, msg, *args, **kwargs)

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log a debug message."""
        self._log_with_context(logging.DEBUG, msg, *args, **kwargs)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log an info message."""
        self._log_with_context(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log a warning message."""
        self._log_with_context(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log an error message."""
        self._log_with_context(logging.ERROR, msg, *args, **kwargs)

    def critical(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log a critical message."""
        self._log_with_context(logging.CRITICAL, msg, *args, **kwargs)

    def exception(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log an error message with exception info."""
        kwargs.setdefault("exc_info", True)
        self._log_with_context(logging.ERROR, msg, *args, **kwargs)
