"""
Console reporter for displaying test results.

Uses rich library for formatted terminal output with colors and tables.
"""

from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from e2e_test.models.test_result import SourceDocsMatch, TestStatus, TestReport


class ConsoleReporter:
    """Generate formatted console reports for test results."""

    def __init__(self, verbose: bool = False) -> None:
        """Initialize console reporter.

        Args:
            verbose: Enable detailed output
        """
        self.console = Console()
        self.verbose = verbose

    def print_report(self, report: TestReport, title: Optional[str] = None) -> None:
        """Print full test report to console.

        Args:
            report: Test report to display
            title: Optional custom title
        """
        if title is None:
            title = "E2E Test Report"

        self._print_header(title)
        self._print_summary(report)
        self._print_test_results(report)

    def _print_header(self, title: str) -> None:
        """Print report header.

        Args:
            title: Header title
        """
        self.console.print()
        self.console.print(Panel(
            f"[bold cyan]{title}[/bold cyan]",
            border_style="bright_blue"
        ))
        self.console.print()

    def _print_summary(self, report: TestReport) -> None:
        """Print test summary statistics.

        Args:
            report: Test report
        """
        # Build summary table
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Test Suite", report.suite_name)
        table.add_row("Total Tests", str(report.total_tests))

        # Color-code status counts
        passed_style = "green" if report.passed > 0 else "dim"
        failed_style = "red" if report.failed > 0 else "dim"
        errors_style = "yellow" if report.errors > 0 else "dim"

        table.add_row("Passed", f"[{passed_style}]{report.passed}[/{passed_style}]")
        table.add_row("Failed", f"[{failed_style}]{report.failed}[/{failed_style}]")
        table.add_row("Errors", f"[{errors_style}]{report.errors}[/{errors_style}]")

        # Pass rate
        pass_rate = report.pass_rate * 100
        pass_rate_style = "green" if pass_rate == 100 else "yellow" if pass_rate >= 70 else "red"
        table.add_row("Pass Rate", f"[{pass_rate_style}]{pass_rate:.1f}%[/{pass_rate_style}]")

        # Similarity average (if any scored results)
        if report.similarity_avg > 0:
            similarity_style = "green" if report.similarity_avg >= 0.8 else "yellow" if report.similarity_avg >= 0.6 else "red"
            table.add_row("Avg Similarity", f"[{similarity_style}]{report.similarity_avg:.2f}[/{similarity_style}]")

        # Execution time
        table.add_row("Execution Time", f"{report.execution_time_s:.2f}s")

        self.console.print(table)
        self.console.print()

    def _print_test_results(self, report: TestReport) -> None:
        """Print individual test results.

        Args:
            report: Test report
        """
        if not report.results:
            self.console.print("[dim]No test results to display[/dim]")
            return

        table = Table(
            title="Test Results",
            show_header=True,
            header_style="bold cyan",
            title_style="bold white"
        )

        table.add_column("Status", style="bold", width=8)
        table.add_column("Test ID", style="cyan", width=25)
        table.add_column("Similarity", style="white", width=10)
        table.add_column("Source Docs", style="white", width=12)
        table.add_column("Latency", style="dim", width=8)

        for result in report.results:
            # Status icon and color
            status_icon = self._get_status_icon(result.status)
            status_style = self._get_status_color(result.status)

            # Similarity (if applicable)
            similarity_str = "N/A"
            if result.similarity_score > 0:
                similarity_str = f"{result.similarity_score:.2f}"
                similarity_style = "green" if result.similarity_score >= 0.7 else "yellow" if result.similarity_score >= 0.5 else "red"
            else:
                similarity_style = "dim"

            # Source docs match
            if result.source_docs_match_type == SourceDocsMatch.NOT_APPLICABLE:
                docs_str = "N/A"
                docs_style = "dim"
            elif result.source_docs_match:
                docs_str = "✓ Match"
                docs_style = "green"
            else:
                docs_str = "✗ Mismatch"
                docs_style = "red"

            # Add row
            table.add_row(
                f"[{status_style}]{status_icon}[/{status_style}]",
                result.test_id,
                f"[{similarity_style}]{similarity_str}[/{similarity_style}]",
                f"[{docs_style}]{docs_str}[/{docs_style}]",
                f"{result.latency_ms:.0f}ms"
            )

            # Verbose mode: show details
            if self.verbose and result.actual_answer:
                table.add_row(
                    "",
                    f"[dim]Q: {result.actual_answer[:60]}...[/dim]",
                    "",
                    "",
                    ""
                )

        self.console.print(table)
        self.console.print()

    def _get_status_icon(self, status: TestStatus) -> str:
        """Get icon for test status.

        Args:
            status: Test status

        Returns:
            Icon character
        """
        icons = {
            TestStatus.PASSED: "✓",
            TestStatus.FAILED: "✗",
            TestStatus.ERROR: "⚠",
            TestStatus.SKIPPED: "⊝"
        }
        return icons.get(status, "?")

    def _get_status_color(self, status: TestStatus) -> str:
        """Get color for test status.

        Args:
            status: Test status

        Returns:
            Color name for rich markup
        """
        colors = {
            TestStatus.PASSED: "green",
            TestStatus.FAILED: "red",
            TestStatus.ERROR: "yellow",
            TestStatus.SKIPPED: "dim"
        }
        return colors.get(status, "white")

    def print_error(self, message: str) -> None:
        """Print error message.

        Args:
            message: Error message
        """
        self.console.print(f"[red]ERROR: {message}[/red]")

    def print_warning(self, message: str) -> None:
        """Print warning message.

        Args:
            message: Warning message
        """
        self.console.print(f"[yellow]WARNING: {message}[/yellow]")

    def print_info(self, message: str) -> None:
        """Print info message.

        Args:
            message: Info message
        """
        self.console.print(f"[cyan]{message}[/cyan]")
