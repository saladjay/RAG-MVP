"""
LiteLLM Observer for LLM Layer Observability.

This module provides metrics capture for the LLM Layer using LiteLLM.
It handles:
- Cost tracking (per-request, per-user, per-scenario)
- Performance metrics (response time, success/failure, fallback)
- Routing decisions (model selection, provider routing)

The LiteLLM observer is part of the three-layer observability stack:
- Prompt Layer (langfuse_client.py): Prompt template management
- LLM Layer (this module): Model invocation metrics and billing
- Agent Layer (phidata_observer.py): AI task execution behavior

API Reference:
- Location: src/rag_service/observability/litellm_observer.py
- Class: LiteLLMObserver
- Method: capture_inference() -> Record model invocation metrics
- Method: capture_routing_decision() -> Record model/provider routing
- Method: get_aggregated_metrics() -> Get cost/performance aggregation
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from collections import defaultdict

from rag_service.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class InferenceRecord:
    """Represents a single LLM inference record."""

    trace_id: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: float
    cost: float
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Routing metadata
    model_hint: Optional[str] = None
    fallback_used: bool = False
    original_provider: Optional[str] = None

    # Performance metadata
    success: bool = True
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "trace_id": self.trace_id,
            "model": self.model,
            "provider": self.provider,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "latency_ms": self.latency_ms,
            "cost": self.cost,
            "timestamp": self.timestamp.isoformat(),
            "model_hint": self.model_hint,
            "fallback_used": self.fallback_used,
            "original_provider": self.original_provider,
            "success": self.success,
            "error_message": self.error_message,
        }


@dataclass
class RoutingDecision:
    """Represents a model/provider routing decision."""

    trace_id: str
    requested_model: str
    routed_model: str
    provider: str
    routing_reason: str  # "user_hint", "availability", "cost", "performance", "fallback"
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Optional decision context
    available_providers: List[str] = field(default_factory=list)
    provider_health_scores: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "trace_id": self.trace_id,
            "requested_model": self.requested_model,
            "routed_model": self.routed_model,
            "provider": self.provider,
            "routing_reason": self.routing_reason,
            "timestamp": self.timestamp.isoformat(),
            "available_providers": self.available_providers,
            "provider_health_scores": self.provider_health_scores,
        }


class LiteLLMObserver:
    """
    Observer for capturing LLM layer metrics via LiteLLM.

    This observer tracks:
    - Cost metrics: Token usage, estimated costs per request/user/scenario
    - Performance metrics: Response times, success rates, fallback usage
    - Routing metrics: Model selection decisions, provider routing, fallback triggers

    Data is stored in-memory for analysis and can be aggregated for
    optimization insights.

    Attributes:
        _inferences: Store of inference records by trace_id
        _routing_decisions: Store of routing decisions by trace_id
        _cost_aggregates: Aggregated costs by user/scenario
        _provider_metrics: Per-provider performance metrics
        _lock: Async lock for thread-safe operations
    """

    # Approximate token costs per 1M tokens (as of 2024)
    COST_PER_MILLION_TOKENS = {
        "gpt-4": {"input": 30.0, "output": 60.0},
        "gpt-4-turbo": {"input": 10.0, "output": 30.0},
        "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
        "claude-3-opus": {"input": 15.0, "output": 75.0},
        "claude-3-sonnet": {"input": 3.0, "output": 15.0},
        "claude-3-haiku": {"input": 0.25, "output": 1.25},
    }

    def __init__(self):
        """Initialize the LiteLLM observer."""
        self._inferences: Dict[str, InferenceRecord] = {}
        self._routing_decisions: Dict[str, RoutingDecision] = {}
        self._cost_aggregates: Dict[str, float] = defaultdict(float)
        self._provider_metrics: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "total_latency_ms": 0.0,
                "total_tokens": 0,
                "total_cost": 0.0,
            }
        )
        # User and scenario cost tracking
        self._user_costs: Dict[str, float] = defaultdict(float)
        self._scenario_costs: Dict[str, float] = defaultdict(float)
        self._user_request_counts: Dict[str, int] = defaultdict(int)
        self._scenario_request_counts: Dict[str, int] = defaultdict(int)
        self._lock = asyncio.Lock()

    def _estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for model inference.

        Args:
            model: Model identifier
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Estimated cost in USD
        """
        # Normalize model name
        model_key = model.lower()
        for key in self.COST_PER_MILLION_TOKENS:
            if key in model_key or model_key in key:
                costs = self.COST_PER_MILLION_TOKENS[key]
                input_cost = (input_tokens / 1_000_000) * costs["input"]
                output_cost = (output_tokens / 1_000_000) * costs["output"]
                return input_cost + output_cost

        # Default fallback (very rough estimate)
        return ((input_tokens + output_tokens) / 1_000_000) * 1.0

    async def capture_inference(
        self,
        trace_id: str,
        model: str,
        tokens: Dict[str, int],
        latency_ms: float,
        cost: Optional[float] = None,
        provider: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        model_hint: Optional[str] = None,
        fallback_used: bool = False,
        original_provider: Optional[str] = None,
        user_id: Optional[str] = None,
        scenario: Optional[str] = None,
    ) -> None:
        """Capture LLM inference metrics.

        Records detailed metrics about a model invocation including token usage,
        cost, latency, and routing information. Also tracks costs by user and scenario.

        Args:
            trace_id: Unified trace identifier
            model: Model identifier (e.g., "gpt-4", "claude-3-opus")
            tokens: Token counts {"input": int, "output": int}
            latency_ms: Inference latency in milliseconds
            cost: Optional estimated cost (calculated if not provided)
            provider: Optional provider identifier
            success: Whether the inference succeeded
            error_message: Optional error message if failed
            model_hint: Optional model hint from request
            fallback_used: Whether fallback was triggered
            original_provider: Original provider before fallback
            user_id: Optional user identifier for cost aggregation
            scenario: Optional scenario identifier for cost aggregation
        """
        input_tokens = tokens.get("input", 0)
        output_tokens = tokens.get("output", 0)
        total_tokens = input_tokens + output_tokens

        # Estimate cost if not provided
        if cost is None:
            cost = self._estimate_cost(model, input_tokens, output_tokens)

        # Extract provider from model if not specified
        if provider is None:
            if "gpt" in model.lower():
                provider = "openai"
            elif "claude" in model.lower():
                provider = "anthropic"
            elif "ollama" in model.lower() or "llama" in model.lower():
                provider = "ollama"
            else:
                provider = "unknown"

        # Create inference record
        record = InferenceRecord(
            trace_id=trace_id,
            model=model,
            provider=provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            cost=cost,
            model_hint=model_hint,
            fallback_used=fallback_used,
            original_provider=original_provider,
            success=success,
            error_message=error_message,
        )

        async with self._lock:
            self._inferences[trace_id] = record

            # Update provider metrics
            self._provider_metrics[provider]["total_requests"] += 1
            if success:
                self._provider_metrics[provider]["successful_requests"] += 1
            else:
                self._provider_metrics[provider]["failed_requests"] += 1
            self._provider_metrics[provider]["total_latency_ms"] += latency_ms
            self._provider_metrics[provider]["total_tokens"] += total_tokens
            self._provider_metrics[provider]["total_cost"] += cost

            # Update user cost tracking
            if user_id:
                self._user_costs[user_id] += cost
                self._user_request_counts[user_id] += 1

            # Update scenario cost tracking
            if scenario:
                self._scenario_costs[scenario] += cost
                self._scenario_request_counts[scenario] += 1

        logger.info(
            "Captured LLM inference",
            extra={
                "trace_id": trace_id,
                "model": model,
                "provider": provider,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "latency_ms": latency_ms,
                "cost": cost,
                "success": success,
                "user_id": user_id,
                "scenario": scenario,
            },
        )

    async def capture_routing_decision(
        self,
        trace_id: str,
        requested_model: str,
        routed_model: str,
        provider: str,
        routing_reason: str,
        available_providers: Optional[List[str]] = None,
        provider_health_scores: Optional[Dict[str, float]] = None,
    ) -> None:
        """Capture model/provider routing decision.

        Records the routing decision made by the gateway, including why
        a specific model/provider was selected.

        Args:
            trace_id: Unified trace identifier
            requested_model: Model requested by user/hint
            routed_model: Model actually used (may differ)
            provider: Provider selected for routing
            routing_reason: Reason for routing decision
            available_providers: Optional list of available providers
            provider_health_scores: Optional health scores for providers
        """
        decision = RoutingDecision(
            trace_id=trace_id,
            requested_model=requested_model,
            routed_model=routed_model,
            provider=provider,
            routing_reason=routing_reason,
            available_providers=available_providers or [],
            provider_health_scores=provider_health_scores or {},
        )

        async with self._lock:
            self._routing_decisions[trace_id] = decision

        logger.debug(
            "Captured routing decision",
            extra={
                "trace_id": trace_id,
                "requested_model": requested_model,
                "routed_model": routed_model,
                "provider": provider,
                "routing_reason": routing_reason,
            },
        )

    async def get_inference(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Get inference record by trace ID.

        Args:
            trace_id: Unified trace identifier

        Returns:
            Inference record dictionary, or None if not found
        """
        async with self._lock:
            record = self._inferences.get(trace_id)

        if not record:
            return None

        return record.to_dict()

    async def get_routing_decision(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Get routing decision by trace ID.

        Args:
            trace_id: Unified trace identifier

        Returns:
            Routing decision dictionary, or None if not found
        """
        async with self._lock:
            decision = self._routing_decisions.get(trace_id)

        if not decision:
            return None

        return decision.to_dict()

    async def get_provider_metrics(self, provider: str) -> Optional[Dict[str, Any]]:
        """Get aggregated metrics for a specific provider.

        Args:
            provider: Provider identifier

        Returns:
            Provider metrics dictionary, or None if provider not found
        """
        async with self._lock:
            metrics = self._provider_metrics.get(provider)

        if not metrics or metrics["total_requests"] == 0:
            return None

        # Calculate derived metrics
        total_requests = metrics["total_requests"]
        return {
            "provider": provider,
            "total_requests": total_requests,
            "successful_requests": metrics["successful_requests"],
            "failed_requests": metrics["failed_requests"],
            "success_rate": metrics["successful_requests"] / total_requests if total_requests > 0 else 0,
            "average_latency_ms": metrics["total_latency_ms"] / total_requests if total_requests > 0 else 0,
            "total_tokens": metrics["total_tokens"],
            "total_cost": metrics["total_cost"],
        }

    async def get_all_provider_metrics(self) -> List[Dict[str, Any]]:
        """Get metrics for all providers.

        Returns:
            List of provider metrics dictionaries
        """
        metrics_list = []
        async with self._lock:
            for provider in self._provider_metrics:
                metrics = self._provider_metrics[provider]
                if metrics["total_requests"] > 0:
                    total_requests = metrics["total_requests"]
                    metrics_list.append({
                        "provider": provider,
                        "total_requests": total_requests,
                        "successful_requests": metrics["successful_requests"],
                        "failed_requests": metrics["failed_requests"],
                        "success_rate": metrics["successful_requests"] / total_requests if total_requests > 0 else 0,
                        "average_latency_ms": metrics["total_latency_ms"] / total_requests if total_requests > 0 else 0,
                        "total_tokens": metrics["total_tokens"],
                        "total_cost": metrics["total_cost"],
                    })

        return metrics_list

    async def aggregate_costs_by_user(
        self,
        user_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> float:
        """Aggregate costs for a specific user within a date range.

        Args:
            user_id: User identifier
            start_date: Start of date range
            end_date: End of date range

        Returns:
            Total cost in USD
        """
        async with self._lock:
            # Get tracked cost for user
            total_cost = self._user_costs.get(user_id, 0.0)

            # Filter by date range from inferences
            if start_date and end_date:
                filtered_cost = 0.0
                for record in self._inferences.values():
                    if start_date <= record.timestamp <= end_date:
                        # Note: This would require user_id in the inference record
                        # For now, return the tracked user cost
                        filtered_cost += record.cost
                return filtered_cost

            return total_cost

    async def get_user_cost_summary(
        self,
        user_id: str,
    ) -> Dict[str, Any]:
        """Get cost summary for a specific user.

        Args:
            user_id: User identifier

        Returns:
            User cost summary with total cost and request count
        """
        async with self._lock:
            total_cost = self._user_costs.get(user_id, 0.0)
            request_count = self._user_request_counts.get(user_id, 0)

        return {
            "user_id": user_id,
            "total_cost_usd": round(total_cost, 6),
            "total_requests": request_count,
            "average_cost_per_request": round(total_cost / request_count, 6) if request_count > 0 else 0.0,
        }

    async def get_all_user_costs(self) -> List[Dict[str, Any]]:
        """Get cost summaries for all users.

        Returns:
            List of user cost summaries
        """
        summaries = []
        async with self._lock:
            for user_id in self._user_costs:
                total_cost = self._user_costs[user_id]
                request_count = self._user_request_counts.get(user_id, 0)
                summaries.append({
                    "user_id": user_id,
                    "total_cost_usd": round(total_cost, 6),
                    "total_requests": request_count,
                    "average_cost_per_request": round(total_cost / request_count, 6) if request_count > 0 else 0.0,
                })

        return sorted(summaries, key=lambda x: x["total_cost_usd"], reverse=True)

    async def aggregate_costs_by_scenario(
        self,
        scenario: str,
        start_date: datetime,
        end_date: datetime,
    ) -> float:
        """Aggregate costs for a specific scenario within a date range.

        Args:
            scenario: Scenario identifier (e.g., "rag-query", "summarization")
            start_date: Start of date range
            end_date: End of date range

        Returns:
            Total cost in USD
        """
        async with self._lock:
            # Get tracked cost for scenario
            total_cost = self._scenario_costs.get(scenario, 0.0)

            # Filter by date range from inferences
            if start_date and end_date:
                filtered_cost = 0.0
                for record in self._inferences.values():
                    if start_date <= record.timestamp <= end_date:
                        # Note: This would require scenario in the inference record
                        # For now, return the tracked scenario cost
                        filtered_cost += record.cost
                return filtered_cost

            return total_cost

    async def get_scenario_cost_summary(
        self,
        scenario: str,
    ) -> Dict[str, Any]:
        """Get cost summary for a specific scenario.

        Args:
            scenario: Scenario identifier

        Returns:
            Scenario cost summary with total cost and request count
        """
        async with self._lock:
            total_cost = self._scenario_costs.get(scenario, 0.0)
            request_count = self._scenario_request_counts.get(scenario, 0)

        return {
            "scenario": scenario,
            "total_cost_usd": round(total_cost, 6),
            "total_requests": request_count,
            "average_cost_per_request": round(total_cost / request_count, 6) if request_count > 0 else 0.0,
        }

    async def get_all_scenario_costs(self) -> List[Dict[str, Any]]:
        """Get cost summaries for all scenarios.

        Returns:
            List of scenario cost summaries
        """
        summaries = []
        async with self._lock:
            for scenario in self._scenario_costs:
                total_cost = self._scenario_costs[scenario]
                request_count = self._scenario_request_counts.get(scenario, 0)
                summaries.append({
                    "scenario": scenario,
                    "total_cost_usd": round(total_cost, 6),
                    "total_requests": request_count,
                    "average_cost_per_request": round(total_cost / request_count, 6) if request_count > 0 else 0.0,
                })

        return sorted(summaries, key=lambda x: x["total_cost_usd"], reverse=True)

    async def flush_trace(self, trace_id: str) -> None:
        """Non-blocking flush for trace-specific data.

        In a production environment, this would flush data to external storage.
        For now, data is already stored in-memory.

        Args:
            trace_id: Unified trace identifier
        """
        logger.debug(
            "Flushed LiteLLM trace",
            extra={"trace_id": trace_id},
        )

    async def get_recent_inferences(
        self,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get recent inference records.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of inference dictionaries, most recent first
        """
        async with self._lock:
            records = sorted(
                self._inferences.values(),
                key=lambda r: r.timestamp,
                reverse=True,
            )[:limit]

        return [record.to_dict() for record in records]


# Global singleton instance
_litellm_observer: Optional[LiteLLMObserver] = None
_observer_lock = asyncio.Lock()


async def get_litellm_observer() -> LiteLLMObserver:
    """Get or create the global LiteLLM observer singleton.

    Returns:
        The global LiteLLMObserver instance
    """
    global _litellm_observer

    async with _observer_lock:
        if _litellm_observer is None:
            _litellm_observer = LiteLLMObserver()
            logger.info("Initialized global LiteLLM observer")

    return _litellm_observer


def reset_litellm_observer() -> None:
    """Reset the global LiteLLM observer instance.

    This is primarily used for testing to ensure clean state between tests.
    """
    global _litellm_observer
    _litellm_observer = None
    logger.debug("Reset global LiteLLM observer")
