"""
Python Client SDK for Prompt Management Service.

This SDK provides a convenient Python interface for interacting with
the Prompt Management Service without dealing with HTTP directly.

Example usage:
    from prompt_service.client import PromptClient

    client = PromptClient(base_url="http://localhost:8000")

    # Retrieve a prompt
    response = await client.get_prompt(
        template_id="financial_analysis",
        variables={"user_input": "Analyze AAPL stock"}
    )

    # List all prompts
    prompts = await client.list_prompts()

    # Get prompt info
    info = await client.get_prompt_info("financial_analysis")
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

from prompt_service.client.exceptions import (
    ABTestNotFoundError,
    PromptNotFoundError,
    PromptServiceUnavailableError,
    PromptServiceError,
    PromptValidationError,
)
from prompt_service.client.models import (
    HealthStatus,
    PromptInfo,
    PromptListResponse,
    PromptOptions,
    PromptResponse,
    PromptResponse as PromptRetrieveResponse,
    RetrievedDoc,
    Section,
)

logger = logging.getLogger(__name__)


class PromptClient:
    """Client for the Prompt Management Service.

    This client provides async methods for all service endpoints,
    with automatic retry logic and fallback handling.

    Attributes:
        base_url: Base URL of the prompt service
        timeout: Request timeout in seconds
        max_retries: Maximum number of retries
        _client: HTTP client for making requests
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: float = 30.0,
        max_retries: int = 3,
        api_key: Optional[str] = None,
    ):
        """Initialize the prompt client.

        Args:
            base_url: Base URL of the prompt service
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
            api_key: Optional API key for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

        # Configure HTTP client
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=httpx.Timeout(timeout),
        )

    async def close(self) -> None:
        """Close the HTTP client.

        Should be called when done using the client.
        """
        await self._client.aclose()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def health(self, detailed: bool = False) -> HealthStatus:
        """Check service health.

        Args:
            detailed: Whether to return detailed health information

        Returns:
            Health status

        Raises:
            PromptServiceUnavailableError: If service is unavailable
        """
        params = {"detailed": "true" if detailed else "false"}
        response = await self._request("GET", "/health", params=params)

        return HealthStatus(
            status=response.get("status"),
            version=response.get("version"),
            components=response.get("components", {}),
            uptime_ms=response.get("uptime_ms", 0.0),
        )

    async def get_prompt(
        self,
        template_id: str,
        variables: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        retrieved_docs: Optional[List[RetrievedDoc]] = None,
        options: Optional[PromptOptions] = None,
    ) -> PromptResponse:
        """Retrieve and render a prompt template.

        Args:
            template_id: The prompt template identifier
            variables: Variable values for interpolation
            context: Additional context (user_id, session_id, etc.)
            retrieved_docs: Retrieved documents for inclusion
            options: Retrieval options

        Returns:
            Rendered prompt with metadata

        Raises:
            PromptNotFoundError: If template not found
            PromptValidationError: If validation fails
            PromptServiceUnavailableError: If service unavailable
        """
        payload = {
            "variables": variables or {},
            "context": context or {},
            "retrieved_docs": [
                {"id": doc.id, "content": doc.content, "metadata": doc.metadata}
                for doc in (retrieved_docs or [])
            ],
            "options": {
                "version_id": options.version_id if options else None,
                "include_metadata": options.include_metadata if options else False,
            },
        }

        response = await self._request(
            "POST",
            f"/api/v1/prompts/{template_id}/retrieve",
            json=payload,
        )

        # Convert sections
        sections = None
        if response.get("sections"):
            sections = [
                Section(name=s["name"], content=s["content"])
                for s in response["sections"]
            ]

        return PromptResponse(
            content=response["content"],
            template_id=response["template_id"],
            version_id=response["version_id"],
            variant_id=response.get("variant_id"),
            sections=sections,
            metadata=response.get("metadata", {}),
            trace_id=response.get("trace_id"),
            from_cache=response.get("from_cache", False),
        )

    async def list_prompts(
        self,
        tag: str = "",
        search: str = "",
        page: int = 1,
        page_size: int = 20,
    ) -> PromptListResponse:
        """List all prompt templates.

        Args:
            tag: Filter by tag
            search: Search in name/description
            page: Page number
            page_size: Page size

        Returns:
            List of prompt templates

        Raises:
            PromptServiceUnavailableError: If service unavailable
        """
        params = {
            "tag": tag,
            "search": search,
            "page": page,
            "page_size": min(page_size, 100),
        }

        response = await self._request("GET", "/api/v1/prompts", params=params)

        # Convert prompts
        prompts = []
        for p in response.get("prompts", []):
            # Convert sections
            sections = [
                Section(name=s["name"], content=s["content"])
                for s in p.get("sections", [])
            ]

            # Convert variables
            variables = {}
            for name, var_def in p.get("variables", {}).items():
                variables[name] = VariableDef(
                    name=name,
                    description=var_def["description"],
                    type=var_def["type"],
                    default_value=var_def.get("default_value"),
                    is_required=var_def["is_required"],
                )

            from datetime import datetime

            prompts.append(PromptInfo(
                template_id=p["template_id"],
                name=p["name"],
                description=p["description"],
                version=p["version"],
                sections=sections,
                variables=variables,
                tags=p.get("tags", []),
                is_active=p["is_active"],
                is_published=p["is_published"],
                created_at=datetime.fromisoformat(p["created_at"]),
                updated_at=datetime.fromisoformat(p["updated_at"]),
                created_by=p["created_by"],
            ))

        return PromptListResponse(
            prompts=prompts,
            total=response["total"],
            page=response["page"],
            page_size=response["page_size"],
        )

    async def get_prompt_info(self, template_id: str) -> PromptInfo:
        """Get information about a specific prompt template.

        Args:
            template_id: Template identifier

        Returns:
            Prompt template information

        Raises:
            PromptNotFoundError: If template not found
            PromptServiceUnavailableError: If service unavailable
        """
        # Get from list and filter (simpler than dedicated endpoint)
        response = await self.list_prompts(search=template_id, page_size=100)

        for prompt in response.prompts:
            if prompt.template_id == template_id:
                return prompt

        raise PromptNotFoundError(template_id)

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make an HTTP request with retry logic.

        Args:
            method: HTTP method
            path: Request path
            params: Query parameters
            json: Request body

        Returns:
            Response data

        Raises:
            PromptServiceError: On error
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                response = await self._client.request(
                    method=method,
                    url=path,
                    params=params,
                    json=json,
                )

                # Handle error responses
                if response.status_code == 404:
                    data = response.json()
                    raise PromptNotFoundError(
                        template_id=data.get("template_id", "unknown"),
                        details=data,
                    )
                elif response.status_code == 400:
                    data = response.json()
                    raise PromptValidationError(
                        message=data.get("message", "Validation failed"),
                        validation_errors=data.get("details", {}).get("validation_errors", []),
                        details=data,
                    )
                elif response.status_code >= 500:
                    # Retry on server errors
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(0.5 * (attempt + 1))  # Backoff
                        continue

                    data = response.json()
                    raise PromptServiceUnavailableError(
                        message=data.get("message", "Service unavailable"),
                        details=data,
                    )

                # Success
                return response.json()

            except httpx.TimeoutException as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                raise PromptServiceUnavailableError(
                    message=f"Request timeout: {str(e)}"
                )
            except httpx.ConnectError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                raise PromptServiceUnavailableError(
                    message=f"Connection failed: {str(e)}"
                )
            except (PromptNotFoundError, PromptValidationError, PromptServiceUnavailableError):
                raise
            except Exception as e:
                raise PromptServiceError(
                    message=f"Unexpected error: {str(e)}"
                )

        # Should not reach here, but handle the case
        raise PromptServiceUnavailableError(
            message=f"Request failed after {self.max_retries} retries"
        )


def create_client(
    base_url: str = "http://localhost:8000",
    api_key: Optional[str] = None,
) -> PromptClient:
    """Create a new prompt client.

    Convenience function for creating a client.

    Args:
        base_url: Base URL of the prompt service
        api_key: Optional API key for authentication

    Returns:
        New PromptClient instance
    """
    return PromptClient(base_url=base_url, api_key=api_key)
