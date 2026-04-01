"""
Structured logging configuration for uv_python.

This module provides a centralized logging setup with configurable levels,
formatters, and handlers. It supports both console and file logging with
optional colored output.
"""

import logging
import sys
from pathlib import Path
from typing import Optional

from uv_python.config import get_config


class ColoredFormatter(logging.Formatter):
    """
    Colored log formatter for console output.

    Provides color-coded log levels for better readability in terminals.
    Colors are automatically disabled when output is not a TTY.
    """

    # ANSI color codes
    COLORS = {
        logging.DEBUG: "\033[36m",    # Cyan
        logging.INFO: "\033[32m",     # Green
        logging.WARNING: "\033[33m",  # Yellow
        logging.ERROR: "\033[31m",    # Red
        logging.CRITICAL: "\033[35m", # Magenta
    }
    RESET = "\033[0m"

    def __init__(self, fmt: Optional[str] = None, use_colors: bool = True) -> None:
        """
        Initialize colored formatter.

        Args:
            fmt: Log message format string.
            use_colors: Whether to use colored output.
        """
        super().__init__(fmt)
        self.use_colors = use_colors and self._supports_color()

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record with optional colors.

        Args:
            record: The log record to format.

        Returns:
            Formatted log message.
        """
        if self.use_colors:
            level_color = self.COLORS.get(record.levelno, "")
            record.levelname = f"{level_color}{record.levelname}{self.RESET}"
        return super().format(record)

    @staticmethod
    def _supports_color() -> bool:
        """Check if the terminal supports colored output."""
        return (
            hasattr(sys.stdout, "isatty") and sys.stdout.isatty() and
            sys.platform != "win32"
        )


def setup_logger(
    name: str = "uv_python",
    level: Optional[str] = None,
    log_file: Optional[Path] = None,
) -> logging.Logger:
    """
    Set up and configure a logger instance.

    Args:
        name: Logger name (typically the module name).
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_file: Optional path to log file for file logging.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(name)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # Determine log level
    config = get_config()
    if level:
        log_level = getattr(logging, level.upper(), logging.INFO)
    elif config.verbose:
        log_level = logging.DEBUG
    elif config.quiet:
        log_level = logging.WARNING
    else:
        log_level = logging.INFO

    logger.setLevel(log_level)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # Console formatter
    console_format = "%(levelname)s: %(message)s"
    if config.verbose:
        console_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    use_colors = not config.no_color
    console_formatter = ColoredFormatter(console_format, use_colors=use_colors)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)

        # File formatter (no colors, more detail)
        file_format = "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
        file_formatter = logging.Formatter(file_format, datefmt="%Y-%m-%d %H:%M:%S")
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the given name.

    Args:
        name: Logger name (typically __name__ from calling module).

    Returns:
        Logger instance, creating if necessary.
    """
    # Check if logger already configured
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logger(name)
    return logger


# Module-level logger for this module
_logger = get_logger(__name__)


def log_exception(logger: logging.Logger, message: str, exc_info: bool = True) -> None:
    """
    Log an exception with consistent formatting.

    Args:
        logger: Logger instance to use.
        message: Error message to log.
        exc_info: Whether to include exception info.
    """
    logger.error(message, exc_info=exc_info)


def set_log_level(level: str) -> None:
    """
    Set the log level for all uv_python loggers.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    for logger_name in logging.Logger.manager.loggerDict:
        if logger_name.startswith("uv_python"):
            logging.getLogger(logger_name).setLevel(log_level)
            for handler in logging.getLogger(logger_name).handlers:
                handler.setLevel(log_level)
