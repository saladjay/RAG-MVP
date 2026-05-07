"""
Redis Session Store Service for Query Quality Enhancement.

This service manages session state for multi-turn conversations in the
Query Quality Enhancement module. It uses Redis for fast, scalable session
storage with automatic TTL-based expiration.

Key features:
- Session CRUD operations with automatic serialization
- TTL-based expiration to prevent stale sessions
- Graceful degradation when Redis is unavailable
- Full trace ID propagation for observability
"""

import json
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from rag_service.core.exceptions import RetrievalError
from rag_service.core.logger import get_logger
from rag_service.models.query_quality import SessionState

logger = get_logger(__name__)


class SessionStoreService:
    """Service for managing query quality session state in Redis.

    This service provides CRUD operations for session state, with automatic
    serialization/deserialization and TTL-based expiration.

    Attributes:
        _redis: Redis client instance
        _ttl_seconds: Default TTL for session keys
    """

    _instance: Optional["SessionStoreService"] = None
    _redis: Optional[Any] = None
    _ttl_seconds: int = 900  # 15 minutes default

    def __init__(self, redis_client: Optional[Any] = None, ttl_seconds: int = 900):
        """Initialize the session store service.

        Args:
            redis_client: Optional Redis client (for testing)
            ttl_seconds: TTL for session keys in seconds
        """
        self._redis = redis_client
        self._ttl_seconds = ttl_seconds

    @classmethod
    def get_instance(cls) -> "SessionStoreService":
        """Get the singleton session store instance.

        Returns:
            SessionStoreService instance
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def set_redis_client(cls, redis_client: Any, ttl_seconds: int = 900) -> None:
        """Set the Redis client for the session store.

        Args:
            redis_client: Redis client instance
            ttl_seconds: TTL for session keys
        """
        cls._redis = redis_client
        cls._ttl_seconds = ttl_seconds
        logger.info(
            "Redis client configured for session store",
            extra={"ttl_seconds": ttl_seconds},
        )

    async def get_session(
        self,
        session_id: str,
        trace_id: Optional[str] = None,
    ) -> Optional[SessionState]:
        """Retrieve a session from Redis.

        Args:
            session_id: Session identifier
            trace_id: Trace ID for correlation

        Returns:
            SessionState if found, None otherwise

        Raises:
            RetrievalError: If Redis operation fails
        """
        if trace_id is None:
            trace_id = str(uuid.uuid4())

        if self._redis is None:
            logger.warning(
                "Redis client not configured, returning None for session",
                extra={"session_id": session_id, "trace_id": trace_id},
            )
            return None

        try:
            key = self._make_key(session_id)
            data = await self._redis.get(key)

            if data is None:
                logger.info(
                    "Session not found in Redis",
                    extra={"session_id": session_id, "trace_id": trace_id},
                )
                return None

            session_dict = json.loads(data)
            session = SessionState.from_dict(session_dict)

            logger.info(
                "Session retrieved from Redis",
                extra={
                    "session_id": session_id,
                    "turn_count": session.turn_count,
                    "is_complete": session.is_complete,
                    "trace_id": trace_id,
                },
            )

            return session

        except Exception as e:
            logger.error(
                "Failed to retrieve session from Redis",
                extra={
                    "session_id": session_id,
                    "error": str(e),
                    "trace_id": trace_id,
                },
            )
            raise RetrievalError(
                message=f"Failed to retrieve session: {e}",
                trace_id=trace_id,
            ) from e

    async def create_session(
        self,
        company_id: str,
        original_query: str,
        trace_id: Optional[str] = None,
    ) -> SessionState:
        """Create a new session and store it in Redis.

        Args:
            company_id: Company identifier
            original_query: User's original query text
            trace_id: Trace ID for correlation

        Returns:
            Created SessionState

        Raises:
            RetrievalError: If Redis operation fails
        """
        if trace_id is None:
            trace_id = str(uuid.uuid4())

        session_id = str(uuid.uuid4())
        session = SessionState(
            session_id=session_id,
            company_id=company_id,
            original_query=original_query,
            trace_id=trace_id,
        )

        await self.update_session(session, trace_id=trace_id)

        logger.info(
            "New session created and stored in Redis",
            extra={
                "session_id": session_id,
                "company_id": company_id,
                "trace_id": trace_id,
            },
        )

        return session

    async def update_session(
        self,
        session: SessionState,
        trace_id: Optional[str] = None,
    ) -> bool:
        """Update a session in Redis with automatic TTL refresh.

        Args:
            session: Session state to update
            trace_id: Trace ID for correlation

        Returns:
            True if successful, False otherwise

        Raises:
            RetrievalError: If Redis operation fails
        """
        if trace_id is None:
            trace_id = str(uuid.uuid4())

        if self._redis is None:
            logger.warning(
                "Redis client not configured, session update skipped",
                extra={"session_id": session.session_id, "trace_id": trace_id},
            )
            return False

        try:
            key = self._make_key(session.session_id)
            data = json.dumps(session.to_dict(), ensure_ascii=False)

            await self._redis.set(key, data, ex=self._ttl_seconds)

            logger.info(
                "Session updated in Redis",
                extra={
                    "session_id": session.session_id,
                    "turn_count": session.turn_count,
                    "is_complete": session.is_complete,
                    "trace_id": trace_id,
                },
            )

            return True

        except Exception as e:
            logger.error(
                "Failed to update session in Redis",
                extra={
                    "session_id": session.session_id,
                    "error": str(e),
                    "trace_id": trace_id,
                },
            )
            raise RetrievalError(
                message=f"Failed to update session: {e}",
                trace_id=trace_id,
            ) from e

    async def delete_session(
        self,
        session_id: str,
        trace_id: Optional[str] = None,
    ) -> bool:
        """Delete a session from Redis.

        Args:
            session_id: Session identifier
            trace_id: Trace ID for correlation

        Returns:
            True if deleted, False if not found

        Raises:
            RetrievalError: If Redis operation fails
        """
        if trace_id is None:
            trace_id = str(uuid.uuid4())

        if self._redis is None:
            logger.warning(
                "Redis client not configured, session delete skipped",
                extra={"session_id": session_id, "trace_id": trace_id},
            )
            return False

        try:
            key = self._make_key(session_id)
            result = await self._redis.delete(key)

            if result == 0:
                logger.info(
                    "Session not found for deletion",
                    extra={"session_id": session_id, "trace_id": trace_id},
                )
                return False

            logger.info(
                "Session deleted from Redis",
                extra={"session_id": session_id, "trace_id": trace_id},
            )

            return True

        except Exception as e:
            logger.error(
                "Failed to delete session from Redis",
                extra={
                    "session_id": session_id,
                    "error": str(e),
                    "trace_id": trace_id,
                },
            )
            raise RetrievalError(
                message=f"Failed to delete session: {e}",
                trace_id=trace_id,
            ) from e

    async def increment_turn_count(
        self,
        session: SessionState,
        trace_id: Optional[str] = None,
    ) -> SessionState:
        """Increment the turn count for a session.

        Args:
            session: Session state to update
            trace_id: Trace ID for correlation

        Returns:
            Updated session state
        """
        session.turn_count += 1
        session.updated_at = datetime.utcnow()

        await self.update_session(session, trace_id=trace_id)

        logger.info(
            "Session turn count incremented",
            extra={
                "session_id": session.session_id,
                "new_turn_count": session.turn_count,
                "trace_id": trace_id,
            },
        )

        return session

    async def complete_session(
        self,
        session: SessionState,
        enriched_query: str,
        trace_id: Optional[str] = None,
    ) -> SessionState:
        """Mark a session as complete with the final enriched query.

        Args:
            session: Session state to complete
            enriched_query: Final enriched query for search
            trace_id: Trace ID for correlation

        Returns:
            Updated session state
        """
        session.is_complete = True
        session.enriched_query = enriched_query
        session.updated_at = datetime.utcnow()

        await self.update_session(session, trace_id=trace_id)

        logger.info(
            "Session marked as complete",
            extra={
                "session_id": session.session_id,
                "turn_count": session.turn_count,
                "trace_id": trace_id,
            },
        )

        return session

    def _make_key(self, session_id: str) -> str:
        """Create Redis key for session storage.

        Args:
            session_id: Session identifier

        Returns:
            Redis key string
        """
        return f"query_quality:session:{session_id}"

    async def health_check(self, trace_id: Optional[str] = None) -> bool:
        """Check if Redis connection is healthy.

        Args:
            trace_id: Trace ID for correlation

        Returns:
            True if Redis is available, False otherwise
        """
        if trace_id is None:
            trace_id = str(uuid.uuid4())

        if self._redis is None:
            logger.warning(
                "Redis client not configured for health check",
                extra={"trace_id": trace_id},
            )
            return False

        try:
            await self._redis.ping()
            logger.info("Redis health check passed", extra={"trace_id": trace_id})
            return True
        except Exception as e:
            logger.error(
                "Redis health check failed",
                extra={"error": str(e), "trace_id": trace_id},
            )
            return False


# Global service instance
def get_session_store() -> SessionStoreService:
    """Get the global session store service instance.

    Returns:
        SessionStoreService instance
    """
    return SessionStoreService.get_instance()
