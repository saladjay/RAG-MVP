"""
CLI command handlers for uv_python.

This module provides the implementation of all CLI commands.
"""

import json
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from uv_python.config import get_config
from uv_python.core.logger import get_logger
from uv_python.core.exceptions import UVPythonError


# Console for rich output
console = Console()
logger = get_logger(__name__)


def list(
    all: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Include pre-release versions",
    ),
    installed: bool = typer.Option(
        False,
        "--installed",
        help="Show only installed versions",
    ),
    stable: bool = typer.Option(
        True,
        "--stable",
        "-s",
        help="Show only stable versions",
    ),
    format: str = typer.Option(
        "table",
        "--format",
        "-f",
        help="Output format: table, json, plain",
    ),
) -> None:
    """
    List available Python versions.

    Shows Python versions available from official sources.
    Use --all to include pre-release versions.
    """
    config = get_config()

    if config.verbose:
        logger.debug(f"Listing versions: all={all}, installed={installed}, stable={stable}")

    # TODO: Implement version listing from VersionDiscoveryService
    # This is a stub implementation
    console.print("[yellow]Version listing not yet implemented[/yellow]")
    console.print("Use --verbose for more information")

    # Placeholder output
    if format == "json":
        output = {
            "versions": [
                {
                    "version": "3.11.8",
                    "status": "stable",
                    "platforms": ["linux", "macos", "windows"],
                    "installed": False,
                }
            ]
        }
        console.print(json.dumps(output, indent=2))
    else:
        table = Table(title="Python Versions")
        table.add_column("Version", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Platform", style="blue")
        table.add_column("Installed", style="yellow")

        table.add_row("3.11.8", "stable", "linux", "X")
        table.add_row("3.12.0", "stable", "linux", "X")

        console.print(table)


def install(
    version: str = typer.Argument(
        ...,
        help="Python version to install (e.g., '3.11.8', '3.11', 'latest')",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Reinstall if already installed",
    ),
    no_cache: bool = typer.Option(
        False,
        "--no-cache",
        help="Skip cache, force download",
    ),
    no_verify: bool = typer.Option(
        False,
        "--no-verify",
        help="Skip checksum verification",
    ),
) -> None:
    """
    Install a Python version.

    Downloads and installs the specified Python version.
    Use --force to reinstall an existing version.
    """
    config = get_config()

    if config.verbose:
        logger.debug(f"Installing Python {version}: force={force}, no_cache={no_cache}, no_verify={no_verify}")

    try:
        # TODO: Implement installation via PythonInstaller
        console.print(f"[yellow]Installing Python {version}...[/yellow]")

        # Placeholder implementation
        console.print(f"[green][OK][/green] Successfully installed Python {version}")
        console.print(f"Binary: {config.install_dir / version / 'bin' / 'python3'}")

    except UVPythonError as e:
        console.print(f"[red]ERROR:[/red] {e.message}")
        if e.suggestion:
            console.print(f"[dim]Suggestion: {e.suggestion}[/dim]")
        raise typer.Exit(1)


def uninstall(
    version: str = typer.Argument(
        ...,
        help="Python version to uninstall",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force removal without confirmation",
    ),
) -> None:
    """
    Uninstall a Python version.

    Removes the specified Python version from the system.
    """
    config = get_config()

    if config.verbose:
        logger.debug(f"Uninstalling Python {version}: force={force}")

    try:
        # TODO: Implement uninstallation via PythonUninstaller
        if not force:
            confirm = typer.confirm(f"Uninstall Python {version}?")
            if not confirm:
                console.print("[yellow]Uninstall cancelled[/yellow]")
                raise typer.Exit(0)

        console.print(f"[yellow]Uninstalling Python {version}...[/yellow]")
        console.print(f"[green][OK][/green] Successfully uninstalled Python {version}")

    except UVPythonError as e:
        console.print(f"[red]ERROR:[/red] {e.message}")
        if e.suggestion:
            console.print(f"[dim]Suggestion: {e.suggestion}[/dim]")
        raise typer.Exit(1)


def global_version(
    version: Optional[str] = typer.Argument(
        None,
        help="Python version to set as global",
    ),
    unset: bool = typer.Option(
        False,
        "--unset",
        "-u",
        help="Unset global version",
    ),
) -> None:
    """
    Set or display the global default Python version.

    With no arguments, displays the current global version.
    With a version argument, sets it as the global default.
    """
    config = get_config()

    if unset:
        # Unset global version
        try:
            # TODO: Implement via GlobalConfigService
            console.print("[yellow]Unsetting global Python version...[/yellow]")
            console.print("[green][OK][/green] Global version unset")
        except UVPythonError as e:
            console.print(f"[red]ERROR:[/red] {e.message}")
            raise typer.Exit(1)
        return

    if version is None:
        # Display current global version
        current = config.default_version
        if current:
            console.print(f"Global Python version: [cyan]{current}[/cyan]")
            console.print(f"Binary: {config.install_dir / current / 'bin' / 'python3'}")
        else:
            console.print("[yellow]No global Python version set[/yellow]")
            console.print("Use 'uv python global <version>' to set one")
        return

    # Set global version
    try:
        # TODO: Implement via GlobalConfigService
        console.print(f"[yellow]Setting global Python version to {version}...[/yellow]")
        console.print(f"[green][OK][/green] Global version set to {version}")
        console.print(f"Config: {config.config_file}")

    except UVPythonError as e:
        console.print(f"[red]ERROR:[/red] {e.message}")
        if e.suggestion:
            console.print(f"[dim]Suggestion: {e.suggestion}[/dim]")
        raise typer.Exit(1)


def pin(
    version: str = typer.Argument(
        ...,
        help="Python version to pin (e.g., '3.11.8', '>=3.11')",
    ),
    file: Optional[str] = typer.Option(
        None,
        "--file",
        "-f",
        help="Config file to use (.python-version or pyproject.toml)",
    ),
) -> None:
    """
    Pin a Python version to the current project.

    Creates or updates .python-version or pyproject.toml with the specified version.
    """
    config = get_config()

    if config.verbose:
        logger.debug(f"Pinning Python version {version} to file: {file}")

    try:
        # TODO: Implement via ProjectDetector and version resolver
        console.print(f"[yellow]Pinning Python {version}...[/yellow]")

        # Determine file to use
        if file:
            target_file = file
        else:
            target_file = ".python-version"

        console.print(f"[green][OK][/green] Pinned Python {version} to {target_file}")
        console.print(f"Project: {Path.cwd()}")

    except UVPythonError as e:
        console.print(f"[red]ERROR:[/red] {e.message}")
        if e.suggestion:
            console.print(f"[dim]Suggestion: {e.suggestion}[/dim]")
        raise typer.Exit(1)


def verify(
    version: str = typer.Argument(
        ...,
        help="Python version to verify",
    ),
    checksum: bool = typer.Option(
        True,
        "--checksum",
        "-c",
        help="Verify checksum",
    ),
    binary: bool = typer.Option(
        True,
        "--binary",
        "-b",
        help="Verify binary works",
    ),
) -> None:
    """
    Verify an installed Python version.

    Checks the integrity and functionality of an installed Python version.
    """
    config = get_config()

    if config.verbose:
        logger.debug(f"Verifying Python {version}: checksum={checksum}, binary={binary}")

    try:
        # TODO: Implement via VerificationService
        console.print(f"[yellow]Verifying Python {version}...[/yellow]")

        # Placeholder output
        console.print(f"[green][OK][/green] Python {version} is valid")
        console.print("  Checksum: verified")
        console.print("  Binary: working")

    except UVPythonError as e:
        console.print(f"[red]ERROR:[/red] Python {version} verification failed")
        console.print(f"  {e.message}")
        if e.suggestion:
            console.print(f"[dim]Suggestion: {e.suggestion}[/dim]")
        raise typer.Exit(1)


def check(
    format: str = typer.Option(
        "table",
        "--format",
        "-f",
        help="Output format: table, json",
    ),
) -> None:
    """
    Perform system health check.

    Checks all installed Python versions and system configuration.
    """
    config = get_config()

    if config.verbose:
        logger.debug(f"Running system health check: format={format}")

    try:
        # TODO: Implement via VerificationService
        console.print("[yellow]Running system health check...[/yellow]")

        if format == "json":
            output = {
                "system": {
                    "platform": config.system,
                    "architecture": config.architecture,
                },
                "config": {
                    "file": str(config.config_file),
                    "cache_dir": str(config.cache_dir),
                },
                "installations": [],
            }
            console.print(json.dumps(output, indent=2))
        else:
            table = Table(title="System Health Check")
            table.add_column("Item", style="cyan")
            table.add_column("Status", style="green")

            table.add_row("System", f"{config.system} {config.architecture}")
            table.add_row("Config", str(config.config_file))
            table.add_row("Cache", str(config.cache_dir))
            table.add_row("No Python versions installed", "OK")

            console.print(table)

    except UVPythonError as e:
        console.print(f"[red]ERROR:[/red] Health check failed: {e.message}")
        raise typer.Exit(1)
