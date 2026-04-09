"""
Compare External HTTP KB vs Internal Milvus KB

This script demonstrates how to compare retrieval results between:
1. External HTTP Knowledge Base (current implementation)
2. Internal Milvus Knowledge Base (new implementation)

Usage:
    1. Set MILVUS_KB_URI in .env to your Milvus address
    2. Run this script: uv run python compare_kb_methods.py
"""
import asyncio
import sys
import os
import time
from typing import List, Dict, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from rag_service.clients.external_kb_client import get_external_kb_client
from rag_service.capabilities.milvus_kb_query import MilvusKBQuery, MilvusKBQueryInput
from rag_service.core.exceptions import RetrievalError


async def query_external_kb(query: str, top_k: int = 5) -> Dict[str, Any]:
    """Query external HTTP knowledge base."""
    print(f"\n[External HTTP KB] Query: {query}")
    print("-" * 60)

    try:
        kb_client = await get_external_kb_client()
        start_time = time.time()

        result = await kb_client.query(
            query=query,
            top_k=top_k,
            trace_id=f"compare-external-{query[:3]}",
        )

        elapsed_ms = int((time.time() - start_time) * 1000)

        print(f"Retrieved: {len(result.chunks)} chunks")
        print(f"Timing: {elapsed_ms}ms")
        print(f"Query rewritten: {result.query_rewritten}")

        for i, chunk in enumerate(result.chunks, 1):
            print(f"  {i}. [{chunk.chunk_id}] {chunk.content[:80]}...")
            print(f"     Score: {chunk.score:.4f}")

        return {
            "method": "external_http",
            "query": query,
            "retrieval_count": len(result.chunks),
            "timing_ms": elapsed_ms,
            "query_rewritten": result.query_rewritten,
            "chunks": [
                {
                    "id": c.chunk_id,
                    "content": c.content[:100],
                    "score": c.score,
                }
                for c in result.chunks
            ],
        }

    except Exception as e:
        print(f"Error: {e}")
        return {"error": str(e)}


async def query_milvus_kb(query: str, search_type: str = "hybrid", limit: int = 5) -> Dict[str, Any]:
    """Query internal Milvus knowledge base."""
    print(f"\n[Internal Milvus KB] Query: {query}")
    print(f"Search type: {search_type}")
    print("-" * 60)

    try:
        # Initialize Milvus KB query
        from rag_service.clients.milvus_kb_client import MilvusKBClient, MilvusKBConfig
        from rag_service.retrieval.embeddings import get_http_embedding_service
        from rag_service.config import get_settings

        settings = get_settings()

        if not settings.milvus_kb.enabled:
            raise RuntimeError("Milvus KB not configured. Set MILVUS_KB_URI in .env")

        milvus_client = MilvusKBClient(
            MilvusKBConfig(
                milvus_uri=settings.milvus_kb.milvus_uri,
                collection_name=settings.milvus_kb.collection_name,
            )
        )
        embedding_service = await get_http_embedding_service()

        kb_query = MilvusKBQuery(
            milvus_client=milvus_client,
            embedding_service=embedding_service,
        )

        # Test different search types
        input_data = MilvusKBQueryInput(
            query=query,
            limit=limit,
            search_type=search_type,
            trace_id=f"compare-milvus-{query[:3]}",
        )

        start_time = time.time()
        result = await kb_query.execute(input_data)
        elapsed_ms = int((time.time() - start_time) * 1000)

        print(f"Retrieved: {result.retrieval_count} chunks")
        print(f"Timing: {elapsed_ms}ms")

        for i, chunk in enumerate(result.chunks, 1):
            print(f"  {i}. [{chunk.id}] {chunk.content[:80]}...")
            print(f"     Score: {chunk.score:.4f} | Doc: {chunk.document_name or 'N/A'}")

        return {
            "method": f"milvus_{search_type}",
            "query": query,
            "retrieval_count": result.retrieval_count,
            "timing_ms": elapsed_ms,
            "chunks": [
                {
                    "id": c.id,
                    "content": c.content[:100],
                    "score": c.score,
                    "document_name": c.document_name,
                }
                for c in result.chunks
            ],
        }

    except Exception as e:
        print(f"Error: {e}")
        return {"error": str(e)}


async def compare_kb_methods(queries: List[str]):
    """Compare retrieval results between KB methods."""
    print("=" * 60)
    print("Knowledge Base Comparison")
    print("=" * 60)
    print(f"\nTesting {len(queries)} queries...\n")

    results = []

    for query in queries:
        print(f"\n{'=' * 60}")
        print(f"Query: {query}")
        print("=" * 60)

        # External HTTP KB
        external_result = await query_external_kb(query, top_k=5)
        results.append(external_result)

        # Milvus KB - try different search types
        for search_type in ["vector", "keyword", "hybrid"]:
            milvus_result = await query_milvus_kb(query, search_type=search_type, limit=5)
            results.append(milvus_result)

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    for r in results:
        if "error" not in r:
            method = r["method"]
            count = r["retrieval_count"]
            timing = r["timing_ms"]
            print(f"{method:20} | {count:3} chunks | {timing:4}ms")

    return results


async def main():
    """Main comparison function."""
    # Test queries
    queries = [
        "节日放假安排",
        "公司报销流程",
        "年假政策",
    ]

    results = await compare_kb_methods(queries)

    # Save results to JSON
    import json
    output_file = "kb_comparison_results.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    print("\nNote: Make sure both KB systems are configured:")
    print("  1. External KB: EXTERNAL_KB_BASE_URL in .env")
    print("  2. Milvus KB: MILVUS_KB_URI in .env")
    print()

    asyncio.run(main())
