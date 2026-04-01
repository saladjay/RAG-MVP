"""
Direct test script for external KB service.
This script bypasses e2e_test module and directly uses ExternalKBClient.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


async def test_external_kb():
    """Test external KB directly."""
    from rag_service.clients.external_kb_client import ExternalKBClient, ExternalKBClientConfig

    # Configuration
    base_url = "http://128.23.77.226:6719"
    endpoint = "/cloudoa-ai/ai/file-knowledge/queryKnowledge"
    comp_id = "N000131"
    file_type = "PublicDocDispatch"

    print(f"Testing External KB:")
    print(f"  URL: {base_url}{endpoint}")
    print(f"  Comp ID: {comp_id}")
    print("-" * 50)

    # Create client
    config = ExternalKBClientConfig(
        base_url=base_url,
        endpoint=endpoint,
        timeout=30,
        max_retries=3,
    )
    client = ExternalKBClient(config)

    # Test queries
    queries = [
        "2025年春节放假共计几天",
        "春节调休需上班日期是哪天",
        "test",
    ]

    results = []

    for idx, query in enumerate(queries, 1):
        print(f"\nTest {idx}: {query}")
        try:
            chunks = await client.query(
                query=query,
                comp_id=comp_id,
                file_type=file_type,
                search_type=1,
                topk=5,
            )

            print(f"  [OK] Success: {len(chunks)} chunks retrieved")

            if chunks:
                for i, chunk in enumerate(chunks[:2], 1):
                    print(f"    Chunk {i}: {chunk.get('content', '')[:100]}...")

            results.append({
                "query": query,
                "success": True,
                "chunk_count": len(chunks),
                "chunks": chunks[:2],  # Keep first 2 chunks
            })

        except Exception as e:
            print(f"  [FAIL] Error: {e}")
            results.append({
                "query": query,
                "success": False,
                "error": str(e),
            })

    # Save results
    output_file = Path("external_kb_direct_test_results.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "config": {
                "base_url": base_url,
                "endpoint": endpoint,
                "comp_id": comp_id,
                "file_type": file_type,
            },
            "total_tests": len(queries),
            "successful": sum(1 for r in results if r["success"]),
            "failed": sum(1 for r in results if not r["success"]),
            "results": results,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n{'-' * 50}")
    print(f"Summary:")
    print(f"  Total: {len(queries)}")
    print(f"  Successful: {sum(1 for r in results if r['success'])}")
    print(f"  Failed: {sum(1 for r in results if not r['success'])}")
    print(f"  Results saved to: {output_file}")

    await client.close()

    return 0 if all(r["success"] for r in results) else 1


if __name__ == "__main__":
    exit_code = asyncio.run(test_external_kb())
    sys.exit(exit_code)
