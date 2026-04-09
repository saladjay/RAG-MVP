"""
Milvus collection utility for hybrid search.

This module provides utilities for creating BM25-enabled hybrid collections
with both dense vector (semantic) and sparse vector (BM25 keyword) search support.
"""

import asyncio
from typing import Any, Dict, List

from pymilvus import (
    MilvusClient,
    MilvusException,
    utility,
    Function,
    FunctionType,
    DataType,
)

# Try to import hybrid search components (available in newer pymilvus versions)
try:
    from pymilvus import AnnSearchRequest
    from pymilvus import SPARSESearchRequest
    from pymilvus import RRFRanker
    HYBRID_SEARCH_AVAILABLE = True
except ImportError:
    # Fallback for older pymilvus versions
    AnnSearchRequest = None
    SPARSESearchRequest = None
    RRFRanker = None
    HYBRID_SEARCH_AVAILABLE = False

from rag_service.core.logger import get_logger


logger = get_logger(__name__)


async def create_hybrid_collection(
    collection_name: str = "knowledge_base",
    dimension: int = 1024,
    drop_existing: bool = False,
    milvus_uri: str = None,
) -> Dict[str, Any]:
    """
    Create a collection in Milvus for knowledge base storage.

    The collection supports:
    - Dense vector search (semantic similarity)
    - Full-text search with analyzer (when supported by Milvus version)

    Args:
        collection_name: Name of the collection to create
        dimension: Embedding vector dimension (default: 1024 for bge-m3)
        drop_existing: Whether to drop existing collection
        milvus_uri: Optional Milvus URI (defaults to env var)

    Returns:
        Dictionary with creation result

    Raises:
        MilvusException: If collection creation fails
    """
    loop = asyncio.get_event_loop()

    def _create_collection() -> Dict[str, Any]:
        # Get Milvus URI from env if not provided
        if milvus_uri is None:
            import os
            milvus_uri = os.getenv("MILVUS_KB_URI", "http://localhost:19530")

        client = MilvusClient(uri=milvus_uri)

        # Check if collection exists
        has_collection = client.has_collection(collection_name)

        if has_collection:
            if drop_existing:
                logger.info(f"Dropping existing collection: {collection_name}")
                client.drop_collection(collection_name)
                has_collection = False
            else:
                logger.info(f"Collection already exists: {collection_name}")
                return {"created": False, "existed": True, "collection_name": collection_name}

        # Define schema
        schema = client.create_schema()

        # Add fields
        schema.add_field(
            field_name="id",
            datatype=DataType.INT64,
            is_primary=True,
            auto_id=True,
            description="Primary key (auto-generated)"
        )

        # Text content
        # Try to enable analyzer if supported
        try:
            schema.add_field(
                field_name="fileContent",
                datatype=DataType.VARCHAR,
                max_length=65535,
                enable_analyzer=True,
                enable_match=True,
                description="Document content text"
            )
            analyzer_enabled = True
        except Exception:
            # Analyzer not supported in this version
            schema.add_field(
                field_name="fileContent",
                datatype=DataType.VARCHAR,
                max_length=65535,
                description="Document content text"
            )
            analyzer_enabled = False

        # Document title
        schema.add_field(
            field_name="formTitle",
            datatype=DataType.VARCHAR,
            max_length=512,
            description="Document title"
        )

        # Document identifier
        schema.add_field(
            field_name="document_id",
            datatype=DataType.VARCHAR,
            max_length=256,
            description="Document identifier for grouping chunks"
        )

        # Chunk index within document
        schema.add_field(
            field_name="chunk_index",
            datatype=DataType.INT64,
            description="Chunk position in document"
        )

        # Dense embedding vector
        schema.add_field(
            field_name="vector",
            datatype=DataType.FLOAT_VECTOR,
            dim=dimension,
            description="Dense embedding vector for semantic search"
        )

        # Try to add BM25 function for sparse vector (if supported)
        if analyzer_enabled:
            try:
                bm25_function = Function(
                    name="bm25_function",
                    function_type=FunctionType.BM25,
                    input_field_names=["fileContent"],
                    output_field_names=["sparse_vector"],
                )
                schema.add_function(bm25_function)

                # Add sparse vector field
                schema.add_field(
                    field_name="sparse_vector",
                    datatype=DataType.SPARSE_FLOAT_VECTOR,
                    description="Sparse BM25 vector for keyword search (auto-generated)"
                )
                logger.info("BM25 function and sparse_vector field added")
            except Exception as e:
                logger.warning(f"Could not add BM25 function: {e}")

        # Create collection with schema
        logger.info(f"Creating collection: {collection_name}")
        client.create_collection(
            collection_name=collection_name,
            schema=schema,
            index=""
        )

        # Create dense vector index
        dense_index_params = {
            "index_type": "IVF_FLAT",
            "metric_type": "COSINE",
            "params": {"nlist": 128}
        }
        client.create_index(
            collection_name=collection_name,
            index_name="dense_vector_index",
            field_name="vector",
            index_params=dense_index_params
        )
        logger.info(f"Created dense vector index for {collection_name}")

        # Try to create sparse vector index (if sparse_vector field exists)
        if analyzer_enabled:
            try:
                sparse_index_params = {
                    "index_type": "SPARSE_INVERTED_INDEX",
                    "metric_type": "BM25",
                    "params": {"drop_ratio_build": 0.1}
                }
                client.create_index(
                    collection_name=collection_name,
                    index_name="sparse_vector_index",
                    field_name="sparse_vector",
                    index_params=sparse_index_params
                )
                logger.info(f"Created sparse vector index for {collection_name}")
            except Exception as e:
                logger.warning(f"Could not create sparse vector index: {e}")

        # Load collection into memory
        client.load_collection(collection_name=collection_name)
        logger.info(f"Loaded collection into memory: {collection_name}")

        return {
            "created": True,
            "existed": False,
            "collection_name": collection_name,
            "dimension": dimension,
            "analyzer_enabled": analyzer_enabled,
        }

    try:
        return await loop.run_in_executor(None, _create_collection)

    except MilvusException as e:
        logger.error(f"Failed to create collection: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating collection: {e}")
        raise


async def get_collection_stats(
    collection_name: str,
    milvus_uri: str = None,
) -> Dict[str, Any]:
    """
    Get statistics for a Milvus collection.

    Args:
        collection_name: Name of the collection
        milvus_uri: Optional Milvus URI

    Returns:
        Dictionary with collection statistics

    Raises:
        MilvusException: If stats retrieval fails
    """
    loop = asyncio.get_event_loop()

    def _get_stats() -> Dict[str, Any]:
        # Get Milvus URI from env if not provided
        if milvus_uri is None:
            import os
            milvus_uri = os.getenv("MILVUS_KB_URI", "http://localhost:19530")

        client = MilvusClient(uri=milvus_uri)

        # Check if collection exists
        has_collection = client.has_collection(collection_name)

        if not has_collection:
            return {
                "exists": False,
                "collection_name": collection_name,
            }

        # Get collection info
        from pymilvus import Collection

        # Connect using standard Milvus client for detailed info
        from pymilvus import connections

        connections.connect(alias="stats_conn", uri=milvus_uri)
        collection = Collection(name=collection_name)

        # Get row count
        stats = {
            "exists": True,
            "collection_name": collection_name,
            "chunk_count": collection.num_entities,
        }

        # Get schema fields
        schema = collection.schema
        fields = []
        for field in schema.fields:
            fields.append({
                "name": field.name,
                "type": str(field.dtype),
                "description": field.description if hasattr(field, "description") else "",
            })
        stats["schema_fields"] = [f["name"] for f in fields]

        # Get indexes
        indexes_info = collection.indexes
        indexes = []
        for index in indexes_info:
            indexes.append({
                "name": index.index_name,
                "field_name": index.field_name,
                "index_type": index.index_type,
            })
        stats["indexes"] = [idx["name"] for idx in indexes]

        # Count unique documents (approximate)
        # This is a rough estimate based on assuming uniform distribution
        if stats["chunk_count"] > 0:
            # We can't easily get unique document count without querying
            # For now, set to 0
            stats["document_count"] = 0

        connections.disconnect("stats_conn")

        return stats

    try:
        return await loop.run_in_executor(None, _get_stats)

    except MilvusException as e:
        logger.error(f"Failed to get collection stats: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error getting collection stats: {e}")
        raise


async def verify_collection_schema(
    collection_name: str,
    milvus_uri: str = None,
) -> Dict[str, Any]:
    """
    Verify that a collection has the correct schema for hybrid search.

    Args:
        collection_name: Name of the collection
        milvus_uri: Optional Milvus URI

    Returns:
        Dictionary with verification result
    """
    loop = asyncio.get_event_loop()

    def _verify_schema() -> Dict[str, Any]:
        # Get Milvus URI from env if not provided
        if milvus_uri is None:
            import os
            milvus_uri = os.getenv("MILVUS_KB_URI", "http://localhost:19530")

        from pymilvus import connections, Collection

        connections.connect(alias="verify_conn", uri=milvus_uri)

        if not utility.has_collection(collection_name):
            connections.disconnect("verify_conn")
            return {
                "valid": False,
                "exists": False,
                "collection_name": collection_name,
            }

        collection = Collection(name=collection_name)
        schema = collection.schema

        # Required fields for hybrid search
        required_fields = {
            "fileContent": DataType.VARCHAR,
            "formTitle": DataType.VARCHAR,
            "document_id": DataType.VARCHAR,
            "chunk_index": DataType.INT64,
            "vector": DataType.FLOAT_VECTOR,
            "sparse_vector": DataType.SPARSE_FLOAT_VECTOR,
        }

        field_names = {f.name for f in schema.fields}

        result = {
            "valid": True,
            "exists": True,
            "collection_name": collection_name,
            "missing_fields": [],
            "extra_fields": [],
        }

        for required_name, required_type in required_fields.items():
            if required_name not in field_names:
                result["missing_fields"].append(required_name)
                result["valid"] = False

        # Check for extra fields (informational only)
        extra = field_names - set(required_fields.keys()) - {"id"}
        if extra:
            result["extra_fields"] = list(extra)

        connections.disconnect("verify_conn")

        return result

    try:
        return await loop.run_in_executor(None, _verify_schema)

    except Exception as e:
        logger.error(f"Failed to verify collection schema: {e}")
        return {
            "valid": False,
            "error": str(e),
            "collection_name": collection_name,
        }
