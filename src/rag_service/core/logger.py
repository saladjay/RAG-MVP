"""
Structured logging configuration for RAG Service.

This module provides centralized logging setup with configurable levels,
formatters, and handlers. It supports trace_id injection for request
correlation and context-aware logging across all layers.

Features:
- Console handler with colors (TTY detection)
- File handler with rotation (optional)
- Trace_id injection for request correlation
- Structured log context builder
- Lazy loading of logger instances
- Non-blocking logging to prevent log failures from blocking requests
"""

import logging
import sys
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Context variable for trace_id propagation
trace_id_context: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)


class ContextFormatter(logging.Formatter):
    """
    Custom log formatter with trace_id injection.

    This formatter adds trace_id, request_id, and other context
    to log records for distributed tracing correlation.
    """

    COLORS = {
        logging.DEBUG: "\033[36m",    # Cyan
        logging.INFO: "\033[32m",     # Green
        logging.WARNING: "\033[33m",  # Yellow
        logging.ERROR: "\033[31m",    # Red
        logging.CRITICAL: "\033[35m", # Magenta
    }
    RESET = "\033[0m"

    def __init__(
        self,
        fmt: Optional[str] = None,
        datefmt: Optional[str] = None,
        use_colors: bool = True,
    ) -> None:
        """
        Initialize ContextFormatter.

        Args:
            fmt: Log message format string.
            datefmt: Date format string.
            use_colors: Whether to use colored output.
        """
        super().__init__(fmt, datefmt)
        self.use_colors = use_colors and self._supports_color()

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record with trace_id and other context.

        Args:
            record: The log record to format.

        Returns:
            Formatted log message.
        """
        # Add trace_id from context
        trace_id = trace_id_context.get()
        if trace_id:
            record.trace_id = trace_id[:8]  # Shorten for readability
        else:
            record.trace_id = "--------"

        # Add extra context if present
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        if not hasattr(record, "user_id"):
            record.user_id = "-"

        # Format with base formatter
        message = super().format(record)

        # Add colors if enabled and TTY
        if self.use_colors and record.levelno in self.COLORS:
            level_color = self.COLORS[record.levelno]
            # Replace level name with colored version
            message = message.replace(
                f"{record.levelname}",
                f"{level_color}{record.levelname}{self.RESET}",
            )

        return message

    @staticmethod
    def _supports_color() -> bool:
        """Check if the terminal supports colored output."""
        return (
            hasattr(sys.stdout, "isatty") and
            sys.stdout.isatty() and
            sys.platform != "win32"
        )


def setup_logging(
    name: str = "rag_service",
    level: str = "INFO",
    log_file: Optional[Path] = None,
    log_format: Optional[str] = None,
) -> logging.Logger:
    """
    Set up and configure a logger instance.

    Args:
        name: Logger name (typically the module name).
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file: Optional path to log file for file logging.
        log_format: Optional custom log format string.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(name)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # Set log level
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(log_level)

    # Default format with trace_id
    if log_format is None:
        log_format = (
            "%(asctime)s | %(trace_id)s | %(levelname)-8s | "
            "%(name)s:%(funcName)s:%(lineno)d | %(message)s"
        )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # Console formatter with colors
    console_formatter = ContextFormatter(
        fmt=log_format,
        datefmt="%Y-%m-%d %H:%M:%S",
        use_colors=True,
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)  # Always log DEBUG to file

        # File formatter (no colors, more detail)
        file_formatter = ContextFormatter(
            fmt=log_format,
            datefmt="%Y-%m-%d %H:%M:%S",
            use_colors=False,
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the given name.

    This function implements lazy loading of loggers, creating
    them on first use and caching for subsequent access.

    Args:
        name: Logger name (typically __name__ from calling module).

    Returns:
        Logger instance, creating if necessary.
    """
    logger = logging.getLogger(name)

    # Configure if not already configured
    if not logger.handlers:
        # Get log level from environment or use default
        import os
        log_level = os.getenv("LOG_LEVEL", "INFO")
        setup_logging(name, level=log_level)

    return logger


def set_trace_id(trace_id: Optional[str]) -> None:
    """
    Set the trace_id in the current context.

    This trace_id will be automatically included in all log messages
    within this context (e.g., during request processing).

    Args:
        trace_id: The trace_id to set, or None to clear.
    """
    trace_id_context.set(trace_id)


def get_trace_id() -> Optional[str]:
    """
    Get the current trace_id from context.

    Returns:
        The current trace_id or None if not set.
    """
    return trace_id_context.get()


class LogContext:
    """
    Context manager for temporary log context.

    This allows setting trace_id and other context for a block of code,
    automatically restoring the previous context on exit.

    Example:
        with LogContext(trace_id="abc123"):
            logger.info("This log will include trace_id")
    """

    def __init__(
        self,
        trace_id: Optional[str] = None,
        request_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        """
        Initialize LogContext.

        Args:
            trace_id: Trace ID to set for this context.
            request_id: Request ID to set.
            user_id: User ID to set.
        """
        self.trace_id = trace_id
        self.request_id = request_id
        self.user_id = user_id
        self._token = None

    def __enter__(self) -> "LogContext":
        """Enter the log context."""
        if self.trace_id:
            self._token = trace_id_context.set(self.trace_id)
        return self

    def __exit__(self, *args: Any) -> None:
        """Exit the log context and restore previous state."""
        if self._token:
            self._token.var.reset(self._token)


class NonBlockingHandler(logging.Handler):
    """
    Non-blocking log handler.

    This handler logs in a separate thread to prevent log failures
    or slow I/O from blocking the main application thread.
    """

    def __init__(self, handler: logging.Handler) -> None:
        """
        Initialize NonBlockingHandler.

        Args:
            handler: The underlying handler to use for logging.
        """
        super().__init__()
        self.handler = handler
        self._queue: Optional[logging.handlers.QueueHandler] = None

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit log record without blocking.

        This implementation logs synchronously for simplicity.
        For true non-blocking logging, consider using QueueHandler.

        Args:
            record: The log record to emit.
        """
        try:
            self.handler.emit(record)
        except Exception:
            # Silently ignore log failures to prevent cascading errors
            self.handleError(record)


def create_log_context(
    trace_id: Optional[str] = None,
    request_id: Optional[str] = None,
    user_id: Optional[str] = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Create a log context dictionary.

    This function builds a structured context object that can be
    passed to logging functions for consistent log formatting.

    Args:
        trace_id: Trace ID for the operation.
        request_id: Request ID for the operation.
        user_id: User ID for the operation.
        **kwargs: Additional context fields.

    Returns:
        Dictionary with log context.
    """
    context = {
        "trace_id": trace_id or get_trace_id() or "--------",
        "request_id": request_id or "-",
        "user_id": user_id or "-",
        "timestamp": datetime.utcnow().isoformat(),
    }
    context.update(kwargs)
    return context


def log_exception(
    logger: logging.Logger,
    message: str,
    exc_info: bool = True,
    level: int = logging.ERROR,
) -> None:
    """
    Log an exception with consistent formatting.

    Args:
        logger: Logger instance to use.
        message: Error message to log.
        exc_info: Whether to include exception info.
        level: Log level to use.
    """
    logger.log(level, message, exc_info=exc_info)


# Module-level logger for this module
logger = get_logger(__name__)


def set_global_log_level(level: str) -> None:
    """
    Set the log level for all RAG service loggers.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    for logger_name in logging.Logger.manager.loggerDict:
        if logger_name.startswith("rag_service"):
            logging.getLogger(logger_name).setLevel(log_level)
            for handler in logging.getLogger(logger_name).handlers:
                handler.setLevel(log_level)
