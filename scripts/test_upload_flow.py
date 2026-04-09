"""
Complete upload flow test to diagnose the 502/upload_failed errors.

This script simulates the exact upload flow:
1. Read a JSON file from batch_output
2. Chunk the text
3. Generate embeddings
4. Insert into Milvus
"""

import asyncio
import json
import os
import sys
import time
from typing import Any, Dict, List

# Windows console encoding fix
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import httpx


# Configuration
EMBEDDING_URL = "http://128.23.74.3:9091/llm/embed-bge/v1/embeddings"
EMBEDDING_MODEL = "bge-m3"
EMBEDDING_TIMEOUT = 120
EMBEDDING_AUTH_TOKEN = "T0EtZ3JvdXAtYXV0aDpPQS1ncm91cC1hdXRo"

MILVUS_URI = "http://localhost:19530"
COLLECTION_NAME = "knowledge_base"

BATCH_OUTPUT_DIR = r"D:\project\OA\core\batch_output\mineru"


def chunk_text(text: str, chunk_size: int, overlap: int) -> List[Dict[str, Any]]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    chunk_index = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunk_text = text[start:end]

        # Only add non-empty chunks
        if chunk_text.strip():
            chunks.append({
                "text": chunk_text,
                "start": start,
                "end": end,
                "chunk_index": chunk_index,
            })
            chunk_index += 1

        # Move start position with overlap
        if end >= text_length:
            break
        start = end - overlap

    return chunks


async def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """Generate embeddings using the cloud service."""
    client = httpx.AsyncClient(timeout=EMBEDDING_TIMEOUT)

    headers = {
        "Content-Type": "application/json",
    }
    if EMBEDDING_AUTH_TOKEN:
        headers["Authorization"] = f"Basic {EMBEDDING_AUTH_TOKEN}"

    payload = {
        "input": texts,
        "model": EMBEDDING_MODEL,
    }

    try:
        response = await client.post(
            EMBEDDING_URL,
            json=payload,
            headers=headers,
        )
        response.raise_for_status()

        data = response.json()

        # Parse response - handle different formats
        embeddings = []
        if "data" in data:
            # OpenAI format
            for item in data["data"]:
                embeddings.append(item["embedding"])
        elif "embeddings" in data:
            # Custom format
            embeddings = data["embeddings"]
        else:
            raise ValueError(f"Unexpected response format: {list(data.keys())}")

        return embeddings

    finally:
        await client.aclose()


async def insert_milvus(documents: List[Dict[str, Any]]) -> int:
    """Insert documents into Milvus."""
    try:
        from pymilvus import MilvusClient
    except ImportError:
        print("[ERROR] pymilvus not installed")
        raise

    client = MilvusClient(uri=MILVUS_URI)

    # Check collection exists
    collections = client.list_collections()
    collection_names = []
    for c in collections:
        if isinstance(c, str):
            collection_names.append(c)
        elif isinstance(c, dict):
            collection_names.append(c.get("name", ""))

    if COLLECTION_NAME not in collection_names:
        print(f"[ERROR] Collection '{COLLECTION_NAME}' does not exist")
        print(f"Available collections: {collection_names}")
        raise ValueError(f"Collection '{COLLECTION_NAME}' not found")

    # Get collection stats before insert
    try:
        stats_before = client.get_collection_stats(COLLECTION_NAME)
        row_count_before = stats_before.get("row_count", 0)
        print(f"Collection row count before: {row_count_before}")
    except Exception as e:
        print(f"[WARNING] Could not get collection stats: {e}")
        row_count_before = 0

    # Prepare data for insertion
    insert_data = []
    for doc in documents:
        insert_data.append({
            "fileContent": doc["fileContent"],
            "formTitle": doc["formTitle"],
            "document_id": doc["document_id"],
            "chunk_index": doc["chunk_index"],
            "vector": doc["vector"],
        })

    # Insert
    print(f"Inserting {len(insert_data)} documents...")
    try:
        result = client.insert(
            collection_name=COLLECTION_NAME,
            data=insert_data
        )
        print(f"Insert result: {result}")

        # Get collection stats after insert
        stats_after = client.get_collection_stats(COLLECTION_NAME)
        row_count_after = stats_after.get("row_count", 0)
        print(f"Collection row count after: {row_count_after}")
        print(f"Rows added: {row_count_after - row_count_before}")

        return len(insert_data)

    except Exception as e:
        print(f"[ERROR] Milvus insert failed: {e}")
        import traceback
        traceback.print_exc()
        raise


async def test_single_file_upload(file_path: str) -> Dict[str, Any]:
    """Test uploading a single JSON file."""
    print(f"\n{'=' * 60}")
    print(f"Testing file: {os.path.basename(file_path)}")
    print('=' * 60)

    # Step 1: Read JSON file
    print("\n[Step 1] Reading JSON file...")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            json_data = json.load(f)

        # Extract content and title
        # Content is in "markdown" field from mineru output
        file_content = json_data.get("markdown") or json_data.get("content", "")
        # Title from filename if not in JSON
        form_title = json_data.get("title", os.path.basename(file_path).replace("_mineru.json", ""))

        if not file_content:
            print(f"[FAILED] No content in JSON file")
            return {"status": "failed", "error": "No content in JSON file"}

        print(f"Content length: {len(file_content)} chars")
        print(f"Title: {form_title[:50]}...")

    except Exception as e:
        print(f"[FAILED] Error reading JSON: {e}")
        return {"status": "failed", "error": str(e)}

    # Step 2: Chunk text
    print("\n[Step 2] Chunking text...")
    chunk_size = 512
    chunk_overlap = 50

    chunks = chunk_text(file_content, chunk_size, chunk_overlap)
    print(f"Created {len(chunks)} chunks")

    # Step 3: Generate embeddings
    print("\n[Step 3] Generating embeddings...")
    chunk_texts = [chunk["text"] for chunk in chunks]

    try:
        start_time = time.time()
        embeddings = await generate_embeddings(chunk_texts)
        latency_ms = (time.time() - start_time) * 1000

        print(f"Generated {len(embeddings)} embeddings in {latency_ms:.0f}ms")
        print(f"Vector dimension: {len(embeddings[0])}")

        if len(embeddings) != len(chunks):
            print(f"[FAILED] Embedding count mismatch: {len(embeddings)} != {len(chunks)}")
            return {"status": "failed", "error": "Embedding count mismatch"}

    except Exception as e:
        print(f"[FAILED] Embedding generation failed: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "failed", "error": str(e)}

    # Step 4: Prepare documents
    print("\n[Step 4] Preparing documents for Milvus...")
    import uuid
    document_id = str(uuid.uuid4())

    documents = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        documents.append({
            "fileContent": chunk["text"],
            "formTitle": form_title,
            "document_id": document_id,
            "chunk_index": chunk["chunk_index"],
            "vector": embedding,
        })

    print(f"Prepared {len(documents)} documents")

    # Step 5: Insert into Milvus
    print("\n[Step 5] Inserting into Milvus...")
    try:
        inserted = await insert_milvus(documents)
        print(f"[OK] Successfully inserted {inserted} documents")
        return {
            "status": "success",
            "document_id": document_id,
            "chunk_count": len(chunks),
            "inserted_count": inserted,
        }
    except Exception as e:
        print(f"[FAILED] Milvus insertion failed: {e}")
        return {"status": "failed", "error": str(e)}


async def test_collection_info():
    """Check Milvus collection information."""
    print("\n" + "=" * 60)
    print("Milvus Collection Information")
    print("=" * 60)

    try:
        from pymilvus import MilvusClient
    except ImportError:
        print("[ERROR] pymilvus not installed")
        return

    client = MilvusClient(uri=MILVUS_URI)

    # List all collections
    collections = client.list_collections()
    collection_names = []
    for c in collections:
        if isinstance(c, str):
            collection_names.append(c)
        elif isinstance(c, dict):
            collection_names.append(c.get("name", ""))

    print(f"\nAvailable collections: {collection_names}")

    # Check if our collection exists
    if COLLECTION_NAME in collection_names:
        print(f"\n[OK] Collection '{COLLECTION_NAME}' exists")

        # Get collection description
        desc = client.describe_collection(COLLECTION_NAME)
        print(f"\nCollection schema:")
        for field in desc.get("fields", []):
            field_name = field.get("name")
            field_type = field.get("type")
            type_map = {
                1: 'BOOL',
                2: 'INT8',
                3: 'INT16',
                4: 'INT32',
                5: 'INT64',
                10: 'FLOAT',
                11: 'DOUBLE',
                20: 'STRING',
                21: 'VARCHAR',
                23: 'ARRAY',
                100: 'VECTOR_FLOAT',
                101: 'VECTOR_FLOAT16',
                102: 'VECTOR_BFLOAT16',
                103: 'SPARSE_FLOAT_VECTOR',
            }
            print(f"  - {field_name}: {type_map.get(field_type, field_type)}")
            if field.get("auto_id"):
                print(f"    (auto_id: True)")
            if field.get("is_primary"):
                print(f"    (primary key)")

        # Get stats
        stats = client.get_collection_stats(COLLECTION_NAME)
        print(f"\nRow count: {stats.get('row_count', 0)}")

    else:
        print(f"\n[WARNING] Collection '{COLLECTION_NAME}' does not exist")
        print("You need to create it first with:")
        print(f"  curl -X POST http://localhost:8000/kb/collection/create")


async def main():
    """Main test function."""
    print("=" * 60)
    print("Complete Upload Flow Test")
    print("=" * 60)

    # Check collection info first
    await test_collection_info()

    # Find JSON files
    if not os.path.exists(BATCH_OUTPUT_DIR):
        print(f"\n[ERROR] Batch output directory not found: {BATCH_OUTPUT_DIR}")
        return

    json_files = [f for f in os.listdir(BATCH_OUTPUT_DIR) if f.endswith("_mineru.json")]
    print(f"\nFound {len(json_files)} JSON files")

    if not json_files:
        print("[ERROR] No JSON files found")
        return

    # Test with first 3 files
    test_files = json_files[:3]
    results = []

    for json_file in test_files:
        file_path = os.path.join(BATCH_OUTPUT_DIR, json_file)
        result = await test_single_file_upload(file_path)
        results.append((json_file, result))

        # Small delay between uploads
        await asyncio.sleep(1)

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    success_count = sum(1 for _, r in results if r.get("status") == "success")
    failed_count = len(results) - success_count

    print(f"\nTested: {len(results)} files")
    print(f"Success: {success_count}")
    print(f"Failed: {failed_count}")

    if failed_count > 0:
        print("\nFailed files:")
        for filename, result in results:
            if result.get("status") != "success":
                print(f"  - {filename}: {result.get('error', 'Unknown error')}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[INTERRUPTED] Test stopped by user")
    except Exception as e:
        print(f"\n\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
