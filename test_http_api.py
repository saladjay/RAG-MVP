import asyncio
import httpx

async def test_http_api():
    url = "http://128.23.74.3:9091/llm/Qwen3-32B-Instruct/v1/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Basic T0EtZ3JvdXAtYXV0aDpPQS1ncm91cC1hdXRo"
    }
    payload = {
        "prompt": "你好，请问今天天气怎么样？",
        "max_tokens": 100,
        "temperature": 0.7,
        "model": "Qwen3-32B"
    }
    
    print(f"Testing HTTP API with httpx...")
    print(f"URL: {url}")
    print(f"Headers: {headers}")
    print(f"Payload: {payload}")
    
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, json=payload, headers=headers)
            print(f"\nResponse status: {response.status_code}")
            print(f"Response headers: {dict(response.headers)}")
            response.raise_for_status()
            data = response.json()
            print(f"\nResponse data:")
            import json
            print(json.dumps(data, ensure_ascii=False, indent=2))
            
            # Extract text
            if "choices" in data:
                text = data["choices"][0].get("text", "")
                print(f"\nGenerated text: {text}")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_http_api())
