"""
Trace Analysis Service for prompt performance insights.

This service handles:
- Storing and retrieving trace records
- Calculating aggregate metrics
- Detecting error patterns
- Generating performance insights

The service uses in-memory storage for recent traces and provides
interfaces for querying and analyzing prompt execution data.
"""

import heapq
import uuid
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from prompt_service.config import get_config
from prompt_service.core.logger import get_logger
from prompt_service.models.trace import (
    EvaluationMetrics,
    TraceFilter,
    TraceInsight,
    TraceRecord,
)

logger = get_logger(__name__)


class TraceAnalysisService:
    """Service for analyzing prompt execution traces.

    This service manages trace data storage and provides methods for
    calculating metrics, detecting patterns, and generating insights.

    Attributes:
        _traces: In-memory trace storage
        _config: Service configuration
    """

    def __init__(self, max_traces: int = 10000):
        """Initialize the trace analysis service.

        Args:
            max_traces: Maximum number of traces to keep in memory
        """
        self._config = get_config()
        self._max_traces = max_traces
        self._traces: List[TraceRecord] = []

        logger.info(
            "TraceAnalysisService initialized",
            extra={"max_traces": max_traces}
        )

    def record_trace(
        self,
        trace_id: str,
        template_id: str,
        template_version: int,
        rendered_prompt: str,
        input_variables: Dict[str, Any],
        context: Dict[str, Any],
        latency_ms: float = 0.0,
        total_latency_ms: Optional[float] = None,
        variant_id: Optional[str] = None,
        success: bool = True,
        retrieved_docs: Optional[List[Dict[str, Any]]] = None,
        model_output: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> TraceRecord:
        """Record a new trace.

        Args:
            trace_id: Unique trace identifier
            template_id: Template used
            template_version: Version used
            rendered_prompt: Final rendered prompt
            input_variables: Variables provided
            context: Runtime context
            latency_ms: Prompt latency
            total_latency_ms: End-to-end latency
            variant_id: Variant ID if A/B test
            success: Whether successful
            retrieved_docs: Retrieved documents
            model_output: LLM output
            timestamp: Trace timestamp (defaults to now)

        Returns:
            Created trace record
        """
        trace = TraceRecord(
            trace_id=trace_id,
            template_id=template_id,
            template_version=template_version,
            variant_id=variant_id,
            input_variables=input_variables,
            context=context,
            retrieved_docs=retrieved_docs or [],
            rendered_prompt=rendered_prompt,
            latency_ms=latency_ms,
            total_latency_ms=total_latency_ms or latency_ms,
            model_output=model_output,
            success=success,
            timestamp=timestamp or datetime.utcnow(),
        )

        self._traces.append(trace)

        # Keep only the most recent traces
        if len(self._traces) > self._max_traces:
            self._traces = self._traces[-self._max_traces:]

        logger.debug(
            "Trace recorded",
            extra={
                "trace_id": trace_id,
                "template_id": template_id,
                "success": success,
            }
        )

        return trace

    def update_trace(
        self,
        trace_id: str,
        model_output: Optional[str] = None,
        total_latency_ms: Optional[float] = None,
        success: Optional[bool] = None,
        user_feedback: Optional[str] = None,
        user_rating: Optional[int] = None,
    ) -> Optional[TraceRecord]:
        """Update an existing trace with outcome data.

        Args:
            trace_id: Trace identifier
            model_output: LLM output
            total_latency_ms: Total end-to-end latency
            success: Success status
            user_feedback: User feedback
            user_rating: User rating

        Returns:
            Updated trace or None if not found
        """
        for trace in self._traces:
            if trace.trace_id == trace_id:
                if model_output is not None:
                    trace.model_output = model_output
                if total_latency_ms is not None:
                    trace.total_latency_ms = total_latency_ms
                if success is not None:
                    trace.success = success
                if user_feedback is not None:
                    trace.user_feedback = user_feedback
                if user_rating is not None:
                    trace.user_rating = user_rating

                logger.debug(
                    "Trace updated",
                    extra={"trace_id": trace_id}
                )
                return trace

        logger.warning(
            "Trace not found for update",
            extra={"trace_id": trace_id}
        )
        return None

    def search_traces(self, filter_params: TraceFilter) -> List[TraceRecord]:
        """Search traces with filters.

        Args:
            filter_params: Filter criteria

        Returns:
            Matching traces
        """
        results = self._traces

        # Apply filters
        if filter_params.template_id:
            results = [
                t for t in results
                if t.template_id == filter_params.template_id
            ]

        if filter_params.variant_id:
            results = [
                t for t in results
                if t.variant_id == filter_params.variant_id
            ]

        if filter_params.start_date:
            results = [
                t for t in results
                if t.timestamp >= filter_params.start_date
            ]

        if filter_params.end_date:
            results = [
                t for t in results
                if t.timestamp <= filter_params.end_date
            ]

        if filter_params.success_only:
            results = [t for t in results if t.success]

        if filter_params.errors_only:
            results = [t for t in results if not t.success]

        if filter_params.min_latency is not None:
            results = [
                t for t in results
                if t.total_latency_ms >= filter_params.min_latency
            ]

        if filter_params.max_latency is not None:
            results = [
                t for t in results
                if t.total_latency_ms <= filter_params.max_latency
            ]

        # Sort by timestamp descending
        results = sorted(results, key=lambda t: t.timestamp, reverse=True)

        # Apply pagination
        start = filter_params.offset
        end = start + filter_params.limit
        return results[start:end]

    def aggregate_metrics(
        self,
        template_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> EvaluationMetrics:
        """Calculate aggregate metrics for a template.

        Args:
            template_id: Template identifier
            start_date: Start of date range
            end_date: End of date range

        Returns:
            Aggregated metrics
        """
        # Filter traces for template
        traces = [
            t for t in self._traces
            if t.template_id == template_id
        ]

        if start_date:
            traces = [t for t in traces if t.timestamp >= start_date]
        if end_date:
            traces = [t for t in traces if t.timestamp <= end_date]

        if not traces:
            return EvaluationMetrics(
                total_count=0,
                success_count=0,
                error_count=0,
                success_rate=1.0,
                avg_latency_ms=0.0,
            )

        # Calculate basic metrics
        total_count = len(traces)
        success_count = sum(1 for t in traces if t.success)
        error_count = total_count - success_count
        success_rate = success_count / total_count if total_count > 0 else 1.0

        # Use total_latency if available, otherwise latency_ms
        latencies = [
            t.total_latency_ms or t.latency_ms
            for t in traces
        ]

        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        min_latency = min(latencies) if latencies else 0.0
        max_latency = max(latencies) if latencies else 0.0

        # Calculate percentiles
        p50 = self._calculate_percentile(latencies, 50)
        p95 = self._calculate_percentile(latencies, 95)
        p99 = self._calculate_percentile(latencies, 99)

        # Calculate metrics per variant
        variant_metrics = {}
        for trace in traces:
            if trace.variant_id:
                if trace.variant_id not in variant_metrics:
                    variant_metrics[trace.variant_id] = {
                        "count": 0,
                        "successes": 0,
                        "latencies": [],
                    }
                variant_metrics[trace.variant_id]["count"] += 1
                if trace.success:
                    variant_metrics[trace.variant_id]["successes"] += 1
                variant_metrics[trace.variant_id]["latencies"].append(
                    trace.total_latency_ms or trace.latency_ms
                )

        # Calculate summary for each variant
        for variant_id, data in variant_metrics.items():
            data["success_rate"] = data["successes"] / data["count"]
            data["avg_latency"] = sum(data["latencies"]) / len(data["latencies"])
            del data["latencies"]

        # Detect error patterns
        error_patterns = self._detect_error_patterns(
            [t for t in traces if not t.success]
        )

        return EvaluationMetrics(
            total_count=total_count,
            success_count=success_count,
            error_count=error_count,
            success_rate=success_rate,
            avg_latency_ms=avg_latency,
            p50_latency_ms=p50,
            p95_latency_ms=p95,
            p99_latency_ms=p99,
            min_latency_ms=min_latency,
            max_latency_ms=max_latency,
            variant_metrics=variant_metrics if variant_metrics else None,
            error_patterns=error_patterns,
        )

    def get_insights(
        self,
        template_id: str,
        limit: int = 10,
    ) -> List[TraceInsight]:
        """Generate insights for a template.

        Args:
            template_id: Template identifier
            limit: Maximum insights to return

        Returns:
            List of insights
        """
        traces = [t for t in self._traces if t.template_id == template_id]

        if not traces:
            return []

        insights = []

        # Check for high error rate
        total_count = len(traces)
        error_count = sum(1 for t in traces if not t.success)
        error_rate = error_count / total_count if total_count > 0 else 0

        if error_rate > 0.1:  # More than 10% errors
            insights.append(TraceInsight(
                insight_type="error",
                title="High error rate detected",
                description=f"Error rate is {error_rate:.1%}, which is above 10% threshold",
                severity="critical" if error_rate > 0.2 else "warning",
                data={
                    "error_rate": error_rate,
                    "error_count": error_count,
                    "total_count": total_count,
                },
            ))

        # Check for slow performance
        latencies = [
            t.total_latency_ms or t.latency_ms
            for t in traces
            if t.total_latency_ms or t.latency_ms
        ]

        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            p95_latency = self._calculate_percentile(latencies, 95)

            if p95_latency > 5000:  # More than 5 seconds
                insights.append(TraceInsight(
                    insight_type="performance",
                    title="Slow performance detected",
                    description=f"P95 latency is {p95_latency:.0f}ms, consider optimization",
                    severity="warning" if p95_latency < 10000 else "critical",
                    data={
                        "avg_latency_ms": avg_latency,
                        "p95_latency_ms": p95_latency,
                        "threshold_ms": 5000,
                    },
                ))

        # Check for A/B test performance differences
        variant_metrics = defaultdict(lambda: {"successes": 0, "count": 0, "latencies": []})
        for trace in traces:
            if trace.variant_id:
                variant_metrics[trace.variant_id]["count"] += 1
                if trace.success:
                    variant_metrics[trace.variant_id]["successes"] += 1
                latency = trace.total_latency_ms or trace.latency_ms
                variant_metrics[trace.variant_id]["latencies"].append(latency)

        if len(variant_metrics) > 1:
            variant_rates = {
                vid: data["successes"] / data["count"]
                for vid, data in variant_metrics.items()
            }
            best_variant = max(variant_rates, key=variant_rates.get)
            worst_variant = min(variant_rates, key=variant_rates.get)
            improvement = variant_rates[best_variant] - variant_rates[worst_variant]

            if improvement > 0.05:  # More than 5% improvement
                insights.append(TraceInsight(
                    insight_type="ab_test",
                    title="Significant A/B test difference",
                    description=f"{best_variant} outperforms {worst_variant} by {improvement:.1%}",
                    severity="info",
                    data={
                        "best_variant": best_variant,
                        "worst_variant": worst_variant,
                        "improvement": improvement,
                        "variant_rates": variant_rates,
                    },
                ))

        # Sort by severity and limit
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        insights.sort(key=lambda i: severity_order.get(i.severity, 3))

        return insights[:limit]

    def _calculate_percentile(self, values: List[float], percentile: int) -> float:
        """Calculate a percentile value.

        Args:
            values: List of values
            percentile: Percentile to calculate (0-100)

        Returns:
            Percentile value
        """
        if not values:
            return 0.0

        # Use heapq.nsmallest for efficiency with large lists
        k = max(1, int(len(values) * percentile / 100))
        sorted_values = heapq.nsmallest(k, values)

        if len(sorted_values) == 0:
            return 0.0

        return sorted_values[-1]

    def _detect_error_patterns(self, error_traces: List[TraceRecord]) -> List[Dict[str, Any]]:
        """Detect common error patterns.

        Args:
            error_traces: List of failed traces

        Returns:
            List of error patterns
        """
        patterns = []

        if not error_traces:
            return patterns

        # Check for common error context values
        error_contexts = []
        for trace in error_traces:
            if trace.context:
                error_contexts.append(trace.context)

        # Look for common patterns in errors
        # For now, just return count by template version
        version_errors = Counter()
        for trace in error_traces:
            key = f"{trace.template_id}_v{trace.template_version}"
            version_errors[key] += 1

        for version, count in version_errors.most_common(5):
            patterns.append({
                "type": "version_errors",
                "version": version,
                "error_count": count,
                "percentage": count / len(error_traces),
            })

        return patterns


# Global service instance
_service: Optional[TraceAnalysisService] = None


def get_trace_analysis_service() -> TraceAnalysisService:
    """Get the global trace analysis service instance.

    Returns:
        Trace analysis service instance
    """
    global _service
    if _service is None:
        _service = TraceAnalysisService()
    return _service


def reset_trace_analysis_service() -> None:
    """Reset the global service instance.

    This is primarily useful for testing.
    """
    global _service
    _service = None
