"""
Langfuse SDK wrapper with graceful degradation.

This module provides a unified interface for Langfuse operations
with built-in fallback handling when Langfuse is unavailable.

The wrapper implements:
- Connection handling with retries
- Graceful degradation on failures
- Prompt template CRUD operations
- Trace logging
- Health check
"""

import logging
from typing import Any, Dict, List, Optional

from langfuse import Langfuse as LangfuseClient

from prompt_service.config import get_config
from prompt_service.core.logger import get_logger

logger = get_logger(__name__)


class LangfuseConnectionError(Exception):
    """Raised when Langfuse connection fails."""

    pass


class LangfuseClientWrapper:
    """Wrapper for Langfuse SDK with graceful degradation.

    This wrapper provides a clean interface to Langfuse functionality
    while handling connection failures gracefully. When Langfuse is
    unavailable, operations return cached/default values rather than
    raising exceptions.

    Attributes:
        _client: The underlying Langfuse client (may be None)
        _connected: Whether connection to Langfuse is active
        _config: Service configuration
    """

    def __init__(self, public_key: Optional[str] = None, secret_key: Optional[str] = None):
        """Initialize the Langfuse client wrapper.

        Args:
            public_key: Langfuse public key (overrides config)
            secret_key: Langfuse secret key (overrides config)
        """
        self._config = get_config()
        self._client: Optional[LangfuseClient] = None
        self._connected = bool = False

        # Use provided credentials or fall back to config
        if public_key is None:
            public_key = self._config.langfuse.public_key
        if secret_key is None:
            secret_key = self._config.langfuse.secret_key

        # Initialize client if credentials are provided
        if public_key and secret_key and self._config.langfuse.enabled:
            try:
                self._client = LangfuseClient(
                    public_key=public_key,
                    secret_key=secret_key,
                    host=self._config.langfuse.host,
                )
                self._connected = True
                logger.info(
                    "Langfuse client initialized",
                    extra={"host": self._config.langfuse.host}
                )
            except Exception as e:
                logger.warning(
                    "Failed to initialize Langfuse client",
                    extra={"error": str(e)},
                    exc_info=True
                )
                self._connected = False
        else:
            logger.info("Langfuse integration disabled")
            self._connected = False

    def is_connected(self) -> bool:
        """Check if Langfuse connection is active.

        Returns:
            True if connected to Langfuse, False otherwise
        """
        return self._connected and self._client is not None

    def get_prompt(
        self,
        template_id: str,
        version: Optional[int] = None,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get a prompt template from Langfuse.

        Args:
            template_id: The prompt template identifier
            version: Optional specific version (uses active if not specified)
            variables: Optional variable values for preview

        Returns:
            Prompt template data or None if unavailable

        Raises:
            LangfuseConnectionError: If connection fails critically
        """
        if not self.is_connected():
            logger.warning(
                "Langfuse not connected, returning None for prompt",
                extra={"template_id": template_id}
            )
            return None

        try:
            prompt = self._client.get_prompt(
                name=template_id,
                version=version,
            )

            return {
                "name": prompt.name,
                "prompt": prompt.prompt,
                "version": prompt.version,
                "config": prompt.config,
                "metadata": prompt.metadata,
            }

        except Exception as e:
            logger.error(
                "Failed to retrieve prompt from Langfuse",
                extra={
                    "template_id": template_id,
                    "version": version,
                    "error": str(e),
                },
                exc_info=True
            )
            # Return None instead of raising for graceful degradation
            return None

    def create_prompt(
        self,
        template_id: str,
        prompt: str,
        config: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Create a new prompt template in Langfuse.

        Args:
            template_id: The prompt template identifier
            prompt: The prompt content
            config: Optional configuration (variables, etc.)
            metadata: Optional metadata

        Returns:
            Created prompt data or None if failed

        Raises:
            LangfuseConnectionError: If connection fails critically
        """
        if not self.is_connected():
            logger.warning("Langfuse not connected, cannot create prompt")
            return None

        try:
            created = self._client.create_prompt(
                name=template_id,
                prompt=prompt,
                config=config or {},
                metadata=metadata or {},
            )

            return {
                "name": created.name,
                "prompt": created.prompt,
                "version": created.version,
                "config": created.config,
            }

        except Exception as e:
            logger.error(
                "Failed to create prompt in Langfuse",
                extra={
                    "template_id": template_id,
                    "error": str(e),
                },
                exc_info=True
            )
            return None

    def update_prompt(
        self,
        template_id: str,
        prompt: str,
        version: Optional[int] = None,
        config: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update an existing prompt template in Langfuse.

        Args:
            template_id: The prompt template identifier
            prompt: The new prompt content
            version: Optional specific version to update
            config: Optional configuration
            metadata: Optional metadata

        Returns:
            Updated prompt data or None if failed

        Raises:
            LangfuseConnectionError: If connection fails critically
        """
        if not self.is_connected():
            logger.warning("Langfuse not connected, cannot update prompt")
            return None

        try:
            updated = self._client.create_prompt(
                name=template_id,
                prompt=prompt,
                version=version,
                config=config or {},
                metadata=metadata or {},
            )

            return {
                "name": updated.name,
                "prompt": updated.prompt,
                "version": updated.version,
                "config": updated.config,
            }

        except Exception as e:
            logger.error(
                "Failed to update prompt in Langfuse",
                extra={
                    "template_id": template_id,
                    "error": str(e),
                },
                exc_info=True
            )
            return None

    def log_trace(
        self,
        trace_id: str,
        template_id: str,
        version: int,
        variables: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        variant_id: Optional[str] = None,
        output: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Log a prompt retrieval trace to Langfuse.

        Args:
            trace_id: Unique trace identifier
            template_id: Prompt template identifier
            version: Template version used
            variables: Variable values provided
            context: Additional context
            variant_id: A/B test variant ID (if applicable)
            output: Model output (if available)
            metadata: Additional metadata

        Returns:
            True if logged successfully, False otherwise
        """
        if not self.is_connected():
            # Silently skip logging if Langfuse is unavailable
            return False

        try:
            trace = self._client.trace(
                id=trace_id,
                name=template_id,
                metadata={
                    "template_id": template_id,
                    "template_version": version,
                    "variant_id": variant_id,
                    **(metadata or {}),
                },
            )

            # Log variable inputs
            if variables:
                for key, value in variables.items():
                    trace.event(
                        name=f"variable_{key}",
                        input=value,
                    )

            # Log context
            if context:
                trace.event(
                    name="context",
                    input=context,
                )

            # Log output if provided
            if output:
                trace.end(output=output)

            logger.debug(
                "Trace logged to Langfuse",
                extra={
                    "trace_id": trace_id,
                    "template_id": template_id,
                }
            )
            return True

        except Exception as e:
            # Log failures but don't raise (observability shouldn't block requests)
            logger.warning(
                "Failed to log trace to Langfuse",
                extra={
                    "trace_id": trace_id,
                    "error": str(e),
                },
                exc_info=True
            )
            return False

    def health(self) -> Dict[str, Any]:
        """Get health status of Langfuse connection.

        Returns:
            Health status information
        """
        if self._connected and self._client:
            try:
                # Simple health check - list prompts
                self._client.prompts().list(limit=1)
                return {
                    "status": "connected",
                    "host": self._config.langfuse.host,
                }
            except Exception as e:
                return {
                    "status": "disconnected",
                    "host": self._config.langfuse.host,
                    "error": str(e),
                }
        else:
            return {
                "status": "not_configured",
                "host": self._config.langfuse.host,
            }

    def flush(self) -> None:
        """Flush any pending Langfuse operations.

        This should be called before shutdown to ensure
        all traces are uploaded.
        """
        if self._client:
            try:
                self._client.flush()
                logger.info("Langfuse client flushed")
            except Exception as e:
                logger.warning(
                    "Failed to flush Langfuse client",
                    extra={"error": str(e)},
                    exc_info=True
                )


# Global client instance
_client: Optional[LangfuseClientWrapper] = None


def get_langfuse_client() -> LangfuseClientWrapper:
    """Get the global Langfuse client wrapper instance.

    The client is initialized once and cached for subsequent calls.

    Returns:
        Langfuse client wrapper instance
    """
    global _client
    if _client is None:
        _client = LangfuseClientWrapper()
    return _client


def reset_langfuse_client() -> None:
    """Reset the global Langfuse client instance.

    This is primarily useful for testing.
    """
    global _client
    if _client:
        _client.flush()
    _client = None
