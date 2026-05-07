"""Test Milvus KB Query Capability"""
import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from rag_service.capabilities.milvus_kb_query import (
    MilvusKBQuery,
    MilvusKBQueryInput,
    get_milvus_kb_query,
)


async def test_milvus_kb_query():
    """Test Milvus KB query capability"""
    print("=" * 60)
    print("Milvus KB Query Capability Test")
    print("=" * 60)
    print("\nNOTE: Make sure MILVUS_KB_URI is set in .env file")
    print()

    try:
        # Get the global Milvus KB query capability
        kb_query = await get_milvus_kb_query()

        print("Milvus KB Query capability initialized successfully")
        print(f"Collection: {kb_query._milvus_client._config.collection_name}")
        print(f"URI: {kb_query._milvus_client._config.milvus_uri}")
        print()

        # Test queries
        test_queries = [
            "节日放假安排",
            "公司报销流程",
            "年假政策",
        ]

        for query in test_queries:
            print("-" * 60)
            print(f"Query: {query}")
            print("-" * 60)

            # Test hybrid search
            input_data = MilvusKBQueryInput(
                query=query,
                limit=5,
                search_type="hybrid",
                trace_id=f"test-{query[:3]}",
            )

            result = await kb_query.execute(input_data)

            print(f"Search type: {result.search_type}")
            print(f"Retrieved: {result.retrieval_count} chunks")
            print(f"Timing: {result.timing_ms}ms")
            print()

            for i, chunk in enumerate(result.chunks, 1):
                print(f"  {i}. [{chunk.id}] {chunk.content[:80]}...")
                print(f"     Score: {chunk.score:.4f} | Doc: {chunk.document_name or 'N/A'}")
                print()

    except ImportError as e:
        print(f"Import error: {e}")
        print("\nPlease install pymilvus:")
        print("  uv add pymilvus")

    except RuntimeError as e:
        print(f"Configuration error: {e}")
        print("\nPlease set MILVUS_KB_URI in .env file:")
        print("  MILVUS_KB_URI=http://192.168.xxx.xxx:19530")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_milvus_kb_query())
