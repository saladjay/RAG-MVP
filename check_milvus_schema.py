"""Check Milvus Collection Schema"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from pymilvus import MilvusClient

# Connect to Milvus
client = MilvusClient(uri="http://128.23.74.1:19530")

# List collections
collections = client.list_collections()
print("Collections:", collections)
print()

# Check schema for each collection
for collection_name in collections[:5]:  # Check first 5
    print(f"=== {collection_name} ===")
    try:
        # Get collection description
        desc = client.describe_collection(collection_name)
        print(f"Fields: {desc.get('fields', [])}")
        print()
    except Exception as e:
        print(f"Error: {e}")
        print()
