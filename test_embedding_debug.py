"""Debug HTTP Embedding Response"""
import asyncio
import httpx

async def test():
    url = "http://128.23.74.3:9091/llm/embed-bge/v1/embeddings"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Basic T0EtZ3JvdXAtYXV0aDpPQS1ncm91cC1hdXRo"
    }
    payload = {
        "input": ["测试文本"],
        "model": "bge-m3"
    }

    print(f"URL: {url}")
    print(f"Payload: {payload}")
    print()

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, json=payload, headers=headers)
        print(f"Status: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        print()
        print(f"Response:")
        print(response.text)

asyncio.run(test())
