"""
Command-line interface for E2E Test Framework.

Provides the `e2e` command for running tests against RAG Service.
"""

import asyncio
import sys
from pathlib import Path
from typing import List, Optional

import typer

from e2e_test.clients.rag_client import RAGClient
from e2e_test.core.exceptions import E2ETestError, TestFileError
from e2e_test.core.logger import get_logger
from e2e_test.models.config import OutputFormat, TestConfig
from e2e_test.models.test_result import TestReport
from e2e_test.reporters.console import ConsoleReporter
from e2e_test.reporters.json_report import JSONReporter
from e2e_test.runners.test_runner import TestRunner
from e2e_test.runners.external_kb_test import run_external_kb_test

# Create CLI app
app = typer.Typer(
    name="e2e",
    help="E2E Test Framework for RAG Service validation",
    add_completion=False
)

# Global logger
logger = get_logger()


@app.command()
def run(
    file_path: Path = typer.Argument(
        ...,
        help="Path to test file or directory",
        exists=True
    ),
    url: str = typer.Option(
        "http://localhost:8000",
        "--url",
        "-u",
        help="RAG Service base URL"
    ),
    timeout: int = typer.Option(
        30,
        "--timeout",
        "-t",
        help="Request timeout in seconds"
    ),
    threshold: float = typer.Option(
        0.7,
        "--threshold",
        "-T",
        help="Similarity threshold for passing (0.0-1.0)"
    ),
    format: OutputFormat = typer.Option(
        OutputFormat.CONSOLE,
        "--format",
        "-f",
        help="Output format"
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path (for JSON format)"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output"
    ),
    tag: List[str] = typer.Option(
        [],
        "--tag",
        "-g",
        help="Filter tests by tag (can be specified multiple times)"
    ),
    exclude_tag: List[str] = typer.Option(
        [],
        "--exclude-tag",
        "-e",
        help="Exclude tests by tag (can be specified multiple times)"
    ),
    test_id: List[str] = typer.Option(
        [],
        "--test-id",
        "-i",
        help="Run specific test by ID (can be specified multiple times)"
    )
) -> None:
    """Run E2E tests against RAG Service.

    Examples:
        e2e run tests.test.json
        e2e run tests/ --url http://localhost:8001
        e2e run basic.test.json --format json --output results.json
    """
    # Create config
    try:
        config = TestConfig(
            rag_service_url=url,
            timeout_seconds=timeout,
            similarity_threshold=threshold,
            output_format=format,
            verbose=verbose
        )
    except Exception as e:
        reporter = ConsoleReporter()
        reporter.print_error(f"Invalid configuration: {e}")
        sys.exit(1)

    # Create reporter
    reporter = ConsoleReporter(verbose=verbose)

    # Create RAG client and test runner
    rag_client = RAGClient(
        base_url=config.rag_service_url,
        timeout_seconds=config.timeout_seconds
    )
    runner = TestRunner(config=config, rag_client=rag_client)

    # Run tests
    try:
        report = asyncio.run(_run_tests(
            runner,
            file_path,
            reporter,
            tags=tag if tag else None,
            exclude_tags=exclude_tag if exclude_tag else None,
            test_ids=test_id if test_id else None
        ))

        # Print report
        if config.output_format == OutputFormat.CONSOLE:
            reporter.print_report(report)
        elif config.output_format == OutputFormat.JSON:
            json_reporter = JSONReporter(pretty=True)
            output_path = output or Path("results.json")
            json_reporter.save_report(report, output_path)
            reporter.print_info(f"Report saved to: {output_path}")

        # Exit with appropriate code
        if report.errors > 0:
            sys.exit(2)  # Errors indicate test execution problems
        elif report.failed > 0:
            sys.exit(1)  # Failures indicate tests didn't pass
        else:
            sys.exit(0)  # All tests passed

    except TestFileError as e:
        reporter.print_error(f"Test file error: {e.message}")
        if e.details:
            for key, value in e.details.items():
                reporter.print_info(f"  {key}: {value}")
        sys.exit(1)

    except E2ETestError as e:
        reporter.print_error(f"E2E test error: {e.message}")
        sys.exit(1)

    except Exception as e:
        reporter.print_error(f"Unexpected error: {e}")
        sys.exit(1)


async def _run_tests(
    runner: TestRunner,
    file_path: Path,
    reporter: ConsoleReporter,
    tags: Optional[List[str]] = None,
    exclude_tags: Optional[List[str]] = None,
    test_ids: Optional[List[str]] = None
) -> TestReport:
    """Run tests from file or directory.

    Args:
        runner: Test runner instance
        file_path: Path to test file or directory
        reporter: Console reporter
        tags: Optional list of tags to filter by
        exclude_tags: Optional list of tags to exclude
        test_ids: Optional list of specific test IDs to run

    Returns:
        Aggregated test report
    """
    # Check if path is file or directory
    if file_path.is_file():
        # Run single test file
        return await runner.run_test_file(
            file_path,
            tags=tags,
            exclude_tags=exclude_tags,
            test_ids=test_ids
        )

    elif file_path.is_dir():
        # Discover and run all test files in directory
        test_files = _discover_test_files(file_path)

        if not test_files:
            reporter.print_warning(f"No test files found in: {file_path}")
            # Return empty report
            return TestReport(
                suite_name=file_path.name,
                total_tests=0,
                passed=0,
                failed=0,
                errors=0,
                skipped=0,
                results=[]
            )

        # Run all test files and aggregate results
        all_results = []
        total_passed = 0
        total_failed = 0
        total_errors = 0
        total_latency = 0.0

        for test_file in test_files:
            reporter.print_info(f"Running: {test_file.name}")
            report = await runner.run_test_file(
                test_file,
                tags=tags,
                exclude_tags=exclude_tags,
                test_ids=test_ids
            )

            all_results.extend(report.results)
            total_passed += report.passed
            total_failed += report.failed
            total_errors += report.errors
            total_latency += report.total_latency_ms

        # Create aggregated report
        return TestReport(
            suite_name=file_path.name,
            total_tests=len(all_results),
            passed=total_passed,
            failed=total_failed,
            errors=total_errors,
            skipped=0,
            results=all_results,
            total_latency_ms=total_latency
        )

    else:
        raise TestFileError(f"Path does not exist: {file_path}")


def _discover_test_files(directory: Path) -> List[Path]:
    """Discover test files in directory.

    Args:
        directory: Directory to search

    Returns:
        List of test file paths
    """
    from e2e_test.parsers.factory import ParserFactory

    test_files = []
    supported_extensions = ParserFactory.get_supported_extensions()

    # Look for all supported test file formats
    for ext in supported_extensions:
        # Match patterns like *.json, *.yaml, etc.
        test_files.extend(directory.glob(f"*{ext}"))
        test_files.extend(directory.glob(f"test_*{ext}"))
        test_files.extend(directory.glob(f"*.test*{ext}"))

        # Also search subdirectories recursively
        for subdir in directory.rglob("*"):
            if subdir.is_dir():
                test_files.extend(subdir.glob(f"*{ext}"))
                test_files.extend(subdir.glob(f"test_*{ext}"))
                test_files.extend(subdir.glob(f"*.test*{ext}"))

    return sorted(set(test_files))


@app.command()
def external_kb(
    file_path: Path = typer.Argument(
        ...,
        help="Path to JSONL test file",
        exists=True
    ),
    base_url: str = typer.Option(
        ...,
        "--base-url",
        "-b",
        help="External KB service base URL"
    ),
    output: Path = typer.Option(
        "external_kb_results.json",
        "--output",
        "-o",
        help="Output file path for results"
    ),
    comp_id: str = typer.Option(
        "N000131",
        "--comp-id",
        "-c",
        help="Company ID for queries"
    ),
    file_type: str = typer.Option(
        "PublicDocDispatch",
        "--file-type",
        "-f",
        help="File type filter"
    ),
    search_type: int = typer.Option(
        1,
        "--search-type",
        "-s",
        help="Search type: 0=vector, 1=fulltext, 2=hybrid"
    ),
    topk: int = typer.Option(
        10,
        "--topk",
        "-k",
        help="Number of results to retrieve"
    ),
    endpoint: str = typer.Option(
        "/ai-parsing-file/ai/file-knowledge/queryKnowledge",
        "--endpoint",
        "-e",
        help="API endpoint path"
    ),
    xtoken: str = typer.Option(
        "",
        "--xtoken",
        "-x",
        help="X-Token header for authentication"
    ),
    mock: bool = typer.Option(
        False,
        "--mock",
        "-m",
        help="Use mock data instead of calling real service"
    ),
    limit: int = typer.Option(
        0,
        "--limit",
        "-l",
        help="Limit number of tests to run (0 = all)"
    )
) -> None:
    """Run external knowledge base query test.

    Reads a JSONL file with questions, queries the external KB,
    and saves results to a JSON file.

    Example:
        e2e external-kb questions/fianl_version_qa.jsonl --base-url http://localhost:8001
        e2e external-kb questions/fianl_version_qa.jsonl --base-url http://localhost:8001 --mock --limit 5
    """
    reporter = ConsoleReporter()

    reporter.print_info(f"Reading test file: {file_path}")
    if mock:
        reporter.print_info("Mode: MOCK (using simulated data)")
    else:
        reporter.print_info(f"External KB URL: {base_url}")
    if limit > 0:
        reporter.print_info(f"Limit: Running first {limit} tests only")

    async def run_test() -> None:
        results = await run_external_kb_test(
            file_path=file_path,
            base_url=base_url,
            output_path=output,
            comp_id=comp_id,
            file_type=file_type,
            search_type=search_type,
            topk=topk,
            endpoint=endpoint,
            xtoken=xtoken,
            mock=mock,
            limit=limit,
        )

        # Print summary
        total = len(results)
        successful = sum(1 for r in results if r.success)
        failed = total - successful

        reporter.print_info(f"\nTest Summary:")
        reporter.print_info(f"  Total tests: {total}")
        reporter.print_info(f"  Successful: {successful}")
        reporter.print_info(f"  Failed: {failed}")
        reporter.print_info(f"  Results saved to: {output}")

        return failed

    failed_count = asyncio.run(run_test())

    # Exit with appropriate code
    if failed_count > 0:
        sys.exit(1)
    else:
        sys.exit(0)


@app.command()
def health(
    url: str = typer.Option(
        "http://localhost:8000",
        "--url",
        "-u",
        help="RAG Service base URL"
    )
) -> None:
    """Check RAG Service health.

    Example:
        e2e health --url http://localhost:8000
    """
    reporter = ConsoleReporter()

    async def check() -> bool:
        client = RAGClient(base_url=url)
        return await client.health_check()

    is_healthy = asyncio.run(check())

    if is_healthy:
        reporter.print_info(f"✓ RAG Service is healthy: {url}")
        sys.exit(0)
    else:
        reporter.print_error(f"✗ RAG Service is not healthy: {url}")
        sys.exit(1)


def main() -> None:
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
