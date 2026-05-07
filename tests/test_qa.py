"""简单的QA测试脚本"""
import asyncio
import httpx
import json

async def test_qa():
    url = "http://localhost:8000/qa/query"
    
    # 测试查询
    payload = {
        "query": "实习生",
        "context": {
            "company_id": "N000131",
            "file_type": 'PublicDocReceive'
        }
    }
    
    print("=" * 60)
    print("测试查询:", payload["query"])
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(url, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            print("\n[SUCCESS] Query successful")
            print("\nAnswer:")
            print(data['answer'])
            print(f"\nSources count: {len(data['sources'])}")
            
            # 显示时序
            timing = data['metadata']['timing_ms']
            print(f"\nTiming:")
            print(f"  - Retrieval: {timing['retrieve_ms']:.0f}ms")
            print(f"  - Generation: {timing['generate_ms']:.0f}ms")
            print(f"  - Total: {timing['total_ms']:.0f}ms")
        else:
            print(f"[ERROR] Query failed: {response.status_code}")
            print(response.text)

if __name__ == "__main__":
    asyncio.run(test_qa())
