"""
分析 Milvus 评估日志，统计生成质量

用法:
    # 分析所有日志
    uv run python analyze_eval_logs.py

    # 分析指定目录
    uv run python analyze_eval_logs.py --dir custom_results

    # 只统计，不显示详情
    uv run python analyze_eval_logs.py --dir custom_results --quiet
"""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any


def parse_log_file(filepath: Path) -> List[Dict[str, Any]]:
    """Parse a single log file"""
    entries = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entry = json.loads(line)
                        entries.append(entry)
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        print(f"  [Warning] Cannot read {filepath.name}: {e}")
    return entries


def analyze_logs(log_dir: Path, quiet: bool = False) -> Dict[str, Any]:
    """分析所有日志文件"""

    print("=" * 80)
    print("Milvus Evaluation Log Analysis")
    print("=" * 80)
    print(f"Log Directory: {log_dir}")
    print("-" * 80)

    # Collect all log entries
    all_entries = []
    log_files = sorted(log_dir.glob("milvus_eval_log_*.jsonl"), reverse=True)

    if not log_files:
        print(f"  [Info] No log files found")
        return None

    print(f"  Found {len(log_files)} log files\n")

    for log_file in log_files:
        entries = parse_log_file(log_file)
        if entries:
            print(f"  {log_file.name}: {len(entries)} records")
            all_entries.extend(entries)

    if not all_entries:
        print(f"  [Info] No valid log records")
        return None

    print(f"\n  Total: {len(all_entries)} records")
    print("-" * 80)

    # 统计分析
    stats = {
        "total": len(all_entries),
        "has_evaluation": 0,
        "correct": 0,
        "incorrect": 0,
        "has_error": 0,
        "no_answer": 0,
        "retrieval_only": 0,
        "confidence_sum": 0.0,
        "confidence_count": 0,
        "timing": {
            "retrieve_ms": [],
            "generate_ms": [],
        },
        "by_index": {},
    }

    # 错误分类
    errors = {}

    # 失败原因分类
    failure_reasons = {}
    # 失败案例样本（每个类别保留前3个）
    failure_samples = {}

    for entry in all_entries:
        idx = entry.get("index", 0)
        stats["by_index"][idx] = entry

        # 检查是否有错误
        if "error" in entry:
            stats["has_error"] += 1
            error_msg = entry.get("error", "unknown")[:50]
            errors[error_msg] = errors.get(error_msg, 0) + 1
            continue

        # 检查是否有答案
        if "answer" not in entry:
            stats["no_answer"] += 1
            continue

        # 检查是否只有检索结果（没有生成）
        if "answer" in entry and not entry.get("answer"):
            stats["retrieval_only"] += 1
            continue

        # 有评估结果
        if "evaluation" in entry:
            stats["has_evaluation"] += 1
            eval_result = entry["evaluation"]

            is_correct = eval_result.get("is_correct", False)
            if is_correct:
                stats["correct"] += 1
            else:
                stats["incorrect"] += 1

            # 置信度统计
            confidence = eval_result.get("confidence", 0)
            if confidence > 0:
                stats["confidence_sum"] += confidence
                stats["confidence_count"] += 1

            # 收集失败原因
            if not is_correct:
                reason = eval_result.get("reason", "")
                # 简化原因（取前30个字符作为分类）
                reason_key = reason[:30] if reason else "Unknown"
                failure_reasons[reason_key] = failure_reasons.get(reason_key, 0) + 1

                # 保存样本（每个类别最多3个）
                if reason_key not in failure_samples:
                    failure_samples[reason_key] = []
                if len(failure_samples[reason_key]) < 3:
                    failure_samples[reason_key].append({
                        "index": idx,
                        "query": entry.get("query", "")[:80],
                        "reason": reason[:100]
                    })

        # 计时统计
        if "retrieval" in entry and "timing" in entry["retrieval"]:
            timing = entry["retrieval"]["timing"]
            if "total_ms" in timing:
                stats["timing"]["retrieve_ms"].append(timing["total_ms"])

        if "generation_timing" in entry:
            timing = entry["generation_timing"]
            if "generate_ms" in timing:
                stats["timing"]["generate_ms"].append(timing["generate_ms"])

    # Output statistics
    print(f"\n[Statistics]")
    print(f"  Total Tests:       {stats['total']}")
    print(f"  Has Evaluation:   {stats['has_evaluation']} ({stats['has_evaluation']/stats['total']*100:.1f}%)")
    print(f"  Has Errors:        {stats['has_error']} ({stats['has_error']/stats['total']*100:.1f}%)")
    print(f"  No Answer:        {stats['no_answer']} ({stats['no_answer']/stats['total']*100:.1f}%)")
    print(f"  Retrieval Only:   {stats['retrieval_only']} ({stats['retrieval_only']/stats['total']*100:.1f}%)")

    if stats["has_evaluation"] > 0:
        accuracy = stats["correct"] / stats["has_evaluation"] * 100
        print(f"\n[Accuracy]")
        print(f"  Correct:          {stats['correct']}")
        print(f"  Incorrect:        {stats['incorrect']}")
        print(f"  Accuracy:         {accuracy:.2f}%")

        if stats["confidence_count"] > 0:
            avg_confidence = stats["confidence_sum"] / stats["confidence_count"]
            print(f"  Avg Confidence:   {avg_confidence:.3f}")

    # Timing statistics
    if stats["timing"]["retrieve_ms"]:
        avg_retrieve = sum(stats["timing"]["retrieve_ms"]) / len(stats["timing"]["retrieve_ms"])
        print(f"\n[Retrieval Performance]")
        print(f"  Avg Time:         {avg_retrieve:.1f} ms")
        print(f"  Fastest:          {min(stats['timing']['retrieve_ms']):.1f} ms")
        print(f"  Slowest:          {max(stats['timing']['retrieve_ms']):.1f} ms")

    if stats["timing"]["generate_ms"]:
        avg_generate = sum(stats["timing"]["generate_ms"]) / len(stats["timing"]["generate_ms"])
        print(f"\n[Generation Performance]")
        print(f"  Avg Time:         {avg_generate:.1f} ms ({avg_generate/1000:.1f} s)")
        print(f"  Fastest:          {min(stats['timing']['generate_ms']):.1f} ms")
        print(f"  Slowest:          {max(stats['timing']['generate_ms']):.1f} ms")

    # Error statistics
    if errors:
        print(f"\n[Error Categories]")
        for error, count in sorted(errors.items(), key=lambda x: -x[1]):
            print(f"  {count}x: {error}")

    # Failure reasons statistics
    if failure_reasons:
        print(f"\n[Failure Reasons (Top 10)]")
        for reason, count in sorted(failure_reasons.items(), key=lambda x: -x[1])[:10]:
            pct = count / stats['incorrect'] * 100 if stats['incorrect'] > 0 else 0
            print(f"  {count}x ({pct:.1f}%): {reason}...")

        # Show samples for top failure reasons
        if not quiet and failure_samples:
            print(f"\n[Failure Samples (Top 3 categories)]")
            top_reasons = sorted(failure_reasons.items(), key=lambda x: -x[1])[:3]
            for reason_key, _ in top_reasons:
                samples = failure_samples.get(reason_key, [])
                print(f"\n  Category: {reason_key}... ({len(samples)} samples)")
                for sample in samples[:2]:  # Show 2 samples per category
                    print(f"    [{sample['index']}] {sample['query']}...")
                    print(f"      Reason: {sample['reason']}...")

    # Check missing indices
    if not quiet and stats["by_index"]:
        indices = sorted(stats["by_index"].keys())
        if indices:
            min_idx, max_idx = min(indices), max(indices)
            missing = [i for i in range(min_idx, max_idx + 1) if i not in stats["by_index"]]
            if missing:
                print(f"\n[Missing Indices]")
                print(f"  Range: {min_idx} - {max_idx}")
                print(f"  Missing: {len(missing)} items")
                if len(missing) <= 20:
                    print(f"  Details: {missing}")
                else:
                    print(f"  Details: {missing[:10]} ... (total {len(missing)})")

    # Latest record
    if not quiet and all_entries:
        latest = all_entries[0]
        print(f"\n[Latest Record]")
        print(f"  Index:     {latest.get('index', 'N/A')}")
        print(f"  Timestamp: {latest.get('timestamp', 'N/A')}")
        print(f"  Query:     {latest.get('query', 'N/A')[:60]}...")
        if "evaluation" in latest:
            print(f"  Result:    {'PASS' if latest['evaluation'].get('is_correct') else 'FAIL'}")
            print(f"  Reason:    {latest['evaluation'].get('reason', 'N/A')[:60]}...")
        elif "error" in latest:
            print(f"  Error:     {latest.get('error', 'N/A')[:60]}...")

    print("=" * 80)

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Analyze Milvus evaluation logs and statistics generation quality",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=Path("custom_results"),
        help="Log file directory (default: custom_results)"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only show statistics, no details"
    )

    args = parser.parse_args()

    if not args.dir.exists():
        print(f"Error: Directory does not exist: {args.dir}")
        return

    analyze_logs(args.dir, args.quiet)


if __name__ == "__main__":
    main()
