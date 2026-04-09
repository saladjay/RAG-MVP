"""
Milvus Knowledge Base Upload Capability.

This module provides document upload functionality for the Milvus-based
knowledge base, supporting automatic text chunking, embedding generation,
and hybrid search (vector + BM25) indexing.
"""

import time
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from rag_service.capabilities.base import (
    Capability,
    CapabilityInput,
    CapabilityOutput,
    CapabilityValidationResult,
)
from rag_service.core.exceptions import RetrievalError, EmbeddingError
from rag_service.core.logger import get_logger


logger = get_logger(__name__)


class MilvusKBUploadInput(CapabilityInput):
    """Input for Milvus KB document upload.

    Attributes:
        form_title: Document title/name
        file_content: Full document content text
        chunk_size: Maximum characters per chunk
        chunk_overlap: Character overlap between chunks
        document_id: Optional document identifier (auto-generated if not provided)
    """

    form_title: str = Field(..., min_length=1, max_length=512, description="Document title")
    file_content: str = Field(..., min_length=1, description="Document content text")
    chunk_size: int = Field(default=512, ge=100, le=4096, description="Chunk size in characters")
    chunk_overlap: int = Field(default=50, ge=0, le=512, description="Chunk overlap in characters")
    document_id: Optional[str] = Field(default=None, description="Optional document ID")

    @field_validator("form_title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        """Validate title is not just whitespace."""
        if not v or not v.strip():
            raise ValueError("form_title cannot be empty or whitespace only")
        return v.strip()

    @field_validator("file_content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate content is not just whitespace."""
        if not v or not v.strip():
            raise ValueError("file_content cannot be empty or whitespace only")
        return v

    @field_validator("chunk_overlap")
    @classmethod
    def validate_overlap(cls, v: int, info) -> int:
        """Validate overlap is less than chunk size."""
        chunk_size = info.data.get("chunk_size", 512)
        if v >= chunk_size:
            raise ValueError(f"chunk_overlap ({v}) must be less than chunk_size ({chunk_size})")
        return v


class MilvusKBUploadOutput(CapabilityOutput):
    """Output from Milvus KB document upload.

    Attributes:
        success: Whether upload succeeded
        document_id: Unique document identifier
        chunk_count: Number of chunks created
        inserted_count: Number of chunks inserted into Milvus
        timing_ms: Total processing time in milliseconds
        trace_id: Trace ID for observability
    """

    document_id: str = Field(..., description="Unique document identifier")
    chunk_count: int = Field(..., ge=0, description="Number of chunks created")
    inserted_count: int = Field(..., ge=0, description="Number of chunks inserted")
    timing_ms: float = Field(..., ge=0, description="Processing time in milliseconds")


class MilvusKBUploadCapability(Capability[MilvusKBUploadInput, MilvusKBUploadOutput]):
    """
    Capability for uploading documents to Milvus knowledge base.

    This capability handles:
    - Text chunking with overlap
    - Embedding generation using cloud embedding service
    - Document insertion into Milvus with hybrid search support
    - Automatic BM25 sparse vector generation via Milvus
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
    ) -> None:
        """Initialize the upload capability.

        Args:
            chunk_size: Default chunk size in characters
            chunk_overlap: Default chunk overlap in characters
        """
        super().__init__()
        self._default_chunk_size = chunk_size
        self._default_chunk_overlap = chunk_overlap

    def _chunk_text(
        self,
        text: str,
        chunk_size: int,
        overlap: int,
    ) -> List[Dict[str, Any]]:
        """
        Split text into overlapping chunks.

        Args:
            text: Input text to chunk
            chunk_size: Maximum characters per chunk
            overlap: Character overlap between chunks

        Returns:
            List of chunk dictionaries with text, start, end, chunk_index
        """
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
            # If we're at the end, don't apply overlap
            if end >= text_length:
                break
            start = end - overlap

        logger.debug(
            "Text chunking completed",
            extra={
                "original_length": text_length,
                "chunk_count": len(chunks),
                "chunk_size": chunk_size,
                "overlap": overlap,
            },
        )

        return chunks

    def validate_input(self, input_data: MilvusKBUploadInput) -> CapabilityValidationResult:
        """Validate upload input.

        Args:
            input_data: Upload input to validate

        Returns:
            Validation result with any errors or warnings
        """
        errors = []
        warnings = []

        # Check title length
        if len(input_data.form_title) > 512:
            errors.append("form_title must be 512 characters or less")

        # Check content is reasonable size
        content_length = len(input_data.file_content)
        if content_length > 10_000_000:  # 10MB limit
            errors.append("file_content exceeds maximum size of 10MB")

        # Validate chunk parameters
        if input_data.chunk_overlap >= input_data.chunk_size:
            errors.append("chunk_overlap must be less than chunk_size")

        # Warn about very small chunks
        if input_data.chunk_size < 100:
            warnings.append("chunk_size < 100 may result in poor embeddings")

        # Warn about large overlap
        if input_data.chunk_overlap > input_data.chunk_size / 2:
            warnings.append("chunk_overlap > 50% of chunk_size may cause redundancy")

        return CapabilityValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    async def execute(self, input_data: MilvusKBUploadInput) -> MilvusKBUploadOutput:
        """
        Execute document upload to Milvus.

        Args:
            input_data: Upload parameters

        Returns:
            Upload result with document ID and statistics

        Raises:
            RetrievalError: If upload fails
            EmbeddingError: If embedding generation fails
        """
        start_time = time.time()
        trace_id = input_data.trace_id or str(uuid.uuid4())[:8]

        # Generate document ID if not provided
        document_id = input_data.document_id or str(uuid.uuid4())

        logger.info(
            "Starting document upload",
            extra={
                "trace_id": trace_id,
                "document_id": document_id,
                "title": input_data.form_title[:50],
                "content_length": len(input_data.file_content),
            },
        )

        try:
            # 1. Chunk the text
            chunks = self._chunk_text(
                input_data.file_content,
                input_data.chunk_size,
                input_data.chunk_overlap,
            )

            if not chunks:
                raise RetrievalError(
                    message="No chunks created from content",
                    detail="Content may be empty or contain only whitespace",
                )

            logger.info(
                "Text chunking completed",
                extra={"trace_id": trace_id, "chunk_count": len(chunks)},
            )

            # 2. Generate embeddings for all chunks
            from rag_service.retrieval.embeddings import get_http_embedding_service

            embedding_service = await get_http_embedding_service()
            chunk_texts = [chunk["text"] for chunk in chunks]

            embeddings = await embedding_service.embed_batch(chunk_texts)

            if len(embeddings) != len(chunks):
                raise EmbeddingError(
                    message="Embedding count mismatch",
                    detail=f"Expected {len(chunks)} embeddings, got {len(embeddings)}",
                )

            logger.info(
                "Embedding generation completed",
                extra={
                    "trace_id": trace_id,
                    "embedding_count": len(embeddings),
                },
            )

            # 3. Prepare documents for insertion
            # Note: sparse_vector is auto-generated by Milvus BM25 function
            documents = []
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                documents.append({
                    "fileContent": chunk["text"],
                    "formTitle": input_data.form_title,
                    "document_id": document_id,
                    "chunk_index": chunk["chunk_index"],
                    "vector": embedding,
                    # sparse_vector is NOT included - auto-generated by Milvus
                })

            # 4. Insert into Milvus
            from rag_service.clients.milvus_kb_client import get_milvus_kb_client

            milvus_client = await get_milvus_kb_client()
            inserted_count = await milvus_client.insert_documents(documents)

            timing_ms = (time.time() - start_time) * 1000

            logger.info(
                "Document upload completed successfully",
                extra={
                    "trace_id": trace_id,
                    "document_id": document_id,
                    "chunk_count": len(chunks),
                    "inserted_count": inserted_count,
                    "timing_ms": timing_ms,
                },
            )

            return MilvusKBUploadOutput(
                success=True,
                document_id=document_id,
                chunk_count=len(chunks),
                inserted_count=inserted_count,
                timing_ms=timing_ms,
                trace_id=trace_id,
            )

        except RetrievalError:
            # Re-raise our own exceptions
            raise

        except Exception as e:
            logger.error(
                "Document upload failed",
                extra={
                    "trace_id": trace_id,
                    "document_id": document_id,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise RetrievalError(
                message="Failed to upload document to Milvus",
                detail=str(e),
            ) from e

    def get_health(self) -> Dict[str, Any]:
        """Get health status of the upload capability.

        Returns:
            Health status information
        """
        return {
            "capability": self._name,
            "status": "healthy",
            "default_chunk_size": self._default_chunk_size,
            "default_chunk_overlap": self._default_chunk_overlap,
        }
