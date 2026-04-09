"""Simple QA test without external KB dependency."""

import asyncio
import httpx


async def test_qa_without_kb():
    """Test QA with mock knowledge (no external KB)."""
    url = "http://localhost:8000/qa/query"

    # Test with a simple question
    payload = {
        "query": "什么是人工智能？",
        "context": {
            "company_id": "N000131",
            "file_type": "PublicDocDispatch"
        },
        "options": {
            "enable_query_rewrite": False,
            "enable_hallucination_check": False,
            "top_k": 3
        }
    }

    print("=" * 60)
    print("Testing QA Pipeline (without external KB)")
    print("=" * 60)

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
                print("\n[SUCCESS]")
                print(f"Answer: {data.get('answer', 'N/A')}")
                print(f"Sources: {len(data.get('sources', []))}")
            else:
                print(f"\n[ERROR]")
                print(f"Response: {response.text}")

    except Exception as e:
        print(f"\n[ERROR] {e}")


if __name__ == "__main__":
    asyncio.run(test_qa_without_kb())
