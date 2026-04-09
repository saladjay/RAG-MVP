"""
Debug script for External Knowledge Base - Shows detailed request/response
"""
import asyncio
import httpx
import json

async def debug_external_kb():
    """Debug external KB with full request/response logging"""

    base_url = "http://128.23.77.226:6719"
    endpoint = "/cloudoa-ai/ai/file-knowledge/queryKnowledge"
    url = base_url + endpoint

    headers = {
        "Content-Type": "application/json",
        "xtoken": "12345fdsaga6"  # 从 .env 获取
    }

    payload = {
        "compId": "N000131",
        "fileType": "PublicDocDispatch",
        "query": "2025年春节放假共计几天？",
        "searchType": 1,
        "topk": 10,
    }

    print("=" * 60)
    print("External KB Debug")
    print("=" * 60)
    print(f"\n[REQUEST]")
    print(f"URL: {url}")
    print(f"Headers: {json.dumps(headers, indent=2)}")
    print(f"Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.post(url, json=payload, headers=headers)

            print(f"\n[RESPONSE]")
            print(f"Status: {response.status_code}")
            print(f"Headers: {dict(response.headers)}")

            data = response.json()
            print(f"\nBody:")
            print(json.dumps(data, indent=2, ensure_ascii=False))

            # 分析结果
            print(f"\n[ANALYSIS]")
            if data.get("code") == 200:
                chunks = data.get("data", [])
                print(f"Success: YES")
                print(f"Message: {data.get('msg')}")
                print(f"Chunk Count: {len(chunks)}")

                if chunks:
                    print(f"\nTop 3 Chunks:")
                    for i, chunk in enumerate(chunks[:3], 1):
                        meta = chunk.get("metadata", {})
                        print(f"  {i}. Doc: {meta.get('document_name', 'N/A')}")
                        print(f"     Score: {chunk.get('score', 0):.4f}")
                        content = chunk.get("content", "")[:100]
                        print(f"     Content: {content}...")
                else:
                    print(f"⚠️  No chunks returned!")
                    print(f"   Possible reasons:")
                    print(f"   - No documents in KB for this company/file type")
                    print(f"   - Query doesn't match any documents")
                    print(f"   - Search parameters incorrect")
            else:
                print(f"Success: NO")
                print(f"Error: {data}")

        except httpx.HTTPError as e:
            print(f"\n[ERROR]")
            print(f"HTTP Error: {e}")
        except Exception as e:
            print(f"\n[ERROR]")
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(debug_external_kb())
