"""
RAG Service API client for E2E testing.

Handles HTTP communication with RAG Service including
query execution, health checks, and error handling.
"""

import asyncio
from typing import Any, Dict, Optional

import httpx

from e2e_test.core.exceptions import RAGClientError, RAGConnectionError, RAGServerError, RAGTimeoutError
from e2e_test.core.logger import get_logger


class RAGClient:
    """Client for communicating with RAG Service API.

    Provides async methods for querying the RAG Service and checking health.
    """

    DEFAULT_QUERY_ENDPOINT = "/api/v1/ai/agent"
    DEFAULT_HEALTH_ENDPOINT = "/health"

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout_seconds: int = 30,
        retry_count: int = 3,
    ) -> None:
        """Initialize RAG client.

        Args:
            base_url: Base URL of RAG Service
            timeout_seconds: Request timeout in seconds
            retry_count: Number of retry attempts on failure
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout_seconds
        self.retry_count = retry_count
        self.logger = get_logger()

    def _get_timeout(self) -> httpx.Timeout:
        """Create httpx timeout configuration.

        Returns:
            Timeout instance
        """
        return httpx.Timeout(
            connect=5.0,
            read=float(self.timeout),
            write=5.0,
            pool=float(self.timeout)
        )

    async def query(
        self,
        question: str,
        trace_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Query the RAG Service with a question.

        Args:
            question: User question to submit
            trace_id: Optional trace ID for observability

        Returns:
            Response dictionary containing:
            - answer: Generated answer text
            - trace_id: Trace ID for correlation
            - source_documents: List of retrieved document references
            - metadata: Additional response metadata

        Raises:
            RAGConnectionError: Network/connection failure
            RAGTimeoutError: Request timeout
            RAGServerError: 5xx server error
            RAGClientError: 4xx client error
        """
        url = f"{self.base_url}{self.DEFAULT_QUERY_ENDPOINT}"

        # Generate trace ID if not provided
        if trace_id is None:
            import uuid
            trace_id = f"e2e-test-{uuid.uuid4()}"

        payload = {
            "question": question,
            "trace_id": trace_id
        }

        self.logger.debug(
            "Sending RAG query",
            url=url,
            trace_id=trace_id,
            question=question[:100] + "..." if len(question) > 100 else question
        )

        last_error = None

        for attempt in range(self.retry_count + 1):
            try:
                async with httpx.AsyncClient(timeout=self._get_timeout()) as client:
                    response = await client.post(
                        url,
                        json=payload,
                        headers={"Content-Type": "application/json"}
                    )

                    # Handle HTTP errors
                    if response.status_code >= 500:
                        raise RAGServerError(
                            f"Server error: {response.status_code}",
                            status_code=response.status_code
                        )
                    elif response.status_code >= 400:
                        error_data = {}
                        try:
                            if response.headers.get("content-type", "").startswith("application/json"):
                                error_data = response.json().get("error", {})
                        except Exception:
                            pass
                        raise RAGClientError(
                            error_data.get("message", f"Client error: {response.status_code}"),
                            status_code=response.status_code
                        )

                    # Parse successful response
                    data = response.json()
                    self.logger.debug(
                        "RAG query successful",
                        trace_id=trace_id,
                        status_code=response.status_code
                    )
                    return data

            except httpx.TimeoutException as e:
                last_error = RAGTimeoutError(
                    f"Request timeout after {self.timeout}s",
                    timeout_seconds=self.timeout
                )
                self.logger.warning(
                    f"Query timeout (attempt {attempt + 1}/{self.retry_count + 1})",
                    trace_id=trace_id,
                    timeout_seconds=self.timeout
                )

            except httpx.ConnectError as e:
                last_error = RAGConnectionError(
                    f"Connection failed: {e}",
                    url=self.base_url
                )
                self.logger.warning(
                    f"Connection error (attempt {attempt + 1}/{self.retry_count + 1})",
                    trace_id=trace_id,
                    url=self.base_url
                )

            except (RAGServerError, RAGClientError):
                # Don't retry HTTP errors (4xx, 5xx)
                raise

            except Exception as e:
                last_error = RAGConnectionError(
                    f"Unexpected error: {e}",
                    url=self.base_url
                )
                self.logger.error(
                    f"Unexpected error during query (attempt {attempt + 1}/{self.retry_count + 1})",
                    trace_id=trace_id,
                    error=str(e)
                )

            # Retry with backoff if not the last attempt
            if attempt < self.retry_count:
                await asyncio.sleep(1.0 * (attempt + 1))

        # All retries exhausted
        raise last_error

    async def health_check(self) -> bool:
        """Check if RAG Service is healthy.

        Returns:
            True if service is healthy, False otherwise
        """
        url = f"{self.base_url}{self.DEFAULT_HEALTH_ENDPOINT}"

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)

                is_healthy = response.status_code == 200

                if is_healthy:
                    self.logger.debug("RAG Service health check passed", url=url)
                else:
                    self.logger.warning(
                        "RAG Service health check failed",
                        url=url,
                        status_code=response.status_code
                    )

                return is_healthy

        except Exception as e:
            self.logger.warning(
                "RAG Service health check error",
                url=url,
                error=str(e)
            )
            return False
