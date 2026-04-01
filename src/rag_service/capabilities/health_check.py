"""
Health Check Capability for RAG Service.

This capability provides unified access to health status for all
service components. HTTP endpoints use this capability - they
NEVER access components directly.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from rag_service.capabilities.base import (
    Capability,
    CapabilityInput,
    CapabilityOutput,
    CapabilityValidationResult,
)


class HealthCheckInput(CapabilityInput):
    """
    Input for health check operations.

    Attributes:
        components: List of components to check (empty = all).
        detailed: Whether to return detailed health information.
    """

    components: List[str] = Field(default_factory=list, description="Components to check")
    detailed: bool = Field(default=False, description="Return detailed info")


class ComponentHealth(BaseModel):
    """
    Health status of a single component.

    Attributes:
        name: Component name.
        status: Health status (healthy, degraded, unhealthy).
        message: Status message.
        response_time_ms: Response time in milliseconds.
    """

    name: str = Field(..., description="Component name")
    status: str = Field(..., description="Health status")
    message: str = Field(default="", description="Status message")
    response_time_ms: Optional[float] = Field(default=None, description="Response time")


class HealthCheckOutput(CapabilityOutput):
    """
    Output from health check operations.

    Attributes:
        overall_status: Overall service health status.
        components: Health status of each component.
        uptime_ms: Service uptime in milliseconds.
    """

    overall_status: str = Field(default="healthy", description="Overall health")
    components: List[ComponentHealth] = Field(default_factory=list, description="Component health")
    uptime_ms: Optional[float] = Field(default=None, description="Uptime in ms")


class HealthCheckCapability(Capability[HealthCheckInput, HealthCheckOutput]):
    """
    Capability for health check operations.

    This capability checks the health of all service components
    and aggregates their status. HTTP endpoints use this capability
    to get service health information.

    Features:
    - Check all component health
    - Aggregate overall status
    - Support partial component checks
    - Detailed health information
    """

    def __init__(self, capabilities: Optional[Dict[str, Capability]] = None) -> None:
        """
        Initialize HealthCheckCapability.

        Args:
            capabilities: Dictionary of registered capabilities (injected dependency).
        """
        super().__init__()
        self._capabilities = capabilities or {}

    async def execute(self, input_data: HealthCheckInput) -> HealthCheckOutput:
        """
        Execute health check.

        Args:
            input_data: Health check parameters.

        Returns:
            Aggregated health status.
        """
        import time

        start_time = time.time()
        component_health: List[ComponentHealth] = []

        # Determine which components to check
        components_to_check = input_data.components if input_data.components else list(self._capabilities.keys())

        # Check each component
        for component_name in components_to_check:
            if component_name not in self._capabilities:
                component_health.append(ComponentHealth(
                    name=component_name,
                    status="unhealthy",
                    message="Component not found",
                ))
                continue

            try:
                capability = self._capabilities[component_name]
                health_info = capability.get_health()

                component_health.append(ComponentHealth(
                    name=component_name,
                    status=health_info.get("status", "healthy"),
                    message=health_info.get("message", ""),
                ))

            except Exception as e:
                component_health.append(ComponentHealth(
                    name=component_name,
                    status="unhealthy",
                    message=f"Health check failed: {e}",
                ))

        # Determine overall status
        if any(c.status == "unhealthy" for c in component_health):
            overall_status = "unhealthy"
        elif any(c.status == "degraded" for c in component_health):
            overall_status = "degraded"
        else:
            overall_status = "healthy"

        elapsed_ms = (time.time() - start_time) * 1000

        return HealthCheckOutput(
            overall_status=overall_status,
            components=component_health,
            uptime_ms=elapsed_ms,
            trace_id=input_data.trace_id,
            metadata={"detailed": input_data.detailed},
        )

    def validate_input(self, input_data: HealthCheckInput) -> CapabilityValidationResult:
        """
        Validate health check input.

        Args:
            input_data: Input to validate.

        Returns:
            Validation result.
        """
        # Health check input is always valid
        return CapabilityValidationResult(is_valid=True)

    def get_health(self) -> Dict[str, Any]:
        """
        Get health status of health check capability.

        Returns:
            Health status information.
        """
        return {
            "capability": self._name,
            "status": "healthy",
            "registered_components": list(self._capabilities.keys()),
        }
