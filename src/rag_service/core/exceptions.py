"""
Custom exception classes for RAG Service.

This module defines the exception hierarchy used throughout the application.
All exceptions inherit from RAGServiceError for consistent error handling.
"""

from typing import Any, Optional


class RAGServiceError(Exception):
    """
    Base exception for all RAG service errors.

    This exception should be used as the base class for all custom
    exceptions in the application, enabling consistent error handling
    and user-friendly error messages.

    Attributes:
        message: Human-readable error message.
        detail: Additional error details for debugging.
        error_code: Optional error code for documentation lookup.
    """

    def __init__(
        self,
        message: str,
        detail: Optional[str] = None,
        error_code: Optional[str] = None,
    ) -> None:
        """
        Initialize RAGServiceError.

        Args:
            message: Human-readable error message.
            detail: Additional error details for debugging.
            error_code: Optional error code for documentation lookup.
        """
        super().__init__(message)
        self.message = message
        self.detail = detail
        self.error_code = error_code

    def __str__(self) -> str:
        """Return formatted error message."""
        parts = [f"Error: {self.message}"]
        if self.detail:
            parts.append(f"Detail: {self.detail}")
        if self.error_code:
            parts.append(f"Code: {self.error_code}")
        return " | ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert exception to dictionary for API responses.

        Returns:
            Dictionary representation of the error.
        """
        result: dict[str, Any] = {"message": self.message}
        if self.detail:
            result["detail"] = self.detail
        if self.error_code:
            result["code"] = self.error_code
        return result


# Configuration Errors


class ConfigurationError(RAGServiceError):
    """Exception raised when configuration is invalid or missing."""

    def __init__(self, message: str, detail: Optional[str] = None) -> None:
        """
        Initialize ConfigurationError.

        Args:
            message: Description of the configuration error.
            detail: Additional details about the error.
        """
        super().__init__(message, detail, "CONFIG_ERROR")


# Component Errors


class ComponentError(RAGServiceError):
    """Base class for component-related errors."""

    def __init__(
        self,
        component: str,
        message: str,
        detail: Optional[str] = None,
    ) -> None:
        """
        Initialize ComponentError.

        Args:
            component: Name of the component that failed.
            message: Error message.
            detail: Additional details.
        """
        super().__init__(f"{component}: {message}", detail, "COMPONENT_ERROR")
        self.component = component


class MilvusError(ComponentError):
    """Exception raised when Milvus operations fail."""

    def __init__(self, message: str, detail: Optional[str] = None) -> None:
        """Initialize MilvusError."""
        super().__init__("Milvus", message, detail)
        self.error_code = "MILVUS_ERROR"


class LiteLLMError(ComponentError):
    """Exception raised when LiteLLM operations fail."""

    def __init__(self, message: str, detail: Optional[str] = None) -> None:
        """Initialize LiteLLMError."""
        super().__init__("LiteLLM", message, detail)
        self.error_code = "LITELLM_ERROR"


class LangfuseError(ComponentError):
    """Exception raised when Langfuse operations fail."""

    def __init__(self, message: str, detail: Optional[str] = None) -> None:
        """Initialize LangfuseError."""
        super().__init__("Langfuse", message, detail)
        self.error_code = "LANGFUSE_ERROR"


class PhidataError(ComponentError):
    """Exception raised when Phidata operations fail."""

    def __init__(self, message: str, detail: Optional[str] = None) -> None:
        """Initialize PhidataError."""
        super().__init__("Phidata", message, detail)
        self.error_code = "PHIDATA_ERROR"


# Knowledge Base Errors


class KnowledgeBaseError(RAGServiceError):
    """Base class for knowledge base errors."""

    def __init__(
        self,
        message: str,
        detail: Optional[str] = None,
    ) -> None:
        """Initialize KnowledgeBaseError."""
        super().__init__(message, detail, "KNOWLEDGE_BASE_ERROR")


class DocumentNotFoundError(KnowledgeBaseError):
    """Exception raised when a document is not found."""

    def __init__(self, doc_id: str, detail: Optional[str] = None) -> None:
        """Initialize DocumentNotFoundError."""
        super().__init__(f"Document '{doc_id}' not found", detail)
        self.doc_id = doc_id


class DocumentAlreadyExistsError(KnowledgeBaseError):
    """Exception raised when trying to add a document that already exists."""

    def __init__(self, doc_id: str, detail: Optional[str] = None) -> None:
        """Initialize DocumentAlreadyExistsError."""
        super().__init__(f"Document '{doc_id}' already exists", detail)
        self.doc_id = doc_id


class EmbeddingError(KnowledgeBaseError):
    """Exception raised when embedding generation fails."""

    def __init__(self, message: str, detail: Optional[str] = None) -> None:
        """Initialize EmbeddingError."""
        super().__init__(f"Embedding generation failed: {message}", detail)


class RetrievalError(KnowledgeBaseError):
    """Exception raised when knowledge base retrieval fails."""

    def __init__(self, message: str, detail: Optional[str] = None) -> None:
        """Initialize RetrievalError."""
        super().__init__(f"Retrieval failed: {message}", detail)


class NoResultsError(RetrievalError):
    """Exception raised when no results are found for a query."""

    def __init__(self, query: str, detail: Optional[str] = None) -> None:
        """Initialize NoResultsError."""
        super().__init__(f"No results found for query: '{query}'", detail)
        self.query = query


# Inference Errors


class InferenceError(RAGServiceError):
    """Base class for inference errors."""

    def __init__(
        self,
        message: str,
        detail: Optional[str] = None,
    ) -> None:
        """Initialize InferenceError."""
        super().__init__(message, detail, "INFERENCE_ERROR")


class ModelNotFoundError(InferenceError):
    """Exception raised when a requested model is not available."""

    def __init__(self, model: str, detail: Optional[str] = None) -> None:
        """Initialize ModelNotFoundError."""
        super().__init__(f"Model '{model}' not found", detail)
        self.model = model


class GenerationError(InferenceError):
    """Exception raised when text generation fails."""

    def __init__(self, message: str, detail: Optional[str] = None) -> None:
        """Initialize GenerationError."""
        super().__init__(f"Generation failed: {message}", detail)


# Observability Errors


class ObservabilityError(RAGServiceError):
    """Base class for observability errors."""

    def __init__(
        self,
        message: str,
        detail: Optional[str] = None,
    ) -> None:
        """Initialize ObservabilityError."""
        super().__init__(message, detail, "OBSERVABILITY_ERROR")


class TraceError(ObservabilityError):
    """Exception raised when trace operations fail."""

    def __init__(self, trace_id: str, message: str, detail: Optional[str] = None) -> None:
        """Initialize TraceError."""
        super().__init__(f"Trace '{trace_id}': {message}", detail)
        self.trace_id = trace_id


# API Errors


class APIError(RAGServiceError):
    """Base class for API-related errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        detail: Optional[str] = None,
    ) -> None:
        """
        Initialize APIError.

        Args:
            message: Error message.
            status_code: HTTP status code to return.
            detail: Additional details.
        """
        super().__init__(message, detail, "API_ERROR")
        self.status_code = status_code


class ValidationError(APIError):
    """Exception raised when request validation fails."""

    def __init__(self, message: str, detail: Optional[str] = None) -> None:
        """Initialize ValidationError."""
        super().__init__(message, 422, detail)


class NotFoundError(APIError):
    """Exception raised when a requested resource is not found."""

    def __init__(self, resource: str, identifier: str, detail: Optional[str] = None) -> None:
        """Initialize NotFoundError."""
        super().__init__(f"{resource} '{identifier}' not found", 404, detail)
        self.resource = resource
        self.identifier = identifier


class RateLimitError(APIError):
    """Exception raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
        detail: Optional[str] = None,
    ) -> None:
        """Initialize RateLimitError."""
        super().__init__(message, 429, detail)
        self.retry_after = retry_after


# Agent Errors


class AgentError(RAGServiceError):
    """Base class for agent orchestration errors."""

    def __init__(
        self,
        message: str,
        detail: Optional[str] = None,
    ) -> None:
        """Initialize AgentError."""
        super().__init__(message, detail, "AGENT_ERROR")


class ToolExecutionError(AgentError):
    """Exception raised when agent tool execution fails."""

    def __init__(
        self,
        tool_name: str,
        message: str,
        detail: Optional[str] = None,
    ) -> None:
        """Initialize ToolExecutionError."""
        super().__init__(f"Tool '{tool_name}' failed: {message}", detail)
        self.tool_name = tool_name


class AgentTimeoutError(AgentError):
    """Exception raised when agent execution times out."""

    def __init__(
        self,
        timeout: float,
        detail: Optional[str] = None,
    ) -> None:
        """Initialize AgentTimeoutError."""
        super().__init__(f"Agent execution timed out after {timeout}s", detail)
        self.timeout = timeout
