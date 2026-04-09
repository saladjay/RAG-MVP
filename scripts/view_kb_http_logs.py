"""
View External KB HTTP Request/Response Logs

This script reads and displays the HTTP logs from logs/external_kb_http.jsonl
"""

import json
import sys
from datetime import datetime
from pathlib import Path


def load_logs(log_file: str = "logs/external_kb_http.jsonl"):
    """Load logs from file.

    Args:
        log_file: Path to the log file.

    Returns:
        List of log entries.
    """
    log_path = Path(log_file)

    if not log_path.exists():
        print(f"Log file not found: {log_file}")
        print("Make sure EXTERNAL_KB_HTTP_LOG=true and run some queries first.")
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
    success = sum(1 for log in logs if log["error"] is None)
    errors = total - success

    avg_latency = sum(log["latency_ms"] for log in logs) / total

    print("=" * 60)
    print("HTTP Log Summary")
    print("=" * 60)
    print(f"Total requests: {total}")
    print(f"Successful: {success}")
    print(f"Errors: {errors}")
    print(f"Avg latency: {avg_latency:.0f}ms")
    print("")

    # Time range
    timestamps = [log["timestamp"] for log in logs]
    print(f"Time range:")
    print(f"  First: {timestamps[0]}")
    print(f"  Last: {timestamps[-1]}")
    print("")


def print_log_entry(entry, index: int):
    """Print a single log entry.

    Args:
        entry: Log entry dictionary.
        index: Entry index.
    """
    print("=" * 60)
    print(f"Entry #{index + 1} - {entry['timestamp']}")
    print("=" * 60)

    # Request
    print("\n[REQUEST]")
    print(f"URL: {entry['request']['url']}")
    print(f"Headers: {json.dumps(entry['request']['headers'], indent=2)}")
    print(f"Body:")
    body = entry['request']['body']
    print(f"  query: {body.get('query', 'N/A')}")
    print(f"  compId: {body.get('compId', 'N/A')}")
    print(f"  fileType: {body.get('fileType', 'N/A')}")
    print(f"  topk: {body.get('topk', 'N/A')}")
    print(f"  searchType: {body.get('searchType', 'N/A')}")

    # Response
    print(f"\n[RESPONSE]")
    print(f"Status: {entry['response']['status']}")
    print(f"Latency: {entry['latency_ms']:.0f}ms")

    if entry['error']:
        print(f"Error: {entry['error']}")
    elif entry['response']['body']:
        body = entry['response']['body']
        result_count = len(body.get('result', []))
        print(f"Code: {body.get('code')}")
        print(f"Message: {body.get('msg')}")
        print(f"Result count: {result_count}")

        # Show top chunks
        if result_count > 0:
            print(f"\nTop 3 chunks:")
            for i, chunk in enumerate(body['result'][:3], 1):
                meta = chunk.get('metadata', {})
                doc_name = meta.get('document_name', 'N/A')
                score = meta.get('score', 0)
                content = chunk.get('content', '')[:100]
                print(f"  {i}. {doc_name} (score: {score:.2f})")
                print(f"     Content: {content}...")

    print("")


def filter_logs(logs, query: str = None, min_latency: float = None):
    """Filter logs by criteria.

    Args:
        logs: List of log entries.
        query: Filter by query text.
        min_latency: Minimum latency in ms.

    Returns:
        Filtered list of logs.
    """
    filtered = logs

    if query:
        filtered = [
            log for log in filtered
            if query.lower() in log['request']['body'].get('query', '').lower()
        ]

    if min_latency:
        filtered = [log for log in filtered if log['latency_ms'] >= min_latency]

    return filtered


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="View External KB HTTP logs")
    parser.add_argument("--file", default="logs/external_kb_http.jsonl", help="Log file path")
    parser.add_argument("--tail", type=int, help="Show last N entries")
    parser.add_argument("--filter", help="Filter by query text")
    parser.add_argument("--slow", type=float, help="Show requests slower than X ms")
    parser.add_argument("--errors", action="store_true", help="Show only errors")
    parser.add_argument("--detail", type=int, help="Show detailed view of entry N")

    args = parser.parse_args()

    # Load logs
    logs = load_logs(args.file)

    if not logs:
        return

    # Apply filters
    filtered = logs

    if args.filter:
        filtered = filter_logs(filtered, query=args.filter)

    if args.slow:
        filtered = [log for log in filtered if log['latency_ms'] >= args.slow]

    if args.errors:
        filtered = [log for log in filtered if log['error'] is not None]

    # Show specific entry
    if args.detail is not None:
        if 0 <= args.detail < len(logs):
            print_log_entry(logs[args.detail], args.detail)
        else:
            print(f"Invalid entry index: {args.detail}")
        return

    # Apply tail
    if args.tail:
        filtered = filtered[-args.tail:]

    # Print summary
    print_summary(filtered)

    # Print entries
    for i, entry in enumerate(filtered):
        print_log_entry(entry, i)


if __name__ == "__main__":
    main()
