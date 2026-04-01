"""
Exception classes for Prompt Service SDK.

These exceptions mirror the service-side exceptions and provide
a clean API for client code to handle errors.
"""


class PromptServiceError(Exception):
    """Base exception for all prompt service errors.

    Raised when an unexpected error occurs in the prompt service.
    """

    def __init__(self, message: str, details: dict = None):
        """Initialize the exception.

        Args:
            message: Error message
            details: Additional error details
        """
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def __str__(self) -> str:
        """Return string representation."""
        return self.message


class PromptNotFoundError(PromptServiceError):
    """Raised when a prompt template is not found.

    This typically occurs when:
    - The template_id doesn't exist
    - The template exists but is not published
    - The template has been deleted
    """

    def __init__(self, template_id: str, details: dict = None):
        """Initialize the exception.

        Args:
            template_id: The template that was not found
            details: Additional error details
        """
        self.template_id = template_id
        message = f"Prompt template not found: {template_id}"
        super().__init__(message, details)


class PromptValidationError(PromptServiceError):
    """Raised when prompt validation fails.

    This typically occurs when:
    - Required variables are missing
    - Variable types don't match expected types
    - Template content is invalid
    """

    def __init__(self, message: str, validation_errors: list = None, details: dict = None):
        """Initialize the exception.

        Args:
            message: Error message
            validation_errors: List of specific validation errors
            details: Additional error details
        """
        self.validation_errors = validation_errors or []
        details = details or {}
        details["validation_errors"] = self.validation_errors
        super().__init__(message, details)


class PromptServiceUnavailableError(PromptServiceError):
    """Raised when the prompt service is unavailable.

    This typically occurs when:
    - The service endpoint is unreachable
    - The service times out
    - The service returns a server error
    """

    def __init__(self, message: str = "Prompt service unavailable", details: dict = None):
        """Initialize the exception.

        Args:
            message: Error message
            details: Additional error details
        """
        super().__init__(message, details)


class ABTestNotFoundError(PromptServiceError):
    """Raised when an A/B test is not found.

    This typically occurs when:
    - The test_id doesn't exist
    - The test has been archived
    """

    def __init__(self, test_id: str, details: dict = None):
        """Initialize the exception.

        Args:
            test_id: The test that was not found
            details: Additional error details
        """
        self.test_id = test_id
        message = f"A/B test not found: {test_id}"
        super().__init__(message, details)
