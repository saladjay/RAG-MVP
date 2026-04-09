"""
Performance benchmarks for RAG QA Pipeline.

This script measures end-to-end latency and verifies
the < 10 second success criterion (SC-001).
"""

import asyncio
import time
import statistics
from typing import List, Dict, Any
from datetime import datetime

import httpx


class PerformanceBenchmark:
    """Performance benchmarks for QA Pipeline."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        total_runs: int = 10,
        timeout: float = 30.0,
    ) -> None:
        """
        Initialize benchmark.

        Args:
            base_url: Base URL of the RAG Service
            total_runs: Number of test runs per benchmark
            timeout: Request timeout in seconds
        """
        self.base_url = base_url
        self.total_runs = total_runs
        self.timeout = timeout
        self.results: Dict[str, List[float]] = {}

    async def run_benchmark(self, name: str, request: Dict[str, Any]) -> Dict[str, float]:
        """
        Run a single benchmark.

        Args:
            name: Benchmark name
            request: Request payload

        Returns:
            Dictionary with timing statistics
        """
        latencies = []

        print(f"\n{'=' * 60}")
        print(f"Benchmark: {name}")
        print(f"{'=' * 60}")
        print(f"Running {self.total_runs} iterations...")
        print(f"Target: < 10 seconds (95th percentile)")
        print(f"Timeout: {self.timeout} seconds per request")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for i in range(self.total_runs):
                start = time.time()

                try:
                    response = await client.post(
                        f"{self.base_url}/qa/query",
                        json=request,
                        headers={"X-Trace-ID": f"bench_{name}_{i}"},
                    )

                    latency_ms = (time.time() - start) * 1000

                    if response.status_code == 200:
                        latencies.append(latency_ms)
                        print(f"  Run {i+1}/{self.total_runs}: {latency_ms:.0f}ms ✓")
                    else:
                        print(f"  Run {i+1}/{self.total_runs}: HTTP {response.status_code} ✗")

                except Exception as e:
                    print(f"  Run {i+1}/{self.total_runs}: Error - {e}")

        if not latencies:
            print(f"\n❌ Benchmark failed: No successful requests")
            return {"success": False, "error": "No successful requests"}

        # Calculate statistics
        stats = {
            "name": name,
            "success": True,
            "count": len(latencies),
            "mean_ms": statistics.mean(latencies),
            "median_ms": statistics.median(latencies),
            "stdev_ms": statistics.stdev(latencies) if len(latencies) > 1 else 0,
            "p50_ms": statistics.quantiles(latencies, n=2)[0],
            "p95_ms": statistics.quantiles(latencies, n=20)[18],  # 95th percentile
            "p99_ms": statistics.quantiles(latencies, n=100)[98],  # 99th percentile
            "min_ms": min(latencies),
            "max_ms": max(latencies),
        }

        self.results[name] = latencies

        # Print results
        print(f"\nResults:")
        print(f"  Mean:   {stats['mean_ms']:.0f}ms")
        print(f"  Median: {stats['median_ms']:.0f}ms")
        print(f"  StdDev: {stats['stdev_ms']:.0f}ms")
        print(f"  Min:    {stats['min_ms']:.0f}ms")
        print(f"  Max:    {stats['max_ms']:.0f}ms")
        print(f"\nPercentiles:")
        print(f"  p50:    {stats['p50_ms']:.0f}ms")
        print(f"  p95:    {stats['p95_ms']:.0f}ms {'✓ PASS' if stats['p95_ms'] < 10000 else '✗ FAIL'}")
        print(f"  p99:    {stats['p99_ms']:.0f}ms")

        # Check success criteria
        passed = stats['p95_ms'] < 10000  # SC-001: < 10s at 95th percentile
        print(f"\n{'✓ PASS' if passed else '✗ FAIL'}: SC-001 (95th percentile < 10s)")

        return stats

    async def run_all_benchmarks(self) -> None:
        """Run all defined benchmarks."""
        print(f"\n{'#' * 60}")
        print(f"# RAG QA Pipeline Performance Benchmarks")
        print(f"{'#' * 60}")
        print(f"Date: {datetime.now().isoformat()}")
        print(f"Base URL: {self.base_url}")
        print(f"Target: < 10 seconds at 95th percentile")

        # Benchmark 1: Simple query
        await self.run_benchmark(
            "Simple Query",
            {
                "query": "什么是RAG？",
                "options": {
                    "enable_query_rewrite": False,
                    "enable_hallucination_check": False,
                },
            },
        )

        # Benchmark 2: Query with rewriting
        await self.run_benchmark(
            "Query with Rewriting",
            {
                "query": "春节放假几天？",
                "options": {
                    "enable_query_rewrite": True,
                    "enable_hallucination_check": False,
                },
            },
        )

        # Benchmark 3: Query with hallucination check
        await self.run_benchmark(
            "Query with Hallucination Check",
            {
                "query": "2025年春节放假安排",
                "context": {
                    "company_id": "N000131",
                },
                "options": {
                    "enable_query_rewrite": False,
                    "enable_hallucination_check": True,
                },
            },
        )

        # Benchmark 4: Full pipeline
        await self.run_benchmark(
            "Full Pipeline (All Features)",
            {
                "query": "公司2025年放假安排是什么？",
                "context": {
                    "company_id": "N000131",
                    "file_type": "PublicDocDispatch",
                },
                "options": {
                    "enable_query_rewrite": True,
                    "enable_hallucination_check": True,
                    "top_k": 10,
                },
            },
        )

        # Summary
        print(f"\n{'#' * 60}")
        print(f"# Summary")
        print(f"{'#' * 60}")

        all_passed = True
        for name, latencies in self.results.items():
            p95 = statistics.quantiles(latencies, n=20)[18]
            passed = p95 < 10000
            all_passed = all_passed and passed
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"  {name}: {status} ({p95:.0f}ms at p95)")

        print(f"\n{'=' * 60}")
        if all_passed:
            print("✓ ALL BENCHMARKS PASSED - SC-001 satisfied")
        else:
            print("✗ SOME BENCHMARKS FAILED - SC-001 not satisfied")
        print(f"{'=' * 60}\n")


async def main():
    """Run performance benchmarks."""
    import os

    base_url = os.getenv("RAG_SERVICE_URL", "http://localhost:8000")
    runs = int(os.getenv("BENCHMARK_RUNS", "10"))

    benchmark = PerformanceBenchmark(
        base_url=base_url,
        total_runs=runs,
    )

    await benchmark.run_all_benchmarks()


if __name__ == "__main__":
    asyncio.run(main())
