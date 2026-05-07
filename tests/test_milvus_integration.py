"""Test Milvus KB + HTTP Embedding Integration"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from rag_service.clients.milvus_kb_client import MilvusKBClient, MilvusKBConfig
from rag_service.capabilities.milvus_kb_query import MilvusKBQuery, MilvusKBQueryInput
from rag_service.retrieval.embeddings import get_http_embedding_service
from rag_service.config import get_settings


async def test_integration():
    """Test complete Milvus KB + HTTP Embedding integration."""
    print("=" * 60)
    print("Milvus KB + HTTP Embedding Integration Test")
    print("=" * 60)
    print()

    # Check configuration
    settings = get_settings()

    print("Configuration:")
    print(f"  Milvus KB URI: {settings.milvus_kb.milvus_uri}")
    print(f"  Milvus KB Collection: {settings.milvus_kb.collection_name}")
    print(f"  Embedding Dimension: {settings.milvus_kb.embedding_dimension}")
    print(f"  Cloud Embedding URL: {settings.cloud_embedding.url}")
    print(f"  Cloud Embedding Model: {settings.cloud_embedding.model}")
    print()

    # Test 1: HTTP Embedding Service
    print("Test 1: HTTP Embedding Service")
    print("-" * 60)

    try:
        embedding_service = await get_http_embedding_service()
        test_query = "春节放假安排"
        vector = await embedding_service.embed_text(test_query)

        print(f"Query: {test_query}")
        print(f"Vector dimension: {len(vector)}")
        print(f"Model: {embedding_service.model}")
        print("HTTP Embedding: OK")
        print()

    except Exception as e:
        print(f"HTTP Embedding: FAILED - {e}")
        return

    # Test 2: Milvus Connection
    print("Test 2: Milvus Connection")
    print("-" * 60)

    try:
        config = MilvusKBConfig(
            milvus_uri=settings.milvus_kb.milvus_uri,
            collection_name="N000131_PublicDocDispatch",  # Use existing collection
        )
        client = MilvusKBClient(config)

        is_healthy = await client.health_check()
        print(f"Milvus Health: {'OK' if is_healthy else 'FAILED'}")

        if is_healthy:
            # List collections
            milvus_client = await client._get_client()
            collections = milvus_client.list_collections()
            # Handle both string and dict formats
            collection_names = []
            for c in collections:
                if isinstance(c, str):
                    collection_names.append(c)
                elif isinstance(c, dict):
                    collection_names.append(c.get("name", str(c)))
                else:
                    collection_names.append(str(c))
            print(f"Collections: {collection_names}")

        await client.close()
        print()

    except Exception as e:
        print(f"Milvus Connection: FAILED - {e}")
        import traceback
        traceback.print_exc()
        return

    # Test 3: Milvus KB Query with HTTP Embedding
    print("Test 3: Milvus KB Query with HTTP Embedding")
    print("-" * 60)

    try:
        # Initialize Milvus KB Query capability
        milvus_client = MilvusKBClient(config)
        embedding_service = await get_http_embedding_service()

        kb_query = MilvusKBQuery(
            milvus_client=milvus_client,
            embedding_service=embedding_service,
        )

        # Test query
        input_data = MilvusKBQueryInput(
            query="春节放假安排",
            limit=5,
            search_type="vector",  # Use vector search instead of hybrid
            trace_id="test-integration",
        )

        result = await kb_query.execute(input_data)

        print(f"Query: {input_data.query}")
        print(f"Search type: {result.search_type}")
        print(f"Retrieved: {result.retrieval_count} chunks")
        print(f"Timing: {result.timing_ms}ms")
        print()

        if result.chunks:
            print("Top results:")
            for i, chunk in enumerate(result.chunks[:3], 1):
                print(f"  {i}. [{chunk.id}] {chunk.content[:60]}...")
                print(f"     Score: {chunk.score:.4f} | Doc: {chunk.document_name or 'N/A'}")
        else:
            print("No chunks retrieved (collection may be empty)")

        await milvus_client.close()

    except Exception as e:
        print(f"Milvus KB Query: FAILED - {e}")
        import traceback
        traceback.print_exc()
        return

    print()
    print("=" * 60)
    print("Integration Test Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_integration())
