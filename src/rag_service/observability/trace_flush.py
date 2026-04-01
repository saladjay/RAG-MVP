"""
Non-Blocking Trace Flush for RAG Service Observability.

This module provides background flushing of trace data to prevent observability
failures from blocking request responses. It implements:

- Background task queue for flush operations
- Error isolation to prevent flush failures from affecting requests
- Batched flushes for improved performance
- Retry logic for transient failures

The non-blocking flush ensures that even if Langfuse, LiteLLM, or Phidata
are slow or unavailable, the RAG service remains responsive.

API Reference:
- Location: src/rag_service/observability/trace_flush.py
- Class: TraceFlushManager
- Method: schedule_flush() -> Schedule a trace for background flushing
- Method: flush_now() -> Synchronous flush for critical traces
- Function: get_flush_manager() -> Get global flush manager singleton
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from collections import deque
import logging

from rag_service.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class FlushTask:
    """Represents a pending flush task."""

    trace_id: str
    priority: int = 0  # Higher priority = flush sooner
    created_at: datetime = field(default_factory=datetime.utcnow)
    retry_count: int = 0
    max_retries: int = 3

    # Flush data for each layer
    phidata_data: Optional[Dict[str, Any]] = None
    litellm_data: Optional[Dict[str, Any]] = None
    langfuse_data: Optional[Dict[str, Any]] = None

    def __lt__(self, other: "FlushTask") -> bool:
        """Compare for priority queue (higher priority first)."""
        return self.priority > other.priority


class TraceFlushManager:
    """
    Manager for non-blocking trace flush operations.

    This manager runs background tasks to flush trace data to observability
    layers without blocking request responses. Key features:

    - Background flush queue with priority support
    - Batched flushes for efficiency
    - Error isolation and retry logic
    - Graceful degradation when services are unavailable

    Attributes:
        _flush_queue: Queue of pending flush tasks
        _worker_task: Background worker task
        _flush_interval: Time between flush batches
        _batch_size: Max number of traces to flush per batch
        _enabled: Whether flush is enabled
        _lock: Async lock for thread-safe operations
    """

    def __init__(
        self,
        flush_interval_ms: int = 100,
        batch_size: int = 10,
        enabled: bool = True,
    ):
        """Initialize the trace flush manager.

        Args:
            flush_interval_ms: Milliseconds between flush batches
            batch_size: Maximum number of traces to flush per batch
            enabled: Whether flush operations are enabled
        """
        self._flush_queue: deque[FlushTask] = deque()
        self._worker_task: Optional[asyncio.Task] = None
        self._flush_interval = timedelta(milliseconds=flush_interval_ms)
        self._batch_size = batch_size
        self._enabled = enabled
        self._lock = asyncio.Lock()

        # Statistics
        self._stats = {
            "scheduled": 0,
            "flushed": 0,
            "failed": 0,
            "retried": 0,
        }

        # Shutdown flag
        self._shutdown = False

    async def start(self) -> None:
        """Start the background flush worker."""
        if self._worker_task is None and self._enabled:
            self._worker_task = asyncio.create_task(self._flush_worker())
            logger.info(
                "Started trace flush worker",
                extra={
                    "interval_ms": self._flush_interval.total_seconds() * 1000,
                    "batch_size": self._batch_size,
                },
            )

    async def stop(self) -> None:
        """Stop the background flush worker and flush remaining tasks."""
        self._shutdown = True

        if self._worker_task:
            # Wait for worker to finish processing
            try:
                await asyncio.wait_for(self._worker_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Flush worker did not shut down gracefully")

            self._worker_task = None

        # Flush any remaining tasks
        await self._flush_all()

        logger.info(
            "Stopped trace flush worker",
            extra={
                "scheduled": self._stats["scheduled"],
                "flushed": self._stats["flushed"],
                "failed": self._stats["failed"],
                "retried": self._stats["retried"],
            },
        )

    async def schedule_flush(
        self,
        trace_id: str,
        priority: int = 0,
        phidata_data: Optional[Dict[str, Any]] = None,
        litellm_data: Optional[Dict[str, Any]] = None,
        langfuse_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Schedule a trace for background flushing.

        This is the main entry point for non-blocking flush. The trace
        will be flushed in the background without blocking the request.

        Args:
            trace_id: Unified trace identifier
            priority: Flush priority (higher = sooner)
            phidata_data: Optional Phidata layer data to flush
            litellm_data: Optional LiteLLM layer data to flush
            langfuse_data: Optional Langfuse layer data to flush
        """
        if not self._enabled:
            return

        task = FlushTask(
            trace_id=trace_id,
            priority=priority,
            phidata_data=phidata_data,
            litellm_data=litellm_data,
            langfuse_data=langfuse_data,
        )

        async with self._lock:
            self._flush_queue.append(task)
            self._stats["scheduled"] += 1

        # Ensure worker is running
        if self._worker_task is None:
            await self.start()

        logger.debug(
            "Scheduled trace for background flush",
            extra={
                "trace_id": trace_id,
                "priority": priority,
                "queue_size": len(self._flush_queue),
            },
        )

    async def flush_now(
        self,
        trace_id: str,
        phidata_data: Optional[Dict[str, Any]] = None,
        litellm_data: Optional[Dict[str, Any]] = None,
        langfuse_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Synchronously flush a trace (for critical traces).

        This performs an immediate flush for critical traces, blocking
        until the flush completes. Use sparingly as it affects latency.

        Args:
            trace_id: Unified trace identifier
            phidata_data: Optional Phidata layer data to flush
            litellm_data: Optional LiteLLM layer data to flush
            langfuse_data: Optional Langfuse layer data to flush

        Returns:
            Dictionary with flush results for each layer
        """
        results = {
            "trace_id": trace_id,
            "layers_flushed": [],
            "layers_failed": [],
        }

        # Flush to Phidata
        if phidata_data:
            try:
                from rag_service.observability.phidata_observer import get_phidata_observer

                observer = await get_phidata_observer()
                await observer.flush_trace(trace_id)
                results["layers_flushed"].append("phidata")
            except Exception as e:
                logger.warning(
                    "Failed to flush Phidata trace",
                    extra={"trace_id": trace_id, "error": str(e)},
                )
                results["layers_failed"].append({"layer": "phidata", "error": str(e)})

        # Flush to LiteLLM
        if litellm_data:
            try:
                from rag_service.observability.litellm_observer import get_litellm_observer

                observer = await get_litellm_observer()
                await observer.flush_trace(trace_id)
                results["layers_flushed"].append("litellm")
            except Exception as e:
                logger.warning(
                    "Failed to flush LiteLLM trace",
                    extra={"trace_id": trace_id, "error": str(e)},
                )
                results["layers_failed"].append({"layer": "litellm", "error": str(e)})

        # Flush to Langfuse
        if langfuse_data:
            try:
                from rag_service.observability.langfuse_client import get_langfuse_client

                client = await get_langfuse_client()
                await client.flush_trace(trace_id)
                results["layers_flushed"].append("langfuse")
            except Exception as e:
                logger.warning(
                    "Failed to flush Langfuse trace",
                    extra={"trace_id": trace_id, "error": str(e)},
                )
                results["layers_failed"].append({"layer": "langfuse", "error": str(e)})

        self._stats["flushed"] += 1

        return results

    async def _flush_worker(self) -> None:
        """
        Background worker that processes the flush queue.

        Runs in a loop, processing batches of flush tasks at regular intervals.
        Implements retry logic for transient failures.
        """
        while not self._shutdown:
            try:
                # Process a batch of tasks
                batch = await self._get_next_batch()
                if batch:
                    await self._flush_batch(batch)

                # Sleep until next batch
                await asyncio.sleep(self._flush_interval.total_seconds())

            except asyncio.CancelledError:
                logger.info("Flush worker cancelled")
                break
            except Exception as e:
                logger.error(
                    "Error in flush worker",
                    extra={"error": str(e)},
                    exc_info=True,
                )
                # Continue processing despite errors

    async def _get_next_batch(self) -> List[FlushTask]:
        """Get the next batch of tasks to flush.

        Returns:
            List of flush tasks, sorted by priority
        """
        async with self._lock:
            if not self._flush_queue:
                return []

            # Sort by priority and get batch
            batch = list(sorted(self._flush_queue, key=lambda t: t.priority))[
                : self._batch_size
            ]

            # Remove batched tasks from queue
            for task in batch:
                try:
                    self._flush_queue.remove(task)
                except ValueError:
                    pass  # Task already removed

        return batch

    async def _flush_batch(self, batch: List[FlushTask]) -> None:
        """Flush a batch of tasks.

        Args:
            batch: List of flush tasks to process
        """
        for task in batch:
            try:
                await self._flush_single_task(task)

            except Exception as e:
                logger.warning(
                    "Failed to flush task",
                    extra={
                        "trace_id": task.trace_id,
                        "error": str(e),
                        "retry_count": task.retry_count,
                    },
                )

                # Retry if under limit
                if task.retry_count < task.max_retries:
                    task.retry_count += 1
                    async with self._lock:
                        self._flush_queue.append(task)
                    self._stats["retried"] += 1
                else:
                    self._stats["failed"] += 1

    async def _flush_single_task(self, task: FlushTask) -> None:
        """Flush a single task to all layers.

        Args:
            task: Flush task to process
        """
        # Flush to Phidata
        if task.phidata_data:
            try:
                from rag_service.observability.phidata_observer import get_phidata_observer

                observer = await get_phidata_observer()
                await observer.flush_trace(task.trace_id)
            except Exception as e:
                logger.debug(
                    "Phidata flush failed for task",
                    extra={"trace_id": task.trace_id, "error": str(e)},
                )

        # Flush to LiteLLM
        if task.litellm_data:
            try:
                from rag_service.observability.litellm_observer import get_litellm_observer

                observer = await get_litellm_observer()
                await observer.flush_trace(task.trace_id)
            except Exception as e:
                logger.debug(
                    "LiteLLM flush failed for task",
                    extra={"trace_id": task.trace_id, "error": str(e)},
                )

        # Flush to Langfuse
        if task.langfuse_data:
            try:
                from rag_service.observability.langfuse_client import get_langfuse_client

                client = await get_langfuse_client()
                await client.flush_trace(task.trace_id)
            except Exception as e:
                logger.debug(
                    "Langfuse flush failed for task",
                    extra={"trace_id": task.trace_id, "error": str(e)},
                )

        self._stats["flushed"] += 1

    async def _flush_all(self) -> None:
        """Flush all remaining tasks in the queue."""
        while self._flush_queue:
            batch = await self._get_next_batch()
            if not batch:
                break
            await self._flush_batch(batch)

    def get_stats(self) -> Dict[str, Any]:
        """Get flush manager statistics.

        Returns:
            Dictionary with current statistics
        """
        return {
            **self._stats,
            "queue_size": len(self._flush_queue),
            "is_running": self._worker_task is not None and not self._worker_task.done(),
        }

    def is_enabled(self) -> bool:
        """Check if flush is enabled.

        Returns:
            True if flush operations are enabled
        """
        return self._enabled


# Global singleton instance
_flush_manager: Optional[TraceFlushManager] = None
_manager_lock = asyncio.Lock()


async def get_flush_manager() -> TraceFlushManager:
    """Get or create the global flush manager singleton.

    Returns:
        The global TraceFlushManager instance
    """
    global _flush_manager

    async with _manager_lock:
        if _flush_manager is None:
            # Read configuration from environment
            import os

            flush_interval = int(os.getenv("TRACE_FLUSH_INTERVAL_MS", "100"))
            batch_size = int(os.getenv("TRACE_FLUSH_BATCH_SIZE", "10"))
            enabled = os.getenv("TRACE_FLUSH_ENABLED", "true").lower() == "true"

            _flush_manager = TraceFlushManager(
                flush_interval_ms=flush_interval,
                batch_size=batch_size,
                enabled=enabled,
            )
            await _flush_manager.start()
            logger.info("Initialized global trace flush manager")

    return _flush_manager


def reset_flush_manager() -> None:
    """Reset the global flush manager instance.

    This is primarily used for testing to ensure clean state between tests.
    """
    global _flush_manager
    _flush_manager = None
    logger.debug("Reset global trace flush manager")


async def schedule_trace_flush(
    trace_id: str,
    priority: int = 0,
) -> None:
    """
    Convenience function to schedule a trace for background flushing.

    This is the main entry point used by other components to schedule
    non-blocking flushes.

    Args:
        trace_id: Unified trace identifier
        priority: Flush priority (higher = sooner)
    """
    manager = await get_flush_manager()
    await manager.schedule_flush(trace_id=trace_id, priority=priority)
