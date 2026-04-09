"""Test RAG Service QA endpoint with external KB."""

import asyncio
import httpx
import json


async def test_qa_query():
    """Test QA query endpoint."""
    url = "http://localhost:8000/qa/query"

    payload = {
        "query": "2025年春节放假共计几天？",
        "context": {
            "company_id": "N000131",
            "file_type": "PublicDocDispatch"
        },
        "options": {
            "enable_query_rewrite": False,
            "enable_hallucination_check": False,
            "top_k": 5
        }
    }

    print("=" * 60)
    print("Testing RAG Service QA Endpoint")
    print("=" * 60)
    print(f"URL: {url}")
    print(f"Query: {payload['query']}")
    print("-" * 60)

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )

            print(f"Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print("\n[SUCCESS] Response received!")
                print(f"\nAnswer:\n{data.get('answer', 'N/A')}")

                if 'sources' in data:
                    print(f"\nSources: {len(data['sources'])} chunks")
                    for i, source in enumerate(data['sources'][:3], 1):
                        metadata = source.get('metadata', {})
                        doc_name = metadata.get('doc_metadata', {}).get('doctype', 'N/A')
                        score = source.get('score', 0)
                        print(f"  {i}. {doc_name} (score: {score:.2f})")

                if 'metadata' in data:
                    meta = data['metadata']
                    print(f"\nMetadata:")
                    if 'timing' in meta:
                        timing = meta['timing']
                        print(f"  - Retrieval: {timing.get('retrieval_ms', 0):.0f}ms")
                        print(f"  - Generation: {timing.get('generation_ms', 0):.0f}ms")
            else:
                print(f"\n[ERROR] Request failed")
                print(f"Response: {response.text}")

    except Exception as e:
        print(f"\n[ERROR] {e}")


if __name__ == "__main__":
    asyncio.run(test_qa_query())
