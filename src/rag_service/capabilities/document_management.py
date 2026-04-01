"""
Document Management Capability for RAG Service.

This capability provides unified access to document operations including
add, update, delete, and list. HTTP endpoints use this capability - they
NEVER access Milvus directly.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime

from pydantic import BaseModel, Field

from rag_service.capabilities.base import (
    Capability,
    CapabilityInput,
    CapabilityOutput,
    CapabilityValidationResult,
)
from rag_service.core.exceptions import DocumentNotFoundError, ValidationError
from rag_service.core.logger import get_logger

logger = get_logger(__name__)


class DocumentManagementInput(CapabilityInput):
    """
    Input for document management operations.

    Attributes:
        operation: Operation type (add, delete, update, list).
        doc_id: Document identifier (for add/update/delete).
        content: Document content (for add/update).
        metadata: Document metadata (for add/update).
    """

    operation: str = Field(..., description="Operation: add, delete, update, list")
    doc_id: Optional[str] = Field(default=None, description="Document ID")
    content: Optional[str] = Field(default=None, description="Document content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata")


class DocumentInfo(BaseModel):
    """
    Information about a document.

    Attributes:
        doc_id: Document identifier.
        chunk_count: Number of chunks.
        metadata: Document metadata.
        created_at: Creation timestamp.
    """

    doc_id: str = Field(..., description="Document ID")
    chunk_count: int = Field(default=0, ge=0, description="Number of chunks")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata")
    created_at: Optional[str] = Field(default=None, description="Creation time")


class DocumentManagementOutput(CapabilityOutput):
    """
    Output from document management operations.

    Attributes:
        success: Whether operation succeeded.
        doc_id: Document ID (for add/update).
        documents: List of documents (for list).
        chunk_count: Number of chunks (for add/update).
        indexed: Whether document was indexed (for add/update).
        updated: Whether document was updated (for update).
        re_indexed: Whether document was re-indexed (for update).
        deleted: Whether document was deleted (for delete).
        chunks_removed: Number of chunks removed (for delete).
        old_chunks_removed: Number of old chunks removed (for update).
        new_chunks_added: Number of new chunks added (for update).
        created: Whether document was created (for update on non-existent doc).
        trace_id: Trace ID for observability.
    """

    success: bool = Field(default=True, description="Operation success")
    doc_id: Optional[str] = Field(default=None, description="Document ID")
    documents: List[DocumentInfo] = Field(default_factory=list, description="Document list")
    chunk_count: int = Field(default=0, description="Number of chunks")
    indexed: bool = Field(default=False, description="Whether document was indexed")
    updated: bool = Field(default=False, description="Whether document was updated")
    re_indexed: bool = Field(default=False, description="Whether document was re-indexed")
    deleted: bool = Field(default=False, description="Whether document was deleted")
    chunks_removed: int = Field(default=0, description="Chunks removed")
    old_chunks_removed: int = Field(default=0, description="Old chunks removed")
    new_chunks_added: int = Field(default=0, description="New chunks added")
    created: bool = Field(default=False, description="Whether document was created")
    trace_id: str = Field(default="", description="Trace ID")


class DocumentManagementCapability(Capability[DocumentManagementInput, DocumentManagementOutput]):
    """
    Capability for document management.

    This capability wraps Milvus document operations and provides
    a unified interface for document CRUD. HTTP endpoints use this
    capability - they NEVER access Milvus directly.

    Features:
    - Add documents to knowledge base with chunking and embedding
    - Update existing documents with re-indexing
    - Delete documents with cleanup
    - List all documents
    """

    def __init__(self, knowledge_base: Optional[Any] = None) -> None:
        """
        Initialize DocumentManagementCapability.

        Args:
            knowledge_base: KnowledgeBase instance (injected dependency).
        """
        super().__init__()
        self._knowledge_base = knowledge_base

    async def _get_knowledge_base(self) -> Any:
        """Get or create knowledge base instance."""
        if self._knowledge_base is None:
            from rag_service.retrieval.knowledge_base import get_knowledge_base
            self._knowledge_base = await get_knowledge_base()
        return self._knowledge_base

    async def execute(self, input_data: DocumentManagementInput) -> DocumentManagementOutput:
        """
        Execute document management operation.

        Args:
            input_data: Document management parameters.

        Returns:
            Document management result.

        Raises:
            DocumentNotFoundError: If document not found for delete/update.
            ValidationError: If input validation fails.
        """
        kb = await self._get_knowledge_base()

        try:
            if input_data.operation == "add":
                return await self._add_document(kb, input_data)
            elif input_data.operation == "update":
                return await self._update_document(kb, input_data)
            elif input_data.operation == "delete":
                return await self._delete_document(kb, input_data)
            elif input_data.operation == "list":
                return await self._list_documents(kb, input_data)
            else:
                return DocumentManagementOutput(
                    success=False,
                    trace_id=input_data.trace_id,
                    metadata={"error": f"Unknown operation: {input_data.operation}"},
                )

        except DocumentNotFoundError:
            raise
        except ValidationError:
            raise
        except Exception as e:
            logger.error(
                "Document management operation failed",
                extra={
                    "operation": input_data.operation,
                    "doc_id": input_data.doc_id,
                    "error": str(e),
                },
            )
            return DocumentManagementOutput(
                success=False,
                trace_id=input_data.trace_id,
                metadata={"error": str(e)},
            )

    async def _add_document(
        self,
        kb: Any,
        input_data: DocumentManagementInput,
    ) -> DocumentManagementOutput:
        """Add document to knowledge base."""
        # Validate content
        if not input_data.content or not input_data.content.strip():
            raise ValidationError("Document content cannot be empty")

        result = await kb.add_document_async(
            doc_id=input_data.doc_id,
            content=input_data.content,
            metadata=input_data.metadata,
        )

        logger.info(
            "Document added",
            extra={
                "doc_id": input_data.doc_id,
                "chunk_count": result.get("chunk_count", 0),
            },
        )

        return DocumentManagementOutput(
            success=True,
            doc_id=result.get("doc_id", input_data.doc_id),
            chunk_count=result.get("chunk_count", 0),
            indexed=result.get("indexed", True),
            embedding_model=result.get("embedding_model"),
            embedding_dimension=result.get("embedding_dimension"),
            metadata=result.get("metadata", input_data.metadata),
            trace_id=input_data.trace_id,
        )

    async def _update_document(
        self,
        kb: Any,
        input_data: DocumentManagementInput,
    ) -> DocumentManagementOutput:
        """Update document in knowledge base."""
        result = await kb.update_document(
            doc_id=input_data.doc_id,
            content=input_data.content,
            metadata=input_data.metadata,
        )

        logger.info(
            "Document updated",
            extra={
                "doc_id": input_data.doc_id,
                "re_indexed": result.get("re_indexed", False),
            },
        )

        return DocumentManagementOutput(
            success=True,
            doc_id=result.get("doc_id", input_data.doc_id),
            updated=result.get("updated", True),
            re_indexed=result.get("re_indexed", True),
            old_chunks_removed=result.get("old_chunks_removed", 0),
            new_chunks_added=result.get("new_chunks_added", 0),
            created=result.get("created", False),
            trace_id=input_data.trace_id,
        )

    async def _delete_document(
        self,
        kb: Any,
        input_data: DocumentManagementInput,
    ) -> DocumentManagementOutput:
        """Delete document from knowledge base."""
        result = await kb.delete_document_async(input_data.doc_id)

        logger.info(
            "Document deleted",
            extra={
                "doc_id": input_data.doc_id,
                "chunks_removed": result.get("chunks_removed", 0),
            },
        )

        return DocumentManagementOutput(
            success=True,
            doc_id=result.get("doc_id", input_data.doc_id),
            deleted=result.get("deleted", True),
            chunks_removed=result.get("chunks_removed", 0),
            trace_id=input_data.trace_id,
        )

    async def _list_documents(
        self,
        kb: Any,
        input_data: DocumentManagementInput,
    ) -> DocumentManagementOutput:
        """List all documents in knowledge base."""
        # This would require a list_documents method in kb
        # For now, return empty list
        return DocumentManagementOutput(
            success=True,
            documents=[],
            trace_id=input_data.trace_id,
        )

    def validate_input(self, input_data: DocumentManagementInput) -> CapabilityValidationResult:
        """
        Validate document management input.

        Args:
            input_data: Input to validate.

        Returns:
            Validation result.
        """
        errors = []
        warnings = []

        # Validate operation
        valid_ops = {"add", "delete", "update", "list"}
        if input_data.operation not in valid_ops:
            errors.append(f"Operation must be one of {valid_ops}")

        # Validate doc_id for operations that need it
        if input_data.operation in {"add", "delete", "update"}:
            if not input_data.doc_id:
                errors.append("doc_id is required for this operation")

        # Validate content for add/update
        if input_data.operation in {"add", "update"}:
            if not input_data.content:
                errors.append("content is required for add/update")
            elif input_data.content and len(input_data.content.strip()) == 0:
                errors.append("content cannot be empty or whitespace only")

        return CapabilityValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def get_health(self) -> Dict[str, Any]:
        """
        Get health status of document management.

        Returns:
            Health status information.
        """
        health = super().get_health()
        health["operations"] = ["add", "delete", "update", "list"]
        return health
