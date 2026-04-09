"""
Direct test of the embedding service to diagnose 502 errors.

This script mimics exactly how the RAG service calls the embedding service:
- Uses httpx AsyncClient with same timeout
- Uses same headers (Content-Type, Authorization)
- Uses same payload format
"""

import asyncio
import json
import sys
import time
from typing import List, Dict, Any

# Windows console encoding fix
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import httpx


# Configuration from .env
EMBEDDING_URL = "http://128.23.74.3:9091/llm/embed-bge/v1/embeddings"
EMBEDDING_MODEL = "bge-m3"
EMBEDDING_TIMEOUT = 120
EMBEDDING_AUTH_TOKEN = "T0EtZ3JvdXAtYXV0aDpPQS1ncm91cC1hdXRo"


async def test_embedding_service() -> None:
    """Test the embedding service with various scenarios."""

    print("=" * 60)
    print("Embedding Service Direct Test")
    print("=" * 60)
    print(f"URL: {EMBEDDING_URL}")
    print(f"Model: {EMBEDDING_MODEL}")
    print(f"Timeout: {EMBEDDING_TIMEOUT}s")
    print(f"Auth Token: {EMBEDDING_AUTH_TOKEN[:20]}...")
    print("=" * 60)

    # Test scenarios
    test_texts = [
        "Hello, world!",  # Simple short text
        "This is a longer text with more content to test the embedding service.",  # Medium text
        "测试中文文本的embedding功能",  # Chinese text
        "A" * 1000,  # Long text
    ]

    # Test 1: Single text embedding
    print("\n[Test 1] Single text embedding")
    print("-" * 40)
    await test_single_embedding(test_texts[0])

    # Test 2: Batch embedding (small batch)
    print("\n[Test 2] Batch embedding (3 texts)")
    print("-" * 40)
    await test_batch_embedding(test_texts[:3])

    # Test 3: Larger batch (like real upload scenario)
    print("\n[Test 3] Large batch (10 texts)")
    print("-" * 40)
    large_batch = [f"Chunk {i} content: " + " ".join([f"word{j}" for j in range(50)]) for i in range(10)]
    await test_batch_embedding(large_batch)

    # Test 4: Very long text (simulating document chunk)
    print("\n[Test 4] Very long text (2000 chars)")
    print("-" * 40)
    long_text = " ".join([f"word{i}" for i in range(500)])
    await test_single_embedding(long_text)

    # Test 5: Concurrent requests (like during batch upload)
    print("\n[Test 5] Concurrent requests (5 parallel)")
    print("-" * 40)
    await test_concurrent_requests(5)

    # Test 6: Rapid sequential requests
    print("\n[Test 6] Rapid sequential requests (10 in a row)")
    print("-" * 40)
    await test_sequential_requests(10)

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


async def test_single_embedding(text: str) -> None:
    """Test embedding a single text."""
    client = httpx.AsyncClient(timeout=EMBEDDING_TIMEOUT)

    headers = {
        "Content-Type": "application/json",
    }
    if EMBEDDING_AUTH_TOKEN:
        headers["Authorization"] = f"Basic {EMBEDDING_AUTH_TOKEN}"

    payload = {
        "input": text,
        "model": EMBEDDING_MODEL,
    }

    start_time = time.time()

    try:
        response = await client.post(
            EMBEDDING_URL,
            json=payload,
            headers=headers,
        )

        latency_ms = (time.time() - start_time) * 1000

        print(f"Status: {response.status_code}")
        print(f"Latency: {latency_ms:.0f}ms")

        if response.status_code == 200:
            data = response.json()
            if "data" in data:
                embedding = data["data"][0]["embedding"]
                print(f"Vector dimension: {len(embedding)}")
                print(f"First 5 values: {embedding[:5]}")
            elif "embeddings" in data:
                embedding = data["embeddings"][0]
                print(f"Vector dimension: {len(embedding)}")
                print(f"First 5 values: {embedding[:5]}")
            print("[OK] Single embedding succeeded")
        else:
            print(f"[FAILED] HTTP {response.status_code}: {response.text[:200]}")

    except httpx.HTTPStatusError as e:
        print(f"[FAILED] HTTPStatusError: {e.response.status_code}")
        print(f"Response: {e.response.text[:200]}")
    except httpx.ConnectError as e:
        print(f"[FAILED] Connection error: {e}")
    except httpx.TimeoutException:
        print(f"[FAILED] Timeout after {EMBEDDING_TIMEOUT}s")
    except Exception as e:
        print(f"[FAILED] Error: {e}")
    finally:
        await client.aclose()


async def test_batch_embedding(texts: List[str]) -> None:
    """Test embedding multiple texts in a single request."""
    client = httpx.AsyncClient(timeout=EMBEDDING_TIMEOUT)

    headers = {
        "Content-Type": "application/json",
    }
    if EMBEDDING_AUTH_TOKEN:
        headers["Authorization"] = f"Basic {EMBEDDING_AUTH_TOKEN}"

    payload = {
        "input": texts,
        "model": EMBEDDING_MODEL,
    }

    start_time = time.time()

    try:
        response = await client.post(
            EMBEDDING_URL,
            json=payload,
            headers=headers,
        )

        latency_ms = (time.time() - start_time) * 1000

        print(f"Batch size: {len(texts)}")
        print(f"Status: {response.status_code}")
        print(f"Latency: {latency_ms:.0f}ms")
        print(f"Avg per text: {latency_ms/len(texts):.0f}ms")

        if response.status_code == 200:
            data = response.json()
            if "data" in data:
                embeddings = data["data"]
                print(f"Received embeddings: {len(embeddings)}")
                print(f"Vector dimension: {len(embeddings[0]['embedding'])}")
            elif "embeddings" in data:
                embeddings = data["embeddings"]
                print(f"Received embeddings: {len(embeddings)}")
                print(f"Vector dimension: {len(embeddings[0])}")
            print("[OK] Batch embedding succeeded")
        else:
            print(f"[FAILED] HTTP {response.status_code}: {response.text[:200]}")

    except httpx.HTTPStatusError as e:
        print(f"[FAILED] HTTPStatusError: {e.response.status_code}")
        print(f"Response: {e.response.text[:200]}")
    except httpx.ConnectError as e:
        print(f"[FAILED] Connection error: {e}")
    except httpx.TimeoutException:
        print(f"[FAILED] Timeout after {EMBEDDING_TIMEOUT}s")
    except Exception as e:
        print(f"[FAILED] Error: {e}")
    finally:
        await client.aclose()


async def test_concurrent_requests(count: int) -> None:
    """Test multiple concurrent embedding requests."""
    async def make_request(client: httpx.AsyncClient, text: str, idx: int) -> Dict[str, Any]:
        """Make a single embedding request."""
        headers = {
            "Content-Type": "application/json",
        }
        if EMBEDDING_AUTH_TOKEN:
            headers["Authorization"] = f"Basic {EMBEDDING_AUTH_TOKEN}"

        payload = {
            "input": text,
            "model": EMBEDDING_MODEL,
        }

        start_time = time.time()

        try:
            response = await client.post(
                EMBEDDING_URL,
                json=payload,
                headers=headers,
            )

            latency_ms = (time.time() - start_time) * 1000

            return {
                "index": idx,
                "status": response.status_code,
                "latency_ms": latency_ms,
                "success": response.status_code == 200,
                "error": None if response.status_code == 200 else response.text[:100],
            }
        except Exception as e:
            return {
                "index": idx,
                "status": 0,
                "latency_ms": 0,
                "success": False,
                "error": str(e),
            }

    client = httpx.AsyncClient(timeout=EMBEDDING_TIMEOUT)

    try:
        texts = [f"Concurrent request {i}: {text}" for i, text in enumerate(["Test content"] * count)]

        start_time = time.time()

        # Make concurrent requests
        tasks = [make_request(client, text, i) for i, text in enumerate(texts)]
        results = await asyncio.gather(*tasks)

        total_latency = (time.time() - start_time) * 1000

        # Analyze results
        successful = sum(1 for r in results if r["success"])
        failed = count - successful

        print(f"Concurrent requests: {count}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print(f"Total time: {total_latency:.0f}ms")

        if successful > 0:
            latencies = [r["latency_ms"] for r in results if r["success"]]
            print(f"Avg latency: {sum(latencies)/len(latencies):.0f}ms")
            print(f"Min latency: {min(latencies):.0f}ms")
            print(f"Max latency: {max(latencies):.0f}ms")

        if failed > 0:
            print("\nFailed requests:")
            for r in results:
                if not r["success"]:
                    print(f"  [{r['index']}] {r['error']}")
        else:
            print("[OK] All concurrent requests succeeded")

    finally:
        await client.aclose()


async def test_sequential_requests(count: int) -> None:
    """Test rapid sequential embedding requests."""
    client = httpx.AsyncClient(timeout=EMBEDDING_TIMEOUT)

    headers = {
        "Content-Type": "application/json",
    }
    if EMBEDDING_AUTH_TOKEN:
        headers["Authorization"] = f"Basic {EMBEDDING_AUTH_TOKEN}"

    try:
        start_time = time.time()
        successful = 0
        failed = 0

        for i in range(count):
            payload = {
                "input": f"Sequential request {i}",
                "model": EMBEDDING_MODEL,
            }

            try:
                response = await client.post(
                    EMBEDDING_URL,
                    json=payload,
                    headers=headers,
                )

                if response.status_code == 200:
                    successful += 1
                else:
                    failed += 1
                    print(f"  [{i}] Failed: HTTP {response.status_code}")

            except Exception as e:
                failed += 1
                print(f"  [{i}] Failed: {str(e)[:100]}")

        total_latency = (time.time() - start_time) * 1000

        print(f"Sequential requests: {count}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print(f"Total time: {total_latency:.0f}ms")
        print(f"Avg per request: {total_latency/count:.0f}ms")

        if failed == 0:
            print("[OK] All sequential requests succeeded")
        else:
            print(f"[FAILED] {failed} requests failed")

    finally:
        await client.aclose()


if __name__ == "__main__":
    try:
        asyncio.run(test_embedding_service())
    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Test stopped by user")
    except Exception as e:
        print(f"\n\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
