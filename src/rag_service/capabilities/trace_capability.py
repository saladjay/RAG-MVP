"""
Unified Trace Capability for RAG Service.

Consolidates trace observation and health check:
- TraceObservation → trace access and metrics
- HealthCheck → system health status

API Reference:
- Location: src/rag_service/capabilities/trace_capability.py
"""

from typing import Any, Dict, Optional

from rag_service.capabilities.base import (
    Capability,
    CapabilityInput,
    CapabilityOutput,
    CapabilityValidationResult,
)
from rag_service.core.logger import get_logger

logger = get_logger(__name__)


class TraceCapability(Capability[CapabilityInput, CapabilityOutput]):
    """Unified trace capability for health checks and trace access.

    Consolidates TraceObservation and HealthCheck into a single capability.
    """

    async def execute(self, input_data: CapabilityInput) -> CapabilityOutput:
        """Execute trace observation.

        Args:
            input_data: Trace request with trace_id.

        Returns:
            CapabilityOutput with trace data.
        """
        try:
            from rag_service.capabilities.trace_observation import TraceObservationCapability
            capability = TraceObservationCapability()
            return await capability.execute(input_data)
        except Exception as e:
            logger.error(f"Trace observation failed: {e}")
            raise

    async def get_trace(self, trace_id: str) -> Dict[str, Any]:
        """Get trace details by ID.

        Args:
            trace_id: The trace identifier.

        Returns:
            Trace data dictionary.
        """
        try:
            from rag_service.capabilities.trace_observation import TraceObservationCapability
            capability = TraceObservationCapability()
            return await capability.get_trace(trace_id)
        except Exception as e:
            logger.error(f"Get trace failed: {e}")
            return {"trace_id": trace_id, "error": str(e)}

    async def health_check(self) -> Dict[str, Any]:
        """Get comprehensive health status.

        Returns:
            Health status dictionary with component states.
        """
        health: Dict[str, Any] = {
            "status": "healthy",
            "components": {},
        }

        # Check Milvus
        try:
            from rag_service.capabilities.health_check import HealthCheckCapability
            hc = HealthCheckCapability()
            hc_health = await hc.get_health()
            health["components"]["milvus"] = hc_health.get("status", "unknown")
            if hc_health.get("status") != "healthy":
                health["status"] = "degraded"
        except Exception as e:
            health["components"]["milvus"] = f"error: {e}"
            health["status"] = "degraded"

        # Check LiteLLM
        try:
            from rag_service.inference.gateway import get_gateway
            gateway = await get_gateway()
            health["components"]["litellm"] = f"configured (provider: {gateway.provider})"
        except Exception as e:
            health["components"]["litellm"] = f"error: {e}"
            health["status"] = "degraded"

        # Check external KB (if configured)
        try:
            from rag_service.clients.external_kb_client import get_external_kb_client
            client = await get_external_kb_client()
            kb_healthy = await client.health_check()
            health["components"]["external_kb"] = "connected" if kb_healthy else "disconnected"
        except Exception:
            health["components"]["external_kb"] = "not_configured"

        return health

    def validate_input(self, input_data: CapabilityInput) -> CapabilityValidationResult:
        """Validate trace request."""
        return CapabilityValidationResult(is_valid=True, errors=[], warnings=[])

    async def get_health(self) -> Dict[str, Any]:
        """Get health status of trace components."""
        return await self.health_check()
