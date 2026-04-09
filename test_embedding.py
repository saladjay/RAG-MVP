"""Test HTTP Embedding Service"""
import asyncio
import sys
sys.path.insert(0, 'src')

from rag_service.config import get_settings
from rag_service.retrieval.embeddings import HTTPEmbeddingService, get_http_embedding_service

async def test():
    print("=" * 60)
    print("Testing HTTP Embedding Service")
    print("=" * 60)
    print()

    # Show configuration
    settings = get_settings()
    print("[Configuration]")
    print(f"URL: {settings.cloud_embedding.url}")
    print(f"Model: {settings.cloud_embedding.model}")
    print(f"Timeout: {settings.cloud_embedding.timeout}s")
    print(f"Enabled: {settings.cloud_embedding.enabled}")
    print()

    if not settings.cloud_embedding.enabled:
        print("ERROR: Cloud embedding is not configured!")
        print("Set CLOUD_EMBEDDING_URL environment variable.")
        return

    # Test single text embedding
    print("[Test 1/2] Single text embedding")
    try:
        service = await get_http_embedding_service()
        print(f"Service: {service}")

        test_text = "测试中文文本embedding"
        print(f"Text: {test_text}")
        print()

        vector = await service.embed_text(test_text)

        print(f"SUCCESS!")
        print(f"  Dimension: {len(vector)}")
        print(f"  Vector (first 5): {vector[:5]}")
        print(f"  Cache size: {service.get_cache_size()}")
        print()

    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()
        return

    # Test batch embedding
    print("[Test 2/2] Batch embedding")
    try:
        texts = [
            "第一段测试文本",
            "第二段测试文本",
            "第三段测试文本",
        ]

        print(f"Texts: {len(texts)}")
        print()

        vectors = await service.embed_batch(texts)

        print(f"SUCCESS!")
        print(f"  Generated: {len(vectors)} vectors")
        for i, v in enumerate(vectors):
            print(f"  Vector {i+1}: dimension={len(v)}, first_3={v[:3]}")

    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()

    print()
    print("=" * 60)
    print("Test complete")
    print("=" * 60)

asyncio.run(test())
