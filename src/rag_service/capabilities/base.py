"""
Base Capability class for RAG Service.

This module defines the abstract Capability interface that all capabilities
must implement. The Capability interface is the CORE ARCHITECTURE of the
RAG service, providing unified abstraction between HTTP endpoints and components.

Key Design Principles:
- HTTP endpoints ONLY interact with Capability interfaces
- Components (Phidata, LiteLLM, Milvus, Langfuse) are NEVER directly exposed
- Capabilities provide clean abstraction boundaries
- Capabilities enable component swapping without API changes
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

from rag_service.core.exceptions import RAGServiceError


# Generic types for input and output
InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


class CapabilityInput(BaseModel):
    """
    Base input model for capability execution.

    All capability inputs should inherit from this class.
    """

    trace_id: str = Field(default="", description="Trace ID for observability")


class CapabilityOutput(BaseModel):
    """
    Base output model for capability execution.

    All capability outputs should inherit from this class.
    """

    success: bool = Field(default=True, description="Whether execution succeeded")
    trace_id: str = Field(default="", description="Trace ID for observability")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class CapabilityValidationResult(BaseModel):
    """
    Result of input validation.

    Attributes:
        is_valid: Whether the input is valid.
        errors: List of validation errors.
        warnings: List of validation warnings.
    """

    is_valid: bool = Field(..., description="Whether validation passed")
    errors: list[str] = Field(default_factory=list, description="Validation errors")
    warnings: list[str] = Field(default_factory=list, description="Validation warnings")


class Capability(ABC, Generic[InputT, OutputT]):
    """
    Abstract base class for all capabilities.

    This class defines the interface that all capabilities must implement.
    Capabilities provide unified abstraction over underlying components
    (Phidata, LiteLLM, Milvus, Langfuse) and are the ONLY way HTTP
    endpoints interact with service components.

    All capabilities must:
    1. Inherit from this base class
    2. Implement execute() method for main functionality
    3. Implement validate_input() method for input validation
    4. Include proper error handling with RAGServiceError subclasses
    5. Support trace_id propagation for observability

    Example:
        class MyCapability(Capability[MyInput, MyOutput]):
            async def execute(self, input_data: MyInput) -> MyOutput:
                # Implementation here
                pass

            def validate_input(self, input_data: MyInput) -> CapabilityValidationResult:
                # Validation here
                pass
    """

    def __init__(self) -> None:
        """Initialize the capability."""
        self._name = self.__class__.__name__

    @property
    def name(self) -> str:
        """Get the capability name."""
        return self._name

    @abstractmethod
    async def execute(self, input_data: InputT) -> OutputT:
        """
        Execute the capability with the given input.

        This is the main method that implements the capability's functionality.
        All business logic goes here.

        Args:
            input_data: The input data for capability execution.

        Returns:
            The output of capability execution.

        Raises:
            RAGServiceError: If execution fails.
        """
        raise NotImplementedError(f"{self._name}.execute() not implemented")

    def validate_input(self, input_data: InputT) -> CapabilityValidationResult:
        """
        Validate input data before execution.

        This method is called before execute() to ensure input is valid.
        Subclasses should override this to implement specific validation.

        Args:
            input_data: The input data to validate.

        Returns:
            CapabilityValidationResult indicating if validation passed.
        """
        # Default implementation: always valid
        return CapabilityValidationResult(is_valid=True)

    async def safe_execute(self, input_data: InputT) -> tuple[OutputT, Optional[Exception]]:
        """
        Execute capability with error handling.

        This method wraps execute() in error handling logic to prevent
        capability failures from crashing the entire request.

        Args:
            input_data: The input data for capability execution.

        Returns:
            A tuple of (output, exception). If execution succeeded,
            exception is None. If execution failed, output may be None.
        """
        # Validate input first
        validation = self.validate_input(input_data)
        if not validation.is_valid:
            error = RAGServiceError(
                message=f"Invalid input to {self._name}",
                detail="; ".join(validation.errors),
            )
            # Return None output and error
            return None, error  # type: ignore

        try:
            output = await self.execute(input_data)
            return output, None
        except RAGServiceError:
            # Re-raise our own exceptions as-is
            raise
        except Exception as e:
            # Wrap unexpected exceptions
            error = RAGServiceError(
                message=f"Unexpected error in {self._name}",
                detail=str(e),
            )
            return None, error  # type: ignore

    def get_health(self) -> dict[str, Any]:
        """
        Get health status of the capability.

        This method should return health information about the capability
        and the underlying component it wraps.

        Returns:
            Dictionary with health status information.
        """
        return {
            "capability": self._name,
            "status": "healthy",
        }

    def __repr__(self) -> str:
        """Return string representation of the capability."""
        return f"{self._name}()"


class CapabilityRegistry:
    """
    Registry for managing capability instances.

    This class provides a central place to register and retrieve
    capability instances. The FastAPI app uses this registry to
    access capabilities.
    """

    def __init__(self) -> None:
        """Initialize the capability registry."""
        self._capabilities: dict[str, Capability] = {}

    def register(self, capability: Capability) -> None:
        """
        Register a capability instance.

        Args:
            capability: The capability to register.

        Raises:
            ValueError: If a capability with the same name is already registered.
        """
        name = capability.name
        if name in self._capabilities:
            raise ValueError(f"Capability '{name}' already registered")
        self._capabilities[name] = capability

    def get(self, name: str) -> Capability:
        """
        Get a registered capability by name.

        Args:
            name: The capability name.

        Returns:
            The capability instance.

        Raises:
            KeyError: If the capability is not registered.
        """
        if name not in self._capabilities:
            raise KeyError(f"Capability '{name}' not registered")
        return self._capabilities[name]

    def list_capabilities(self) -> list[str]:
        """
        List all registered capability names.

        Returns:
            List of capability names.
        """
        return list(self._capabilities.keys())

    def get_all_health(self) -> dict[str, dict[str, Any]]:
        """
        Get health status of all registered capabilities.

        Returns:
            Dictionary mapping capability names to health status.
        """
        return {
            name: capability.get_health()
            for name, capability in self._capabilities.items()
        }


# Global capability registry
_global_registry: Optional[CapabilityRegistry] = None


def get_capability_registry() -> CapabilityRegistry:
    """
    Get the global capability registry.

    Returns:
        The global CapabilityRegistry instance.
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = CapabilityRegistry()
    return _global_registry


def reset_capability_registry() -> None:
    """Reset the global capability registry (primarily for testing)."""
    global _global_registry
    _global_registry = None
