"""Simple test of Milvus KB with correct field names"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from pymilvus import MilvusClient
from rag_service.retrieval.embeddings import get_http_embedding_service

async def main():
    # Connect to Milvus
    client = MilvusClient(uri="http://localhost:19530")

    # Get embedding
    embedding_service = await get_http_embedding_service()
    query = "李志杰"
    query_vector = await embedding_service.embed_text(query)

    print(f"Query: {query}")
    print(f"Vector dimension: {len(query_vector)}")
    print()

    # Search in knowledge_base collection (the one we created)
    collection_name = "knowledge_base"
    print(f"Searching in: {collection_name}")
    print()

    try:
        # First, let's check if collection exists and get its stats
        if client.has_collection(collection_name):
            stats = client.get_collection_stats(collection_name)
            row_count = stats.get("row_count", 0)
            print(f"Collection has {row_count} rows")
            print()

            if row_count == 0:
                print("Collection is empty. No results to search.")
                return

        results = client.search(
            collection_name=collection_name,
            data=[query_vector],
            limit=5,
            output_fields=["fileContent", "formTitle", "document_id", "chunk_index"],
        )

        print(f"Found {len(results[0])} results:")
        for hit in results[0]:
            entity = hit["entity"]
            distance = hit["distance"]
            print(f"  - Distance: {distance:.4f}")
            print(f"    Title: {entity.get('formTitle', 'N/A')[:80]}")
            print(f"    Content: {entity.get('fileContent', 'N/A')[:100]}...")
            print(f"    Document ID: {entity.get('document_id', 'N/A')}")
            print(f"    Chunk Index: {entity.get('chunk_index', 'N/A')}")
            print()

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

    # try:
    #     results = client.search(
    #         collection_name=collection_name,
    #         data=[],
    #         search_params = {
    #             "bm25":{
    #                 "field_name": "text",
    #                 "query": "李志杰"
    #             }
    #         },
    #         limit=10,
    #         anns_field="fileContent_vector",  # Specify which vector field to use
    #     )
    # except Exception as e:
    #     print(f"Error: {e}")
    #     import traceback
    #     traceback.print_exc()

async def bm25_search():
    pass

if __name__ == "__main__":
    asyncio.run(main())
