"""
Contract tests for Milvus document operations (US4 - Knowledge Base Management).

These tests verify the document management functionality including:
- Document upload and indexing
- Document retrieval and query
- Document update and re-indexing
- Document deletion and cleanup
"""

import pytest
from typing import Dict, Any


class TestMilvusDocumentUploadContract:
    """Contract tests for Milvus document upload operations.

    Tests verify:
    - Document upload with content and metadata
    - Automatic chunking and embedding generation
    - Document indexing in vector database
    - Duplicate document handling
    """

    @pytest.fixture
    async def knowledge_base(self):
        """Create knowledge base for testing."""
        from rag_service.retrieval.knowledge_base import get_knowledge_base

        kb = await get_knowledge_base()
        return kb

    @pytest.mark.contract
    async def test_upload_document_with_valid_content(
        self,
        knowledge_base,
    ) -> None:
        """Test that document upload works with valid content.

        Given: A document with content and metadata
        When: add_document is called
        Then: Document is indexed and retrievable
        """
        doc_id = "test_doc_001"
        content = "This is a test document about RAG systems. RAG combines retrieval with generation."
        metadata = {"title": "RAG Introduction", "category": "ai"}

        result = await knowledge_base.add_document(
            doc_id=doc_id,
            content=content,
            metadata=metadata,
        )

        assert result["doc_id"] == doc_id
        assert result["chunk_count"] > 0
        assert result["indexed"] is True

    @pytest.mark.contract
    async def test_upload_document_creates_embeddings(
        self,
        knowledge_base,
    ) -> None:
        """Test that document upload creates embeddings.

        Given: A document with text content
        When: add_document is called
        Then: Embeddings are generated for each chunk
        """
        doc_id = "test_doc_002"
        content = "Vector databases store embeddings for semantic search."

        result = await knowledge_base.add_document(
            doc_id=doc_id,
            content=content,
            metadata={},
        )

        assert result["embedding_model"] is not None
        assert result["chunk_count"] > 0
        assert result["embedding_dimension"] > 0

    @pytest.mark.contract
    async def test_upload_document_with_empty_content_fails(
        self,
        knowledge_base,
    ) -> None:
        """Test that uploading empty content fails validation.

        Given: A document with empty content
        When: add_document is called
        Then: Raises validation error
        """
        from rag_service.core.exceptions import ValidationError

        doc_id = "test_doc_003"

        with pytest.raises(ValidationError):
            await knowledge_base.add_document(
                doc_id=doc_id,
                content="",
                metadata={},
            )

    @pytest.mark.contract
    async def test_upload_duplicate_document_updates(
        self,
        knowledge_base,
    ) -> None:
        """Test that uploading duplicate document updates existing.

        Given: An existing document
        When: add_document is called with same doc_id
        Then: Document is updated/re-indexed
        """
        doc_id = "test_doc_004"

        # First upload
        await knowledge_base.add_document(
            doc_id=doc_id,
            content="Original content",
            metadata={"version": 1},
        )

        # Update with same doc_id
        result = await knowledge_base.add_document(
            doc_id=doc_id,
            content="Updated content",
            metadata={"version": 2},
        )

        assert result["doc_id"] == doc_id
        assert result["updated"] is True


class TestMilvusDocumentRetrievalContract:
    """Contract tests for Milvus document retrieval operations.

    Tests verify:
    - Document retrieval by ID
    - Search returns uploaded documents
    - Chunk metadata preservation
    """

    @pytest.fixture
    async def knowledge_base(self):
        """Create knowledge base for testing."""
        from rag_service.retrieval.knowledge_base import get_knowledge_base

        kb = await get_knowledge_base()
        return kb

    @pytest.mark.contract
    async def test_search_returns_uploaded_document(
        self,
        knowledge_base,
    ) -> None:
        """Test that uploaded documents are searchable.

        Given: A document has been uploaded
        When: search is called with relevant query
        Then: Uploaded document chunks are returned
        """
        doc_id = "test_doc_005"
        content = "Machine learning models learn patterns from data."
        metadata = {"topic": "ml"}

        # Upload document
        await knowledge_base.add_document(
            doc_id=doc_id,
            content=content,
            metadata=metadata,
        )

        # Search for relevant content
        results = await knowledge_base.search(
            query="machine learning patterns",
            top_k=5,
        )

        assert len(results) > 0
        # At least one result should be from our document
        doc_ids = [r.get("source_doc") for r in results]
        assert doc_id in doc_ids

    @pytest.mark.contract
    async def test_get_document_returns_document_data(
        self,
        knowledge_base,
    ) -> None:
        """Test that get_document returns uploaded document.

        Given: A document has been uploaded
        When: get_document is called with doc_id
        Then: Returns document content and metadata
        """
        doc_id = "test_doc_006"
        content = "Test document content for retrieval"
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

    @pytest.mark.contract
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


class TestMilvusDocumentUpdateContract:
    """Contract tests for Milvus document update operations.

    Tests verify:
    - Document content update
    - Document metadata update
    - Re-indexing after update
    """

    @pytest.fixture
    async def knowledge_base(self):
        """Create knowledge base for testing."""
        from rag_service.retrieval.knowledge_base import get_knowledge_base

        kb = await get_knowledge_base()
        return kb

    @pytest.mark.contract
    async def test_update_document_modifies_content(
        self,
        knowledge_base,
    ) -> None:
        """Test that update_document modifies content.

        Given: An existing document
        When: update_document is called with new content
        Then: Document content is updated and re-indexed
        """
        doc_id = "test_doc_007"

        # Upload original
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

        # Verify new content is searchable
        results = await knowledge_base.search("new information", top_k=5)
        assert len(results) > 0

    @pytest.mark.contract
    async def test_update_document_preserves_metadata(
        self,
        knowledge_base,
    ) -> None:
        """Test that update_document can preserve existing metadata.

        Given: An existing document with metadata
        When: update_document is called with partial metadata
        Then: Existing metadata is preserved and merged
        """
        doc_id = "test_doc_008"

        # Upload with metadata
        await knowledge_base.add_document(
            doc_id=doc_id,
            content="Test content",
            metadata={"category": "ai", "tags": ["test"], "version": 1},
        )

        # Update with partial metadata
        result = await knowledge_base.update_document(
            doc_id=doc_id,
            content="Updated content",
            metadata={"version": 2},  # Only update version
        )

        document = await knowledge_base.get_document(doc_id)

        # Category and tags should be preserved
        assert document["metadata"]["category"] == "ai"
        assert document["metadata"]["tags"] == ["test"]
        assert document["metadata"]["version"] == 2


class TestMilvusDocumentDeletionContract:
    """Contract tests for Milvus document deletion operations.

    Tests verify:
    - Document deletion removes all chunks
    - Deleted documents are not searchable
    - Metadata cleanup
    """

    @pytest.fixture
    async def knowledge_base(self):
        """Create knowledge base for testing."""
        from rag_service.retrieval.knowledge_base import get_knowledge_base

        kb = await get_knowledge_base()
        return kb

    @pytest.mark.contract
    async def test_delete_document_removes_chunks(
        self,
        knowledge_base,
    ) -> None:
        """Test that delete_document removes all chunks.

        Given: An existing document with multiple chunks
        When: delete_document is called
        Then: All chunks are removed from vector database
        """
        doc_id = "test_doc_009"

        # Upload document (will create multiple chunks)
        await knowledge_base.add_document(
            doc_id=doc_id,
            content="A" * 1000,  # Long content to ensure multiple chunks
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

    @pytest.mark.contract
    async def test_delete_document_makes_unsearchable(
        self,
        knowledge_base,
    ) -> None:
        """Test that deleted documents are not searchable.

        Given: A document that has been deleted
        When: search is called
        Then: Deleted document chunks are not returned
        """
        doc_id = "test_doc_010"
        content = "Unique content for deletion test"

        # Upload document
        await knowledge_base.add_document(
            doc_id=doc_id,
            content=content,
            metadata={},
        )

        # Verify it's searchable
        results_before = await knowledge_base.search("deletion test", top_k=5)
        doc_ids_before = [r.get("source_doc") for r in results_before]
        assert doc_id in doc_ids_before

        # Delete document
        await knowledge_base.delete_document(doc_id)

        # Verify it's no longer searchable
        results_after = await knowledge_base.search("deletion test", top_k=5)
        doc_ids_after = [r.get("source_doc") for r in results_after]
        assert doc_id not in doc_ids_after

    @pytest.mark.contract
    async def test_delete_unknown_document_handled(
        self,
        knowledge_base,
    ) -> None:
        """Test that deleting unknown document is handled gracefully.

        Given: An unknown document ID
        When: delete_document is called
        Then: Returns success=True (idempotent operation)
        """
        result = await knowledge_base.delete_document("unknown_doc_xyz")

        # Should be idempotent - deleting non-existent doc should succeed
        assert result["deleted"] is True  # or False depending on design

    @pytest.mark.contract
    async def test_document_operations_generate_trace(
        self,
        knowledge_base,
    ) -> None:
        """Test that document operations generate trace data.

        Given: Document operations are performed
        When: add_document/update/delete is called
        Then: Trace spans are created for each operation
        """
        doc_id = "test_doc_011"

        # Upload
        upload_result = await knowledge_base.add_document(
            doc_id=doc_id,
            content="Trace test document",
            metadata={},
        )

        assert "trace_id" in upload_result or "operation_id" in upload_result

        # Delete
        delete_result = await knowledge_base.delete_document(doc_id)

        assert "trace_id" in delete_result or "operation_id" in delete_result
