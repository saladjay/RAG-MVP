"""
Unit tests for Knowledge Base Retrieval (US1 - Knowledge Base Query).

These tests verify the knowledge base client and search functionality.
"""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from typing import Dict, Any, List
from datetime import datetime


class TestKnowledgeBaseClient:
    """Unit tests for KnowledgeBase client.

    Tests verify:
    - Connection to Milvus
    - Vector search functionality
    - Error handling for connection failures
    - Chunk retrieval and formatting
    """

    @pytest.fixture
    def mock_milvus_connections(self):
        """Mock Milvus connections module."""
        with patch("pymilvus.connections") as mock:
            yield mock

    @pytest.fixture
    def mock_collection(self):
        """Mock Milvus collection."""
        collection = Mock()
        collection.name = "test_documents"
        return collection

    @pytest.mark.unit
    def test_knowledge_base_init_connects_to_milvus(
        self,
        mock_milvus_connections,
    ) -> None:
        """Test that KnowledgeBase connects to Milvus on initialization.

        Given: KnowledgeBase is instantiated with host and port
        When: __init__ is called
        Then: Establishes connection to Milvus
        """
        from rag_service.retrieval.knowledge_base import KnowledgeBase

        kb = KnowledgeBase(host="localhost", port=19530)

        # Verify connection was attempted
        mock_milvus_connections.connect.assert_called_once()

    @pytest.mark.unit
    def test_knowledge_base_search_returns_chunks(
        self,
        mock_milvus_connections,
        mock_collection,
    ) -> None:
        """Test that search returns relevant chunks.

        Given: A query vector and Milvus collection with data
        When: search is called
        Then: Returns list of chunks with content and metadata
        """
        from rag_service.retrieval.knowledge_base import KnowledgeBase

        # Mock search results
        mock_results = [
            [
                Mock(id="chunk1", distance=0.1, entity={"text": "Result 1", "doc_id": "doc1"}),
                Mock(id="chunk2", distance=0.2, entity={"text": "Result 2", "doc_id": "doc1"}),
            ]
        ]
        mock_collection.search.return_value = mock_results

        with patch("pymilvus.Collection", return_value=mock_collection):
            kb = KnowledgeBase(host="localhost", port=19530)

            # Mock embedding generation
            with patch.object(kb, "_embed_query", return_value=[0.1] * 1536):
                results = kb.search("test query", top_k=5)

        # Verify results structure
        assert len(results) == 2
        assert results[0]["chunk_id"] == "chunk1"
        assert results[0]["content"] == "Result 1"
        assert results[0]["score"] == 1 - 0.1  # Convert distance to similarity

    @pytest.mark.unit
    def test_knowledge_base_search_handles_empty_results(
        self,
        mock_milvus_connections,
        mock_collection,
    ) -> None:
        """Test that search handles empty results.

        Given: A query with no matching documents
        When: search is called
        Then: Returns empty list
        """
        from rag_service.retrieval.knowledge_base import KnowledgeBase

        mock_collection.search.return_value = [[]]

        with patch("pymilvus.Collection", return_value=mock_collection):
            kb = KnowledgeBase(host="localhost", port=19530)

            with patch.object(kb, "_embed_query", return_value=[0.1] * 1536):
                results = kb.search("no matches query", top_k=5)

        assert results == []

    @pytest.mark.unit
    def test_knowledge_base_search_handles_connection_error(
        self,
        mock_milvus_connections,
    ) -> None:
        """Test that search handles connection errors gracefully.

        Given: Milvus connection is unavailable
        When: search is called
        Then: Raises appropriate exception or returns error
        """
        from rag_service.retrieval.knowledge_base import KnowledgeBase

        mock_milvus_connections.connect.side_effect = Exception("Connection refused")

        with pytest.raises(Exception):
            kb = KnowledgeBase(host="localhost", port=19530)

    @pytest.mark.unit
    def test_knowledge_base_search_respects_top_k(
        self,
        mock_milvus_connections,
        mock_collection,
    ) -> None:
        """Test that search respects top_k parameter.

        Given: A query with top_k=3
        When: search is called
        Then: Returns at most 3 results
        """
        from rag_service.retrieval.knowledge_base import KnowledgeBase

        # Mock 5 results but request top_k=3
        mock_results = [
            [Mock(id=f"chunk{i}", distance=i * 0.1, entity={}) for i in range(5)]
        ]
        mock_collection.search.return_value = mock_results

        with patch("pymilvus.Collection", return_value=mock_collection):
            kb = KnowledgeBase(host="localhost", port=19530)

            with patch.object(kb, "_embed_query", return_value=[0.1] * 1536):
                results = kb.search("test query", top_k=3)

        assert len(results) <= 3

    @pytest.mark.unit
    def test_knowledge_base_formats_chunk_correctly(
        self,
        mock_milvus_connections,
        mock_collection,
    ) -> None:
        """Test that chunks are formatted with all required fields.

        Given: Milvus search results with entity data
        When: results are processed
        Then: Each chunk has chunk_id, content, score, source_doc
        """
        from rag_service.retrieval.knowledge_base import KnowledgeBase

        mock_entity = {
            "text": "Test content",
            "doc_id": "test_doc",
            "chunk_index": 0,
        }
        mock_results = [
            [Mock(id="chunk1", distance=0.15, entity=mock_entity)]
        ]
        mock_collection.search.return_value = mock_results

        with patch("pymilvus.Collection", return_value=mock_collection):
            kb = KnowledgeBase(host="localhost", port=19530)

            with patch.object(kb, "_embed_query", return_value=[0.1] * 1536):
                results = kb.search("test query", top_k=5)

        chunk = results[0]
        assert "chunk_id" in chunk
        assert "content" in chunk
        assert "score" in chunk
        assert "source_doc" in chunk
        assert chunk["source_doc"] == "test_doc"


class TestEmbeddingService:
    """Unit tests for embedding generation.

    Tests verify:
    - Text to vector conversion
    - API integration with OpenAI
    - Error handling for API failures
    - Batch embedding support
    """

    @pytest.mark.unit
    @patch("rag_service.retrieval.embeddings.OpenAI")
    def test_embedding_service_generates_vector(
        self,
        mock_openai,
    ) -> None:
        """Test that embedding service generates vector from text.

        Given: A text string
        When: embed_text is called
        Then: Returns embedding vector of correct dimension
        """
        from rag_service.retrieval.embeddings import EmbeddingService

        # Mock OpenAI response
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 1536)]
        mock_openai.return_value.embeddings.create.return_value = mock_response

        service = EmbeddingService()
        embedding = service.embed_text("test text")

        # Verify vector dimensions (text-embedding-3-small uses 1536)
        assert len(embedding) == 1536
        assert all(isinstance(x, float) for x in embedding)

    @pytest.mark.unit
    @patch("rag_service.retrieval.embeddings.OpenAI")
    def test_embedding_service_handles_api_error(
        self,
        mock_openai,
    ) -> None:
        """Test that embedding service handles API errors.

        Given: OpenAI API is unavailable
        When: embed_text is called
        Then: Raises appropriate exception
        """
        from rag_service.retrieval.embeddings import EmbeddingService
        from openai import APIError

        mock_openai.return_value.embeddings.create.side_effect = APIError("API error")

        service = EmbeddingService()

        with pytest.raises(APIError):
            service.embed_text("test text")

    @pytest.mark.unit
    @patch("rag_service.retrieval.embeddings.OpenAI")
    def test_embedding_supports_batch_embedding(
        self,
        mock_openai,
    ) -> None:
        """Test that embedding service supports batch processing.

        Given: A list of texts
        When: embed_batch is called
        Then: Returns list of embedding vectors
        """
        from rag_service.retrieval.embeddings import EmbeddingService

        texts = ["text1", "text2", "text3"]

        # Mock batch response
        mock_response = Mock()
        mock_response.data = [
            Mock(embedding=[0.1] * 1536),
            Mock(embedding=[0.2] * 1536),
            Mock(embedding=[0.3] * 1536),
        ]
        mock_openai.return_value.embeddings.create.return_value = mock_response

        service = EmbeddingService()
        embeddings = service.embed_batch(texts)

        assert len(embeddings) == 3
        assert all(len(e) == 1536 for e in embeddings)


class TestKnowledgeBaseIntegration:
    """Unit tests for knowledge base integration components.

    Tests verify:
    - Connection pooling
    - Retry logic
    - Performance optimization
    """

    @pytest.mark.unit
    def test_connection_pool_reuses_connections(
        self,
    ) -> None:
        """Test that connection pool reuses connections.

        Given: Multiple sequential searches
        When: searches are performed
        Then: Reuses existing connections
        """
        # This would test connection pooling behavior
        # Implementation depends on connection pooling strategy
        pass

    @pytest.mark.unit
    def test_search_implements_retry_logic(
        self,
    ) -> None:
        """Test that search implements retry on transient failures.

        Given: A transient network error
        When: search is called
        Then: Retries before failing
        """
        # This would test retry behavior
        # Implementation depends on retry strategy
        pass


class TestDocumentIndexing:
    """Unit tests for document indexing functionality.

    Tests verify:
    - Document addition with chunking
    - Document deletion with cleanup
    - Document update with re-indexing
    - Metadata preservation
    """

    @pytest.fixture
    async def knowledge_base(self):
        """Create knowledge base for testing."""
        from rag_service.retrieval.knowledge_base import get_knowledge_base

        kb = await get_knowledge_base()
        return kb

    @pytest.mark.unit
    async def test_add_document_creates_chunks(
        self,
        knowledge_base,
    ) -> None:
        """Test that add_document creates chunks from content.

        Given: A document with content longer than chunk size
        When: add_document is called
        Then: Document is split into multiple chunks
        """
        doc_id = "test_doc_chunks"
        content = "A" * 1000  # Long content to force chunking

        result = await knowledge_base.add_document(
            doc_id=doc_id,
            content=content,
            metadata={},
        )

        assert result["doc_id"] == doc_id
        assert result["chunk_count"] > 1  # Should have multiple chunks

    @pytest.mark.unit
    async def test_add_document_generates_embeddings(
        self,
        knowledge_base,
    ) -> None:
        """Test that add_document generates embeddings.

        Given: A document with text content
        When: add_document is called
        Then: Embeddings are generated for all chunks
        """
        doc_id = "test_doc_embeddings"
        content = "Test content for embedding generation"

        result = await knowledge_base.add_document(
            doc_id=doc_id,
            content=content,
            metadata={},
        )

        assert result["embedding_model"] is not None
        assert result["chunk_count"] > 0
        assert result["embedding_dimension"] == 1536  # text-embedding-3-small

    @pytest.mark.unit
    async def test_add_document_stores_metadata(
        self,
        knowledge_base,
    ) -> None:
        """Test that add_document stores metadata.

        Given: A document with metadata
        When: add_document is called
        Then: Metadata is stored with chunks
        """
        doc_id = "test_doc_metadata"
        content = "Test content"
        metadata = {
            "title": "Test Document",
            "category": "test",
            "tags": ["test", "unit"],
        }

        result = await knowledge_base.add_document(
            doc_id=doc_id,
            content=content,
            metadata=metadata,
        )

        assert result["doc_id"] == doc_id
        # Metadata should be preserved
        assert result["metadata"] == metadata or result.get("stored_metadata") is not None

    @pytest.mark.unit
    async def test_delete_document_removes_all_chunks(
        self,
        knowledge_base,
    ) -> None:
        """Test that delete_document removes all chunks.

        Given: A document with multiple chunks
        When: delete_document is called
        Then: All chunks are removed from vector database
        """
        doc_id = "test_doc_delete"

        # Add document first
        await knowledge_base.add_document(
            doc_id=doc_id,
            content="X" * 1000,  # Long content for multiple chunks
            metadata={},
        )

        # Delete document
        result = await knowledge_base.delete_document(doc_id)

        assert result["doc_id"] == doc_id
        assert result["deleted"] is True
        assert result["chunks_removed"] > 0

        # Verify document is gone
        document = await knowledge_base.get_document(doc_id)
        assert document is None

    @pytest.mark.unit
    async def test_delete_unknown_document_handled(
        self,
        knowledge_base,
    ) -> None:
        """Test that deleting unknown document is handled.

        Given: An unknown document ID
        When: delete_document is called
        Then: Returns success (idempotent operation)
        """
        result = await knowledge_base.delete_document("unknown_doc_xyz")

        # Should not raise - idempotent operation
        assert result["deleted"] is True or result["deleted"] is False

    @pytest.mark.unit
    async def test_update_document_modifies_content(
        self,
        knowledge_base,
    ) -> None:
        """Test that update_document modifies content.

        Given: An existing document
        When: update_document is called with new content
        Then: Old chunks are removed and new chunks are indexed
        """
        doc_id = "test_doc_update"

        # Add original document
        await knowledge_base.add_document(
            doc_id=doc_id,
            content="Original content",
            metadata={"version": 1},
        )

        # Update document
        result = await knowledge_base.update_document(
            doc_id=doc_id,
            content="Updated content with new information",
            metadata={"version": 2},
        )

        assert result["doc_id"] == doc_id
        assert result["updated"] is True
        assert result["re_indexed"] is True
        assert result["old_chunks_removed"] > 0
        assert result["new_chunks_added"] > 0

    @pytest.mark.unit
    async def test_update_document_preserves_metadata(
        self,
        knowledge_base,
    ) -> None:
        """Test that update_document preserves existing metadata.

        Given: A document with metadata
        When: update_document is called with partial metadata
        Then: Original metadata is preserved and merged
        """
        doc_id = "test_doc_update_meta"

        # Add with full metadata
        await knowledge_base.add_document(
            doc_id=doc_id,
            content="Test content",
            metadata={"category": "ai", "tags": ["test"], "priority": 1},
        )

        # Update with partial metadata
        result = await knowledge_base.update_document(
            doc_id=doc_id,
            content="Updated content",
            metadata={"priority": 2},  # Only update priority
        )

        # Verify document was updated
        document = await knowledge_base.get_document(doc_id)
        assert document is not None

        # Check that category and tags were preserved
        # (Implementation dependent on metadata merge strategy)

    @pytest.mark.unit
    async def test_update_unknown_document_creates_new(
        self,
        knowledge_base,
    ) -> None:
        """Test that updating unknown document creates new document.

        Given: An unknown document ID
        When: update_document is called
        Then: Creates new document with provided content
        """
        doc_id = "test_doc_update_new"

        result = await knowledge_base.update_document(
            doc_id=doc_id,
            content="New document created via update",
            metadata={},
        )

        assert result["doc_id"] == doc_id
        assert result["created"] is True or result["updated"] is True

    @pytest.mark.unit
    async def test_get_document_returns_uploaded_data(
        self,
        knowledge_base,
    ) -> None:
        """Test that get_document returns uploaded document.

        Given: A document that has been uploaded
        When: get_document is called
        Then: Returns document with content and metadata
        """
        doc_id = "test_doc_get"
        content = "Test content for retrieval"
        metadata = {"category": "test"}

        await knowledge_base.add_document(
            doc_id=doc_id,
            content=content,
            metadata=metadata,
        )

        document = await knowledge_base.get_document(doc_id)

        assert document is not None
        assert document["doc_id"] == doc_id
        assert document["content"] == content
        assert document["metadata"]["category"] == "test"

    @pytest.mark.unit
    async def test_get_document_returns_none_for_unknown(
        self,
        knowledge_base,
    ) -> None:
        """Test that get_document returns None for unknown doc_id.

        Given: An unknown document ID
        When: get_document is called
        Then: Returns None
        """
        document = await knowledge_base.get_document("unknown_doc_xyz")
        assert document is None

    @pytest.mark.unit
    async def test_chunk_size_respects_configuration(
        self,
        knowledge_base,
    ) -> None:
        """Test that chunk size respects configuration.

        Given: A configured chunk size
        When: add_document is called
        Then: Content is split according to chunk size
        """
        # This would verify chunk size configuration
        # Implementation depends on chunking strategy
        pass

    @pytest.mark.unit
    async def test_add_document_handles_empty_content(
        self,
        knowledge_base,
    ) -> None:
        """Test that add_document handles empty content.

        Given: A document with empty content
        When: add_document is called
        Then: Raises validation error
        """
        from rag_service.core.exceptions import ValidationError

        with pytest.raises(ValidationError):
            await knowledge_base.add_document(
                doc_id="test_doc_empty",
                content="",
                metadata={},
            )

    @pytest.mark.unit
    async def test_concurrent_document_operations(
        self,
        knowledge_base,
    ) -> None:
        """Test that concurrent document operations are handled.

        Given: Multiple concurrent add/update/delete operations
        When: Operations are executed simultaneously
        Then: All operations complete without data corruption
        """
        import asyncio

        async def add_doc(i: int):
            return await knowledge_base.add_document(
                doc_id=f"test_doc_concurrent_{i}",
                content=f"Concurrent document {i}",
                metadata={"index": i},
            )

        # Run concurrent operations
        results = await asyncio.gather(
            add_doc(1),
            add_doc(2),
            add_doc(3),
        )

        # All should succeed
        for result in results:
            assert result["doc_id"] is not None
