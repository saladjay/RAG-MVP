"""
Redis Belief State Store Service for Conversational Query Enhancement.

This service manages belief state for multi-turn conversations in the
Conversational Query Enhancement module. It uses Redis for fast, scalable
state storage with automatic TTL-based expiration.

Key features:
- Belief state CRUD operations with automatic serialization
- Slot accumulation across conversation turns
- TTL-based expiration to prevent stale sessions
- Graceful degradation when Redis is unavailable
- Full trace ID propagation for observability
"""

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from rag_service.core.exceptions import RetrievalError
from rag_service.core.logger import get_logger
from rag_service.models.conversational_query import BeliefState

logger = get_logger(__name__)


class BeliefStateStoreService:
    """Service for managing conversational query belief state in Redis.

    This service provides CRUD operations for belief state, with automatic
    serialization/deserialization and TTL-based expiration.

    Attributes:
        _redis: Redis client instance
        _ttl_seconds: Default TTL for state keys
    """

    _instance: Optional["BeliefStateStoreService"] = None
    _redis: Optional[Any] = None
    _ttl_seconds: int = 900  # 15 minutes default

    def __init__(self, redis_client: Optional[Any] = None, ttl_seconds: int = 900):
        """Initialize the belief state store service.

        Args:
            redis_client: Optional Redis client (for testing)
            ttl_seconds: TTL for state keys in seconds
        """
        self._redis = redis_client
        self._ttl_seconds = ttl_seconds

    @classmethod
    def get_instance(cls) -> "BeliefStateStoreService":
        """Get the singleton belief state store instance.

        Returns:
            BeliefStateStoreService instance
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def set_redis_client(cls, redis_client: Any, ttl_seconds: int = 900) -> None:
        """Set the Redis client for the belief state store.

        Args:
            redis_client: Redis client instance
            ttl_seconds: TTL for state keys
        """
        cls._redis = redis_client
        cls._ttl_seconds = ttl_seconds
        logger.info(
            "Redis client configured for belief state store",
            extra={"ttl_seconds": ttl_seconds},
        )

    async def get_state(
        self,
        session_id: str,
        trace_id: Optional[str] = None,
    ) -> Optional[BeliefState]:
        """Retrieve a belief state from Redis.

        Args:
            session_id: Session identifier
            trace_id: Trace ID for correlation

        Returns:
            BeliefState if found, None otherwise

        Raises:
            RetrievalError: If Redis operation fails
        """
        if trace_id is None:
            trace_id = str(uuid.uuid4())

        if self._redis is None:
            logger.warning(
                "Redis client not configured, returning None for belief state",
                extra={"session_id": session_id, "trace_id": trace_id},
            )
            return None

        try:
            key = self._make_key(session_id)
            data = await self._redis.get(key)

            if data is None:
                logger.info(
                    "Belief state not found in Redis",
                    extra={"session_id": session_id, "trace_id": trace_id},
                )
                return None

            state_dict = json.loads(data)
            state = BeliefState.from_dict(state_dict)

            logger.info(
                "Belief state retrieved from Redis",
                extra={
                    "session_id": session_id,
                    "conversation_turn": state.conversation_turn,
                    "slot_count": len(state.slots),
                    "trace_id": trace_id,
                },
            )

            return state

        except Exception as e:
            logger.error(
                "Failed to retrieve belief state from Redis",
                extra={
                    "session_id": session_id,
                    "error": str(e),
                    "trace_id": trace_id,
                },
            )
            raise RetrievalError(
                message=f"Failed to retrieve belief state: {e}",
                trace_id=trace_id,
            ) from e

    async def create_state(
        self,
        session_id: str,
        trace_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> BeliefState:
        """Create a new belief state and store it in Redis.

        Args:
            session_id: Session identifier
            trace_id: Trace ID for correlation
            user_id: Optional user identifier

        Returns:
            Created BeliefState

        Raises:
            RetrievalError: If Redis operation fails
        """
        if trace_id is None:
            trace_id = str(uuid.uuid4())

        state = BeliefState(
            session_id=session_id,
            user_id=user_id,
        )

        await self.update_state(state, trace_id=trace_id)

        logger.info(
            "New belief state created and stored in Redis",
            extra={
                "session_id": session_id,
                "user_id": user_id,
                "trace_id": trace_id,
            },
        )

        return state

    async def update_state(
        self,
        state: BeliefState,
        trace_id: Optional[str] = None,
    ) -> bool:
        """Update a belief state in Redis with automatic TTL refresh.

        Args:
            state: Belief state to update
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
                "Redis client not configured, belief state update skipped",
                extra={"session_id": state.session_id, "trace_id": trace_id},
            )
            return False

        try:
            key = self._make_key(state.session_id)
            data = json.dumps(state.to_dict(), ensure_ascii=False)

            await self._redis.set(key, data, ex=self._ttl_seconds)

            logger.info(
                "Belief state updated in Redis",
                extra={
                    "session_id": state.session_id,
                    "conversation_turn": state.conversation_turn,
                    "slot_count": len(state.slots),
                    "trace_id": trace_id,
                },
            )

            return True

        except Exception as e:
            logger.error(
                "Failed to update belief state in Redis",
                extra={
                    "session_id": state.session_id,
                    "error": str(e),
                    "trace_id": trace_id,
                },
            )
            raise RetrievalError(
                message=f"Failed to update belief state: {e}",
                trace_id=trace_id,
            ) from e

    async def delete_state(
        self,
        session_id: str,
        trace_id: Optional[str] = None,
    ) -> bool:
        """Delete a belief state from Redis.

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
                "Redis client not configured, belief state delete skipped",
                extra={"session_id": session_id, "trace_id": trace_id},
            )
            return False

        try:
            key = self._make_key(session_id)
            result = await self._redis.delete(key)

            if result == 0:
                logger.info(
                    "Belief state not found for deletion",
                    extra={"session_id": session_id, "trace_id": trace_id},
                )
                return False

            logger.info(
                "Belief state deleted from Redis",
                extra={"session_id": session_id, "trace_id": trace_id},
            )

            return True

        except Exception as e:
            logger.error(
                "Failed to delete belief state from Redis",
                extra={
                    "session_id": session_id,
                    "error": str(e),
                    "trace_id": trace_id,
                },
            )
            raise RetrievalError(
                message=f"Failed to delete belief state: {e}",
                trace_id=trace_id,
            ) from e

    async def update_slots(
        self,
        session_id: str,
        slots: Dict[str, Any],
        trace_id: Optional[str] = None,
    ) -> Optional[BeliefState]:
        """Update specific slots in a belief state.

        Args:
            session_id: Session identifier
            slots: Slots to update (key-value pairs)
            trace_id: Trace ID for correlation

        Returns:
            Updated BeliefState if found, None otherwise

        Raises:
            RetrievalError: If Redis operation fails
        """
        state = await self.get_state(session_id, trace_id)
        if state is None:
            return None

        for key, value in slots.items():
            state.set_slot(key, value)

        await self.update_state(state, trace_id=trace_id)

        logger.info(
            "Belief state slots updated",
            extra={
                "session_id": session_id,
                "updated_slots": list(slots.keys()),
                "trace_id": trace_id,
            },
        )

        return state

    async def add_query_to_history(
        self,
        session_id: str,
        query: str,
        trace_id: Optional[str] = None,
    ) -> Optional[BeliefState]:
        """Add a query to the belief state history.

        Args:
            session_id: Session identifier
            query: Query text to add
            trace_id: Trace ID for correlation

        Returns:
            Updated BeliefState if found, None otherwise

        Raises:
            RetrievalError: If Redis operation fails
        """
        state = await self.get_state(session_id, trace_id)
        if state is None:
            return None

        state.add_query(query)
        await self.update_state(state, trace_id=trace_id)

        logger.info(
            "Query added to belief state history",
            extra={
                "session_id": session_id,
                "conversation_turn": state.conversation_turn,
                "trace_id": trace_id,
            },
        )

        return state

    async def get_conversation_history(
        self,
        session_id: str,
        trace_id: Optional[str] = None,
    ) -> List[str]:
        """Get conversation history from belief state.

        Args:
            session_id: Session identifier
            trace_id: Trace ID for correlation

        Returns:
            List of query history, empty list if not found
        """
        state = await self.get_state(session_id, trace_id)
        if state is None:
            return []

        return state.query_history

    def _make_key(self, session_id: str) -> str:
        """Create Redis key for belief state storage.

        Args:
            session_id: Session identifier

        Returns:
            Redis key string
        """
        return f"conversational_query:belief_state:{session_id}"

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
def get_belief_state_store() -> BeliefStateStoreService:
    """Get the global belief state store service instance.

    Returns:
        BeliefStateStoreService instance
    """
    return BeliefStateStoreService.get_instance()
