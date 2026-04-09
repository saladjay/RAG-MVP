"""
View RAG Service Chain Trace Logs

This script reads and displays the chain trace logs from logs/chain_trace.jsonl
"""

import json
import sys
from datetime import datetime
from pathlib import Path


def load_logs(log_file: str = "logs/chain_trace.jsonl"):
    """Load logs from file.

    Args:
        log_file: Path to the log file.

    Returns:
        List of log entries.
    """
    log_path = Path(log_file)

    if not log_path.exists():
        print(f"Log file not found: {log_file}")
        print("Make sure CHAIN_LOG_ENABLED=true and run some QA queries first.")
        return []

    logs = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    logs.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    return logs


def print_summary(logs):
    """Print summary statistics.

    Args:
        logs: List of log entries.
    """
    if not logs:
        return

    total = len(logs)
    avg_time = sum(log["total_time_ms"] for log in logs) / total
    avg_stages = sum(len(log["stages"]) for log in logs) / total

    print("=" * 70)
    print("Chain Trace Log Summary")
    print("=" * 70)
    print(f"Total requests: {total}")
    print(f"Avg total time: {avg_time:.0f}ms")
    print(f"Avg stages: {avg_stages:.1f}")
    print("")

    # Stage statistics
    stage_counts = {}
    stage_times = {}
    for log in logs:
        for stage in log["stages"]:
            name = stage["name"]
            stage_counts[name] = stage_counts.get(name, 0) + 1
            stage_times[name] = stage_times.get(name, 0) + stage["timing_ms"]

    print("Stage breakdown:")
    for stage, count in sorted(stage_counts.items()):
        avg = stage_times[stage] / count
        print(f"  {stage}: {count}x, avg {avg:.0f}ms")
    print("")

    # Time range
    timestamps = [log.get("start_time", log.get("timestamp", "")) for log in logs]
    if timestamps and timestamps[0]:
        print(f"Time range:")
        print(f"  First: {timestamps[0]}")
        print(f"  Last: {timestamps[-1]}")
    print("")


def print_log_entry(entry, index: int, verbose: bool = False):
    """Print a single log entry.

    Args:
        entry: Log entry dictionary.
        index: Entry index.
        verbose: Show detailed information.
    """
    print("=" * 70)
    print(f"Request #{index + 1} - {entry.get('start_time', entry.get('timestamp', 'N/A'))}")
    print(f"Trace ID: {entry['trace_id']}")
    print("=" * 70)

    # Request
    print("\n[REQUEST]")
    req = entry['request']
    print(f"Query: {req.get('query', 'N/A')}")
    print(f"Company ID: {req.get('company_id', 'N/A')}")
    print(f"File Type: {req.get('file_type', 'N/A')}")
    if verbose:
        print(f"Options: {req.get('options', {})}")

    # Stages
    print(f"\n[STAGES] ({len(entry['stages'])} stages)")
    total_stage_time = 0
    for stage in entry['stages']:
        total_stage_time += stage['timing_ms']
        print(f"\n  {stage['name'].upper()}")
        print(f"    Time: {stage['timing_ms']:.0f}ms")
        if stage.get('error'):
            print(f"    Error: {stage['error']}")
        else:
            data = stage.get('data', {})
            if stage['name'] == 'query_rewrite':
                print(f"    Was rewritten: {data.get('was_rewritten', False)}")
                if data.get('was_rewritten'):
                    print(f"    Rewritten query: {data.get('rewritten_query', 'N/A')[:80]}...")
            elif stage['name'] == 'retrieval':
                print(f"    Chunks retrieved: {data.get('chunk_count', 0)}")
                if verbose and data.get('sources'):
                    print(f"    Top sources:")
                    for src in data['sources'][:3]:
                        print(f"      - {src.get('document_name', 'N/A')} (score: {src.get('score', 0):.2f})")
            elif stage['name'] == 'generation':
                print(f"    Model: {data.get('model', 'N/A')}")
                print(f"    Gateway: {data.get('gateway_backend', 'N/A')}")
                print(f"    Answer length: {data.get('answer_length', 0)} chars")
                if verbose:
                    print(f"    Preview: {data.get('answer_preview', 'N/A')[:100]}...")
            elif stage['name'] == 'hallucination_check':
                print(f"    Checked: {data.get('checked', False)}")
                print(f"    Passed: {data.get('passed', False)}")
                print(f"    Confidence: {data.get('confidence', 0):.2f}")

    print(f"\n  Stage time total: {total_stage_time:.0f}ms")
    if entry.get('overhead_ms'):
        print(f"  Overhead: {entry['overhead_ms']:.0f}ms")

    # Response
    print(f"\n[RESPONSE]")
    resp = entry['response']
    print(f"Total time: {entry['total_time_ms']:.0f}ms")
    print(f"Answer length: {resp.get('answer_length', 0)} chars")
    print(f"Source count: {resp.get('source_count', 0)}")
    print(f"Hallucination checked: {resp.get('hallucination_checked', False)}")
    if resp.get('hallucination_checked'):
        print(f"Hallucination passed: {resp.get('hallucination_passed', False)}")

    if verbose:
        print(f"\nFull answer:")
        print(resp.get('answer', 'N/A'))

    print("")


def print_timeline(entry):
    """Print a visual timeline for the request.

    Args:
        entry: Log entry dictionary.
    """
    print("=" * 70)
    print(f"Timeline - Trace ID: {entry['trace_id']}")
    print("=" * 70)

    total_time = entry['total_time_ms']
    current_time = 0

    for stage in entry['stages']:
        stage_time = stage['timing_ms']
        pct = (stage_time / total_time) * 100

        bar_len = int(pct / 2)
        bar = "█" * bar_len + "░" * (50 - bar_len)

        print(f"\n{stage['name'].upper():20} {bar} {pct:.0f}%")
        print(f"{' ':20}{stage_time:.0f}ms")

    print(f"\n{' ':20}{'=' * 50}")
    print(f"{' ':20}{total_time:.0f}ms (100%)")
    print("")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="View RAG Service chain trace logs")
    parser.add_argument("--file", default="logs/chain_trace.jsonl", help="Log file path")
    parser.add_argument("--tail", type=int, help="Show last N entries")
    parser.add_argument("--filter", help="Filter by query text")
    parser.add_argument("--slow", type=float, help="Show requests slower than X ms")
    parser.add_argument("--timeline", action="store_true", help="Show visual timeline")
    parser.add_argument("--detail", type=int, help="Show detailed view of entry N")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed information")

    args = parser.parse_args()

    # Load logs
    logs = load_logs(args.file)

    if not logs:
        return

    # Apply filters
    filtered = logs

    if args.filter:
        filtered = [
            log for log in filtered
            if args.filter.lower() in log['request'].get('query', '').lower()
        ]

    if args.slow:
        filtered = [log for log in filtered if log['total_time_ms'] >= args.slow]

    # Apply tail
    if args.tail:
        filtered = filtered[-args.tail:]

    # Print summary
    print_summary(filtered)

    # Print entries
    for i, entry in enumerate(filtered):
        if args.timeline:
            print_timeline(entry)
        else:
            print_log_entry(entry, i, verbose=args.verbose)

        # Add separator between entries
        if i < len(filtered) - 1:
            print()


if __name__ == "__main__":
    main()
