"""Test chain logging"""
import asyncio
import httpx

async def test():
    url = "http://localhost:8000/qa/query"
    
    payload = {
        "query": "2025年春节放假共计几天？",
        "context": {
            "company_id": "N000131",
            "file_type": "PublicDocDispatch"
        },
        "options": {
            "enable_query_rewrite": True,
            "enable_hallucination_check": False,
            "top_k": 3
        }
    }
    
    print("Testing QA pipeline with chain logging...")
    print("Logs will be saved to: logs/chain_trace.jsonl")
    print()
    
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(url, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            print("Query successful!")
            print(f"Answer: {data['answer'][:100]}...")
            print(f"Sources: {data['metadata']['timing_ms']}")
        else:
            print(f"Query failed: {response.status_code}")
            print(response.text)
    
    print()
    print("Check logs/chain_trace.jsonl for full chain trace")

asyncio.run(test())
