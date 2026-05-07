"""
Security utilities for RAG QA Pipeline.

This module provides input sanitization, rate limiting preparation,
and audit logging for production security requirements.
"""

import re
import html
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from rag_service.core.logger import get_logger


# Security logger for audit events
audit_logger = get_logger("security")


class InputSanitizer:
    """
    Utility class for sanitizing user inputs.

    Provides methods to clean and validate user-provided text
    to prevent injection attacks and other security issues.
    """

    # Patterns that might indicate injection attempts
    SUSPICIOUS_PATTERNS = [
        r'<script[^>]*>.*?</script>',  # Script tags
        r'javascript:',  # JavaScript protocol
        r'on\w+\s*=',  # Event handlers (onclick, onload, etc.)
        r'<iframe[^>]*>',  # iframe tags
        r'<object[^>]*>',  # object tags
        r'<embed[^>]*>',  # embed tags
    ]

    @classmethod
    def sanitize_query(cls, query: str) -> str:
        """
        Sanitize a user query string.

        Removes or escapes potentially dangerous content while
        preserving the original meaning where possible.

        Args:
            query: Raw user query

        Returns:
            Sanitized query string
        """
        if not query:
            return ""

        # Remove null bytes
        query = query.replace('\x00', '')

        # Normalize Unicode
        query = query.encode('utf-8', 'ignore').decode('utf-8')

        # Check for suspicious patterns
        for pattern in cls.SUSPICIOUS_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                audit_logger.warning(
                    "Suspicious pattern detected in query",
                    extra={
                        "pattern": pattern[:50],
                        "query_length": len(query),
                    }
                )
                # Remove the suspicious content
                query = re.sub(pattern, '', query, flags=re.IGNORECASE)

        # Strip excessive whitespace
        query = ' '.join(query.split())

        return query

    @classmethod
    def validate_company_id(cls, company_id: Optional[str]) -> bool:
        """
        Validate company_id format.

        Args:
            company_id: Company ID to validate

        Returns:
            True if valid, False otherwise
        """
        if not company_id:
            return False

        # Must start with N followed by digits
        if not company_id.startswith('N'):
            return False

        # Check remaining characters are digits
        if not company_id[1:].isdigit():
            return False

        # Check length (typically 7 characters: N + 6 digits)
        if not (3 <= len(company_id) <= 10):
            return False

        return True

    @classmethod
    def truncate_query(cls, query: str, max_length: int = 1000) -> str:
        """
        Truncate query to maximum length.

        Args:
            query: Query string
            max_length: Maximum allowed length

        Returns:
            Truncated query
        """
        if len(query) <= max_length:
            return query

        audit_logger.info(
            "Query truncated due to length limit",
            extra={
                "original_length": len(query),
                "truncated_to": max_length,
            }
        )

        return query[:max_length]


class AuditLogger:
    """
    Utility class for security audit logging.

    Logs security-relevant events for compliance and debugging.
    """

    @staticmethod
    def log_query_received(
        trace_id: str,
        query: str,
        company_id: Optional[str] = None,
        client_ip: Optional[str] = None,
    ) -> None:
        """Log query received event."""
        audit_logger.info(
            "QA query received",
            extra={
                "trace_id": trace_id,
                "query_length": len(query),
                "query_preview": query[:100],
                "company_id": company_id,
                "client_ip": client_ip,
                "event": "query_received",
            }
        )

    @staticmethod
    def log_query_completed(
        trace_id: str,
        retrieval_count: int,
        generation_time_ms: float,
        hallucination_checked: bool,
        client_ip: Optional[str] = None,
    ) -> None:
        """Log query completed event."""
        audit_logger.info(
            "QA query completed",
            extra={
                "trace_id": trace_id,
                "retrieval_count": retrieval_count,
                "generation_time_ms": generation_time_ms,
                "hallucination_checked": hallucination_checked,
                "client_ip": client_ip,
                "event": "query_completed",
            }
        )

    @staticmethod
    def log_query_failed(
        trace_id: str,
        error_type: str,
        error_message: str,
        client_ip: Optional[str] = None,
    ) -> None:
        """Log query failed event."""
        audit_logger.error(
            "QA query failed",
            extra={
                "trace_id": trace_id,
                "error_type": error_type,
                "error_message": error_message,
                "client_ip": client_ip,
                "event": "query_failed",
            }
        )

    @staticmethod
    def log_fallback_used(
        trace_id: str,
        fallback_type: str,
        reason: str,
        client_ip: Optional[str] = None,
    ) -> None:
        """Log fallback message used."""
        audit_logger.warning(
            "QA fallback used",
            extra={
                "trace_id": trace_id,
                "fallback_type": fallback_type,
                "reason": reason,
                "client_ip": client_ip,
                "event": "fallback_used",
            }
        )

    @staticmethod
    def log_hallucination_detected(
        trace_id: str,
        confidence: float,
        threshold: float,
        flagged_claims: List[str],
        client_ip: Optional[str] = None,
    ) -> None:
        """Log hallucination detection event."""
        audit_logger.warning(
            "Hallucination detected",
            extra={
                "trace_id": trace_id,
                "confidence": confidence,
                "threshold": threshold,
                "flagged_claims_count": len(flagged_claims),
                "client_ip": client_ip,
                "event": "hallucination_detected",
            }
        )

    @staticmethod
    def log_regeneration_attempt(
        trace_id: str,
        attempt_number: int,
        max_attempts: int,
        client_ip: Optional[str] = None,
    ) -> None:
        """Log answer regeneration attempt."""
        audit_logger.info(
            "Answer regeneration attempted",
            extra={
                "trace_id": trace_id,
                "attempt_number": attempt_number,
                "max_attempts": max_attempts,
                "client_ip": client_ip,
                "event": "regeneration_attempt",
            }
        )


class RateLimiter:
    """
    Simple in-memory rate limiter for QA API.

    NOTE: This is a basic implementation for development/testing.
    Production deployments should use Redis-based rate limiting.
    """

    def __init__(
        self,
        requests_per_minute: int = 60,
        burst_size: int = 10,
    ) -> None:
        """
        Initialize rate limiter.

        Args:
            requests_per_minute: Maximum requests per minute per client
            burst_size: Maximum burst of requests allowed
        """
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self._request_history: Dict[str, List[datetime]] = {}

    def is_allowed(
        self,
        client_id: str,
        current_time: Optional[datetime] = None,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if request is allowed for client.

        Args:
            client_id: Unique client identifier (IP address or API key)
            current_time: Current time for testing (defaults to now)

        Returns:
            Tuple of (allowed, error_message)
        """
        if current_time is None:
            current_time = datetime.utcnow()

        # Clean old history (older than 1 minute)
        self._clean_history(current_time)

        # Get client history
        history = self._request_history.get(client_id, [])

        # Check burst limit
        recent_count = sum(
            1 for t in history
            if (current_time - t).total_seconds() < 1
        )

        if recent_count >= self.burst_size:
            return False, f"Rate limit exceeded: max {self.burst_size} requests per second"

        # Check per-minute limit
        if len(history) >= self.requests_per_minute:
            return False, f"Rate limit exceeded: max {self.requests_per_minute} requests per minute"

        # Add current request to history
        history.append(current_time)
        self._request_history[client_id] = history

        return True, None

    def _clean_history(self, current_time: datetime) -> None:
        """Remove entries older than 1 minute."""
        cutoff_time = current_time.timestamp() - 60  # 1 minute ago

        for client_id in list(self._request_history.keys()):
            # Filter to recent entries
            self._request_history[client_id] = [
                t for t in self._request_history[client_id]
                if t.timestamp() > cutoff_time
            ]

            # Remove empty history
            if not self._request_history[client_id]:
                del self._request_history[client_id]

    def reset(self) -> None:
        """Reset all rate limits (primarily for testing)."""
        self._request_history.clear()


# Global rate limiter instance (can be configured via environment)
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create the global rate limiter instance."""
    global _rate_limiter

    if _rate_limiter is None:
        import os
        requests_per_minute = int(os.getenv("RATE_LIMIT_RPM", "60"))
        _rate_limiter = RateLimiter(requests_per_minute=requests_per_minute)

    return _rate_limiter


def reset_rate_limiter() -> None:
    """Reset the global rate limiter (for testing)."""
    global _rate_limiter
    _rate_limiter = None
