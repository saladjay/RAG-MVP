"""
Chain Logger for RAG Service

Logs the complete request chain from QA query to response.
Each stage is logged with timing and trace_id correlation.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from threading import local
from typing import Any, Dict, Optional
from contextlib import contextmanager


class ChainLogger:
    """
    Logger for complete request chain tracking.

    Logs are saved to logs/chain_trace.jsonl with full request lifecycle.
    """

    def __init__(self, log_dir: str = "logs"):
        """Initialize the chain logger.

        Args:
            log_dir: Directory to store log files.
        """
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = self._log_dir / "chain_trace.jsonl"
        self._enabled = os.getenv("CHAIN_LOG_ENABLED", "true").lower() == "true"

        # Thread-local storage for current request context
        self._local = local()

    def start_request(self, trace_id: str, request_data: Dict[str, Any]) -> None:
        """Start logging a new request.

        Args:
            trace_id: Unique trace identifier.
            request_data: Initial request data.
        """
        if not self._enabled:
            return

        self._current_trace = {
            "trace_id": trace_id,
            "start_time": datetime.now().isoformat(),
            "request": request_data,
            "stages": [],
        }

        self._local.trace = self._current_trace

    def log_stage(
        self,
        stage_name: str,
        stage_data: Dict[str, Any],
        timing_ms: float,
        error: Optional[str] = None,
    ) -> None:
        """Log a processing stage.

        Args:
            stage_name: Stage identifier (e.g., "query_rewrite", "retrieval").
            stage_data: Stage-specific data.
            timing_ms: Stage duration in milliseconds.
            error: Error message if stage failed.
        """
        if not self._enabled:
            return

        trace = getattr(self._local, "trace", None)
        if trace is None:
            return

        stage_entry = {
            "name": stage_name,
            "timestamp": datetime.now().isoformat(),
            "timing_ms": timing_ms,
            "data": stage_data,
            "error": error,
        }

        trace["stages"].append(stage_entry)

    def end_request(self, response_data: Dict[str, Any], total_time_ms: float) -> None:
        """Complete logging for a request.

        Args:
            response_data: Final response data.
            total_time_ms: Total request time in milliseconds.
        """
        if not self._enabled:
            return

        trace = getattr(self._local, "trace", None)
        if trace is None:
            return

        trace["end_time"] = datetime.now().isoformat()
        trace["response"] = response_data
        trace["total_time_ms"] = total_time_ms

        # Calculate stage timing breakdown
        total_stage_time = sum(s["timing_ms"] for s in trace["stages"])
        trace["overhead_ms"] = total_time_ms - total_stage_time

        # Write to log file
        try:
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(trace, ensure_ascii=False) + "\n")
        except Exception as e:
            # Don't fail the request if logging fails
            pass

        # Clear thread-local storage
        self._local.trace = None


# Global chain logger instance
_chain_logger: Optional[ChainLogger] = None


def get_chain_logger() -> ChainLogger:
    """Get the global chain logger instance.

    Returns:
        ChainLogger instance.
    """
    global _chain_logger
    if _chain_logger is None:
        _chain_logger = ChainLogger()
    return _chain_logger


@contextmanager
def trace_request(trace_id: str, request_data: Dict[str, Any]):
    """Context manager for tracing a complete request.

    Args:
        trace_id: Unique trace identifier.
        request_data: Initial request data.

    Yields:
        A function to log stages.
    """
    logger = get_chain_logger()
    logger.start_request(trace_id, request_data)

    def log_stage(stage_name: str, stage_data: Dict[str, Any], timing_ms: float, error: Optional[str] = None):
        logger.log_stage(stage_name, stage_data, timing_ms, error)

    try:
        yield log_stage
    finally:
        pass  # end_request will be called separately


def end_request(trace_id: str, response_data: Dict[str, Any], total_time_ms: float) -> None:
    """End request logging.

    Args:
        trace_id: Trace identifier.
        response_data: Final response data.
        total_time_ms: Total request time.
    """
    logger = get_chain_logger()
    logger.end_request(response_data, total_time_ms)
