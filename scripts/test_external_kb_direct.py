"""
Direct test script for External KB queries.

This script tests the first 10 queries from questions/fianl_version_qa.jsonl
directly against the external knowledge base, bypassing RAG Service.
"""

import asyncio
import json
import time
from typing import List, Dict, Any
from datetime import datetime

import httpx


# Configuration
EXTERNAL_KB_URL = "http://128.23.77.226:6719"
COMPANY_ID = "N000131"
FILE_TYPE = "PublicDocDispatch"
XTOKEN = "12345fdsaga6"  # Authentication token required by external KB

# First 10 queries from fianl_version_qa.jsonl
TEST_QUERIES = [
    "2025年春节放假共计几天？",
    "春节调休需上班日期是哪天？",
    "国庆中秋放假时长是几天？",
    "值班车辆牌号是什么？",
    "元旦放假是否安排调休？",
    "值班电话需保障通畅吗？",
    "2025年春节从哪天开始放假？",
    "节假日自家车要停在什么地方？",
    "值班期间手机必须24小时开机吗？",
    "清明节放假几天？",
]


async def test_external_kb_query(query: str) -> Dict[str, Any]:
    """Test a single query against external KB.

    Args:
        query: Query text

    Returns:
        Query result with chunks and timing
    """
    url = f"{EXTERNAL_KB_URL}/cloudoa-ai/ai/file-knowledge/queryKnowledge"

    payload = {
        "compId": COMPANY_ID,
        "fileType": FILE_TYPE,
        "query": query,
        "searchType": 1,
        "topk": 10,
    }

    start_time = time.time()

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "xtoken": XTOKEN,
                },
            )
            response.raise_for_status()
            data = response.json()

        latency_ms = (time.time() - start_time) * 1000

        # Extract chunks
        chunks = data.get("data", [])

        return {
            "query": query,
            "success": True,
            "latency_ms": latency_ms,
            "chunk_count": len(chunks),
            "chunks": chunks[:5],  # Keep top 5 for summary
        }

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        return {
            "query": query,
            "success": False,
            "error": str(e),
            "latency_ms": latency_ms,
            "chunk_count": 0,
        }


async def run_tests(queries: List[str]) -> List[Dict[str, Any]]:
    """Run tests for all queries.

    Args:
        queries: List of query strings

    Returns:
        List of test results
    """
    print(f"\n{'#' * 60}")
    print(f"# External Knowledge Base Query Test")
    print(f"{'#' * 60}")
    print(f"Date: {datetime.now().isoformat()}")
    print(f"External KB: {EXTERNAL_KB_URL}")
    print(f"Company ID: {COMPANY_ID}")
    print(f"File Type: {FILE_TYPE}")
    print(f"Total Queries: {len(queries)}")

    results = []

    for i, query in enumerate(queries, 1):
        print(f"\n{'=' * 60}")
        print(f"Query {i}/{len(queries)}: {query}")
        print(f"{'=' * 60}")

        result = await test_external_kb_query(query)
        results.append(result)

        if result["success"]:
            print(f"[PASS] Success: {result['chunk_count']} chunks returned")
            print(f"[TIME] Latency: {result['latency_ms']:.0f}ms")

            if result["chunks"]:
                print(f"\nTop chunks:")
                for j, chunk in enumerate(result["chunks"][:3], 1):
                    doc_name = chunk.get("metadata", {}).get("document_name", "N/A")
                    score = chunk.get("metadata", {}).get("score", 0)
                    content_preview = chunk.get("content", "")[:100].replace("\n", " ")
                    print(f"  {j}. {doc_name} (score: {score:.2f})")
                    print(f"     Preview: {content_preview}...")
            else:
                print("[FAIL] No chunks returned")
        else:
            print(f"[FAIL] Failed: {result.get('error', 'Unknown error')}")

        # Small delay between tests
        if i < len(queries):
            await asyncio.sleep(0.3)

    # Print summary
    print_summary(results)

    return results


def print_summary(results: List[Dict[str, Any]]) -> None:
    """Print test summary.

    Args:
        results: List of test results
    """
    print(f"\n\n{'#' * 60}")
    print(f"# Test Summary")
    print(f"{'#' * 60}")

    successful = sum(1 for r in results if r["success"])
    avg_latency = sum(r["latency_ms"] for r in results if r["success"]) / max(successful, 1)
    total_chunks = sum(r.get("chunk_count", 0) for r in results)

    print(f"\nResults:")
    print(f"  Total tests: {len(results)}")
    print(f"  Successful: {successful}")
    print(f"  Failed: {len(results) - successful}")
    print(f"  Total chunks: {total_chunks}")
    print(f"  Avg latency: {avg_latency:.0f}ms")

    # Detailed table
    print(f"\n{'-' * 80}")
    print(f"{'No.':<5} {'Query':<35} {'Status':<8} {'Chunks':<8} {'Latency':<10}")
    print(f"{'-' * 80}")

    for i, r in enumerate(results, 1):
        query_short = r["query"][:32] + "..." if len(r["query"]) > 35 else r["query"]
        status = "[PASS]" if r["success"] else "[FAIL]"
        chunks = str(r["chunk_count"]) if r["success"] else "N/A"
        latency = f"{r['latency_ms']:.0f}ms" if r["success"] else "N/A"
        print(f"{i:<5} {query_short:<35} {status:<10} {chunks:<8} {latency:<10}")

    print(f"{'-' * 80}")

    # Save results
    output_file = "external_kb_test_results_summary.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "config": {
                "external_kb_url": EXTERNAL_KB_URL,
                "company_id": COMPANY_ID,
                "file_type": FILE_TYPE,
            },
            "summary": {
                "total_tests": len(results),
                "successful": successful,
                "failed": len(results) - successful,
                "total_chunks": total_chunks,
                "avg_latency_ms": avg_latency,
            },
            "results": results,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n[FILE] Results saved to: {output_file}")


async def main():
    """Main entry point."""
    print("Starting External Knowledge Base Query Test...")
    print(f"Testing {len(TEST_QUERIES)} queries\n")

    await run_tests(TEST_QUERIES)


if __name__ == "__main__":
    asyncio.run(main())
