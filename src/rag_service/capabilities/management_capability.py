"""
Unified Management Capability for RAG Service.

Consolidates document management, KB upload, and model discovery:
- DocumentManagement → document CRUD
- MilvusKBUpload → Milvus knowledge base upload
- ModelDiscovery → list available models

API Reference:
- Location: src/rag_service/capabilities/management_capability.py
"""

import time
import uuid
from typing import Any, Dict, List, Optional

from rag_service.api.unified_schemas import DocumentRequest, DocumentResponse
from rag_service.capabilities.base import (
    Capability,
    CapabilityInput,
    CapabilityOutput,
    CapabilityValidationResult,
)
from rag_service.config import get_settings
from rag_service.core.logger import get_logger

logger = get_logger(__name__)


class ManagementCapability(Capability[DocumentRequest, DocumentResponse]):
    """Unified management capability for documents and models.

    Consolidates DocumentManagement, MilvusKBUpload, and ModelDiscovery
    into a single capability with operation-based routing.
    """

    async def execute(self, input_data: DocumentRequest) -> DocumentResponse:
        """Execute document management operation.

        Args:
            input_data: Document request with operation field.

        Returns:
            DocumentResponse with operation result.

        Raises:
            ValueError: If operation is invalid or required fields are missing.
        """
        trace_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        if input_data.operation == "upload":
            return await self._upload_document(input_data, trace_id)
        elif input_data.operation == "delete":
            return await self._delete_document(input_data, trace_id)
        elif input_data.operation == "update":
            return await self._update_document(input_data, trace_id)
        else:
            raise ValueError(f"Unknown operation: {input_data.operation}")

    async def _upload_document(self, input_data: DocumentRequest, trace_id: str) -> DocumentResponse:
        """Upload document to knowledge base."""
        try:
            from rag_service.capabilities.milvus_kb_upload import (
                MilvusKBUploadCapability,
                MilvusKBUploadInput,
            )

            settings = get_settings()
            chunk_size = input_data.chunk_size or settings.milvus.chunk_size
            chunk_overlap = input_data.chunk_overlap or settings.milvus.chunk_overlap

            capability = MilvusKBUploadCapability(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )

            upload_input = MilvusKBUploadInput(
                form_title=input_data.title or "Untitled",
                file_content=input_data.content or "",
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                document_id=input_data.doc_id,
                trace_id=trace_id,
            )

            result = await capability.execute(upload_input)

            return DocumentResponse(
                success=result.success,
                doc_id=result.document_id,
                operation="upload",
                chunk_count=result.chunk_count,
                trace_id=trace_id,
            )

        except Exception as e:
            logger.error(f"Document upload failed: {e}", extra={"trace_id": trace_id})
            raise

    async def _delete_document(self, input_data: DocumentRequest, trace_id: str) -> DocumentResponse:
        """Delete document from knowledge base."""
        if not input_data.doc_id:
            raise ValueError("doc_id is required for delete operation")

        try:
            from rag_service.capabilities.document_management import (
                DocumentManagementCapability,
                DocumentManagementInput,
            )

            capability = DocumentManagementCapability()
            dm_input = DocumentManagementInput(
                operation="delete",
                doc_id=input_data.doc_id,
                trace_id=trace_id,
            )
            result = await capability.execute(dm_input)

            return DocumentResponse(
                success=True,
                doc_id=input_data.doc_id,
                operation="delete",
                chunk_count=0,
                trace_id=trace_id,
            )

        except Exception as e:
            logger.error(f"Document delete failed: {e}", extra={"trace_id": trace_id})
            raise

    async def _update_document(self, input_data: DocumentRequest, trace_id: str) -> DocumentResponse:
        """Update document in knowledge base."""
        if not input_data.doc_id:
            raise ValueError("doc_id is required for update operation")

        return await self._upload_document(input_data, trace_id)

    async def list_models(self) -> List[Dict[str, Any]]:
        """List available models via LiteLLM gateway.

        Returns:
            List of model information dictionaries.
        """
        try:
            from rag_service.capabilities.model_discovery import ModelDiscoveryCapability
            capability = ModelDiscoveryCapability()
            result = await capability.get_health()
            return result.get("models", [])
        except Exception as e:
            logger.warning(f"Model discovery failed: {e}")
            return []

    def validate_input(self, input_data: DocumentRequest) -> CapabilityValidationResult:
        """Validate document request."""
        errors = []

        if input_data.operation in ("upload", "update") and not input_data.content:
            errors.append(f"content is required for {input_data.operation} operation")

        if input_data.operation in ("update", "delete") and not input_data.doc_id:
            errors.append(f"doc_id is required for {input_data.operation} operation")

        return CapabilityValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=[],
        )

    async def get_health(self) -> Dict[str, Any]:
        """Get health status of management components."""
        health = await super().get_health()

        try:
            from rag_service.inference.gateway import get_gateway
            gateway = await get_gateway()
            health["models"] = gateway.list_models() if hasattr(gateway, "list_models") else []
            health["status"] = "healthy"
        except Exception as e:
            health["status"] = "degraded"
            health["error"] = str(e)

        return health
