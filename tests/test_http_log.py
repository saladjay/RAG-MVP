"""Test HTTP logging feature"""
import asyncio
import sys
sys.path.insert(0, 'src')

from rag_service.clients.external_kb_client import get_external_kb_client

async def test():
    print("Testing external KB with HTTP logging...")
    print("Logs will be saved to: logs/external_kb_http.jsonl")
    print()

    client = await get_external_kb_client()

    # Make a test query
    chunks = await client.query(
        query="2025年春节放假共计几天？",
        comp_id="N000131",
        file_type="PublicDocDispatch",
        search_type=1,
        topk=3
    )

    print(f"Query completed: {len(chunks)} chunks retrieved")
    print()
    print("Check logs/external_kb_http.jsonl for full HTTP request/response details")

    await client.close()

asyncio.run(test())
