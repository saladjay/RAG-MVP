"""Check Milvus collection status and list available collections"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from pymilvus import MilvusClient

def main():
    # Connect to Milvus
    client = MilvusClient(uri="http://localhost:19530")

    print("=" * 60)
    print("Milvus Collection Status")
    print("=" * 60)

    # List all collections
    collections = client.list_collections()
    print(f"\nAvailable collections ({len(collections)}):")
    for c in collections:
        print(f"  - {c}")

    # Check knowledge_base collection
    collection_name = "knowledge_base"
    if collection_name in collections:
        print(f"\n" + "=" * 60)
        print(f"Collection: {collection_name}")
        print("=" * 60)

        # Get description
        desc = client.describe_collection(collection_name)
        print(f"\nSchema fields:")
        for field in desc.get("fields", []):
            field_name = field.get("name")
            field_type = field.get("type")
            type_map = {
                1: 'BOOL', 2: 'INT8', 3: 'INT16', 4: 'INT32', 5: 'INT64',
                10: 'FLOAT', 11: 'DOUBLE', 20: 'STRING', 21: 'VARCHAR',
                23: 'ARRAY', 100: 'VECTOR_FLOAT', 101: 'VECTOR_FLOAT16',
                102: 'VECTOR_BFLOAT16', 103: 'SPARSE_FLOAT_VECTOR',
            }
            print(f"  - {field_name}: {type_map.get(field_type, field_type)}")
            if field.get("auto_id"):
                print(f"    (auto_id: True)")
            if field.get("is_primary"):
                print(f"    (primary key)")
            if field.get("enable_analyzer"):
                print(f"    (enable_analyzer: True)")

        print(f"\nDynamic fields enabled: {desc.get('enable_dynamic_field', False)}")

        # Get stats
        stats = client.get_collection_stats(collection_name)
        print(f"\nRow count: {stats.get('row_count', 0)}")

        # Get a sample of data
        print(f"\nSample data (first 3 rows):")
        results = client.query(
            collection_name=collection_name,
            filter="",
            output_fields=["formTitle", "document_id", "chunk_index"],
            limit=3
        )
        for i, row in enumerate(results, 1):
            print(f"  [{i}] Title: {row.get('formTitle', 'N/A')[:60]}...")
            print(f"      Document ID: {row.get('document_id', 'N/A')}")
            print(f"      Chunk Index: {row.get('chunk_index', 'N/A')}")
    else:
        print(f"\n[WARNING] Collection '{collection_name}' does not exist!")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
