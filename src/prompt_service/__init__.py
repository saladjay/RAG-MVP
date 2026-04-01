"""
Prompt Management Service.

A FastAPI-based service for managing, retrieving, and analyzing
prompt templates with A/B testing, versioning, and analytics support.

Main components:
- PromptRetrievalService: Retrieve and render prompts
- PromptManagementService: CRUD operations for templates
- ABTestingService: A/B testing for prompt variants
- TraceAnalysisService: Analytics and insights
- VersionControlService: Version history and rollback

Example usage:
    from prompt_service.client import create_client

    client = create_client()
    response = await client.get_prompt(
        template_id="my_prompt",
        variables={"user_input": "Hello"}
    )
    print(response.content)
"""

from prompt_service.client import create_client
from prompt_service.client.sdk import PromptClient
from prompt_service.client.exceptions import (
    PromptServiceError,
    PromptNotFoundError,
    PromptValidationError,
    PromptServiceUnavailableError,
)

__version__ = "0.1.0"
__all__ = [
    "create_client",
    "PromptClient",
    "PromptServiceError",
    "PromptNotFoundError",
    "PromptValidationError",
    "PromptServiceUnavailableError",
]
