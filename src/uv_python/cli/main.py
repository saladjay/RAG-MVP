"""
CLI main module for uv_python.

This module provides the Typer app initialization and common CLI options.
"""

import sys
from pathlib import Path
from typing import Optional

import typer

from uv_python.cli.commands import (
    check,
    global_version,
    install,
    list,
    pin,
    uninstall,
    verify,
)
from uv_python.config import get_config, reset_config
from uv_python.core.logger import get_logger, set_log_level


# Create Typer app
app = typer.Typer(
    name="uv-python",
    help="UV Python Runtime Management - Discover, install, and manage Python versions",
    add_completion=True,
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Logger for this module
logger = get_logger(__name__)


@app.callback()
def main(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Suppress non-error output",
    ),
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to custom configuration file",
        exists=True,
        dir_okay=False,
    ),
) -> None:
    """
    UV Python Runtime Management

    Discover, install, and manage Python versions using uv.
    """
    # Reset config to allow custom config path
    if config:
        reset_config()
        get_config(config_file=config)
    else:
        get_config()

    # Set log level based on flags
    if verbose and quiet:
        logger.error("Cannot specify both --verbose and --quiet")
        raise typer.Exit(code=2)

    if verbose:
        set_log_level("DEBUG")
    elif quiet:
        set_log_level("ERROR")

    logger.debug("uv-python CLI initialized")


# Register commands
app.command()(list)
app.command()(install)
app.command()(uninstall)
app.command()(global_version)
app.command()(pin)
app.command()(verify)
app.command()(check)


def main_entrypoint() -> None:
    """Main entry point for the CLI."""
    try:
        app()
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        logger.info("Operation cancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main_entrypoint()
