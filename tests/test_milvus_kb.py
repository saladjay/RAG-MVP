"""Test Milvus KB Client"""
import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from rag_service.clients.milvus_kb_client import MilvusKBClient, MilvusKBConfig
from rag_service.retrieval.embeddings import get_http_embedding_service


async def test_connection():
    """Test Milvus connection"""
    print("=" * 60)
    print("Test 1: Milvus Connection")
    print("=" * 60)

    # Update this to your actual Milvus URI
    config = MilvusKBConfig(
        milvus_uri="http://192.168.1.100:19530",
        collection_name="knowledge_base",
    )

    client = MilvusKBClient(config)

    try:
        is_healthy = await client.health_check()
        print(f"Health check: {'PASS' if is_healthy else 'FAIL'}")

        if is_healthy:
            print("Collections:", await client._get_client())
            print("Collections list:", (await client._get_client()).list_collections())

    except Exception as e:
        print(f"Connection failed: {e}")
        return False

    await client.close()
    return True


async def test_embedding():
    """Test embedding service"""
    print("\n" + "=" * 60)
    print("Test 2: HTTP Embedding Service")
    print("=" * 60)

    try:
        embedding_service = get_http_embedding_service()
        result = await embedding_service.embed_text("测试查询")

        print(f"Embedding dimension: {len(result.vector)}")
        print(f"First 5 values: {result.vector[:5]}")

        return result.vector

    except Exception as e:
        print(f"Embedding failed: {e}")
        return None


async def test_vector_search(query_vector):
    """Test vector search"""
    print("\n" + "=" * 60)
    print("Test 3: Vector Search")
    print("=" * 60)

    config = MilvusKBConfig(
        milvus_uri="http://192.168.1.100:19530",
        collection_name="knowledge_base",
    )

    client = MilvusKBClient(config)

    try:
        results = await client.search(
            query_vector=query_vector,
            query_text="",
            limit=5,
            search_type="vector"
        )

        print(f"Found {len(results)} results (nested lists)")

        # Handle nested results format
        count = 0
        for result_list in results:
            for result in result_list:
                entity = result.get("entity", {})
                distance = result.get("distance", 0.0)
                print(f"  - [{entity.get('id', 'N/A')}] {entity.get('content', 'N/A')[:50]}... (score: {distance:.4f})")
                count += 1

        print(f"Total results: {count}")

    except Exception as e:
        print(f"Vector search failed: {e}")
        import traceback
        traceback.print_exc()

    await client.close()


async def test_hybrid_search(query_vector):
    """Test hybrid search"""
    print("\n" + "=" * 60)
    print("Test 4: Hybrid Search")
    print("=" * 60)

    config = MilvusKBConfig(
        milvus_uri="http://192.168.1.100:19530",
        collection_name="knowledge_base",
    )

    client = MilvusKBClient(config)

    try:
        results = await client.search(
            query_vector=query_vector,
            query_text="测试",
            limit=5,
            search_type="hybrid"
        )

        print(f"Hybrid search completed")

        count = 0
        for result_list in results:
            for result in result_list:
                entity = result.get("entity", {})
                distance = result.get("distance", 0.0)
                print(f"  - [{entity.get('id', 'N/A')}] {entity.get('content', 'N/A')[:50]}... (score: {distance:.4f})")
                count += 1

        print(f"Total results: {count}")

    except Exception as e:
        print(f"Hybrid search failed: {e}")
        import traceback
        traceback.print_exc()

    await client.close()


async def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("Milvus KB Client Test Suite")
    print("=" * 60)
    print("\nNOTE: Update MILVUS_URI in this script to your actual Milvus address")
    print("Current URI: http://192.168.1.100:19530")
    print()

    # Test 1: Connection
    connected = await test_connection()
    if not connected:
        print("\nCannot proceed with other tests - connection failed")
        return

    # Test 2: Embedding
    query_vector = await test_embedding()
    if not query_vector:
        print("\nCannot proceed with vector search - embedding failed")
        return

    # Test 3: Vector Search
    await test_vector_search(query_vector)

    # Test 4: Hybrid Search
    await test_hybrid_search(query_vector)

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
