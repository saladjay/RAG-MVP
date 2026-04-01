"""
Custom exception hierarchy for Prompt Management Service.

This module defines all service-specific exceptions that provide
structured error information for API responses and logging.

Exception Hierarchy:
- PromptServiceError (base)
  - PromptNotFoundError
  - PromptValidationError
  - PromptServiceUnavailableError
  - ABTestNotFoundError
  - ABTestValidationError
"""

from typing import Any, Dict, List, Optional


class PromptServiceError(Exception):
    """Base exception for all prompt service errors.

    All service exceptions inherit from this class to enable
    consistent error handling and response formatting.

    Attributes:
        message: Human-readable error message
        error_code: Machine-readable error identifier
        details: Additional error context
        trace_id: Request trace identifier for debugging
    """

    def __init__(
        self,
        message: str,
        error_code: str = "PROMPT_SERVICE_ERROR",
        details: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error message
            error_code: Machine-readable error identifier
            details: Additional error context
            trace_id: Request trace identifier
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.trace_id = trace_id

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API response.

        Returns:
            Dictionary representation of the error
        """
        result = {
            "error": self.error_code,
            "message": self.message,
        }
        if self.details:
            result["details"] = self.details
        if self.trace_id:
            result["trace_id"] = self.trace_id
        return result


class PromptNotFoundError(PromptServiceError):
    """Raised when a requested prompt template does not exist.

    This exception is used when:
    - A template_id is not found in the system
    - A specific version of a template is requested but doesn't exist
    - A template exists but is not published/active
    """

    def __init__(
        self,
        template_id: str,
        version: Optional[int] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        """Initialize the exception.

        Args:
            template_id: The template identifier that was not found
            version: Optional version number if specific version was requested
            trace_id: Request trace identifier
        """
        if version:
            message = f"Prompt template '{template_id}' version {version} not found"
        else:
            message = f"Prompt template '{template_id}' not found"

        super().__init__(
            message=message,
            error_code="PROMPT_NOT_FOUND",
            details={"template_id": template_id, "version": version} if version else {"template_id": template_id},
            trace_id=trace_id,
        )


class PromptValidationError(PromptServiceError):
    """Raised when prompt template validation fails.

    This exception is used when:
    - Template ID format is invalid
    - Required variables are missing
    - Variable values fail validation
    - Template content exceeds size limits
    """

    def __init__(
        self,
        message: str,
        validation_errors: Optional[List[str]] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error message
            validation_errors: List of specific validation error messages
            trace_id: Request trace identifier
        """
        super().__init__(
            message=message,
            error_code="PROMPT_VALIDATION_ERROR",
            details={"validation_errors": validation_errors} if validation_errors else None,
            trace_id=trace_id,
        )
        self.validation_errors = validation_errors or []


class PromptServiceUnavailableError(PromptServiceError):
    """Raised when the prompt service is unavailable.

    This exception is used when:
    - Langfuse connection fails
    - Service is in degraded mode
    - External dependencies are unreachable

    The service may include fallback content when this error is raised.
    """

    def __init__(
        self,
        message: str = "Prompt service temporarily unavailable",
        fallback_provided: bool = False,
        fallback_content: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error message
            fallback_provided: Whether fallback content was provided
            fallback_content: The fallback content (if available)
            trace_id: Request trace identifier
        """
        super().__init__(
            message=message,
            error_code="SERVICE_UNAVAILABLE",
            details={
                "fallback_provided": fallback_provided,
            },
            trace_id=trace_id,
        )
        self.fallback_provided = fallback_provided
        self.fallback_content = fallback_content


class ABTestNotFoundError(PromptServiceError):
    """Raised when a requested A/B test does not exist.

    This exception is used when:
    - An A/B test ID is not found
    - A test exists but is in a non-queryable state
    """

    def __init__(
        self,
        test_id: str,
        trace_id: Optional[str] = None,
    ) -> None:
        """Initialize the exception.

        Args:
            test_id: The A/B test identifier that was not found
            trace_id: Request trace identifier
        """
        super().__init__(
            message=f"A/B test '{test_id}' not found",
            error_code="AB_TEST_NOT_FOUND",
            details={"test_id": test_id},
            trace_id=trace_id,
        )


class ABTestValidationError(PromptServiceError):
    """Raised when A/B test configuration validation fails.

    This exception is used when:
    - Traffic percentages don't sum to 100
    - Invalid variant configuration
    - Test already exists with same name
    """

    def __init__(
        self,
        message: str,
        validation_errors: Optional[List[str]] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        """Initialize the exception.

        Args:
            message: Human-readable error message
            validation_errors: List of specific validation error messages
            trace_id: Request trace identifier
        """
        super().__init__(
            message=message,
            error_code="AB_TEST_VALIDATION_ERROR",
            details={"validation_errors": validation_errors} if validation_errors else None,
            trace_id=trace_id,
        )
        self.validation_errors = validation_errors or []
