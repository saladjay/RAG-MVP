"""
Caching middleware for prompt retrieval responses.

This module provides L1 (in-memory) caching for prompt templates
using LRU eviction. The cache improves performance by avoiding
repeated template retrievals and renders.

Features:
- LRU cache with configurable size and TTL
- Cache key generation from template_id and version
- Invalidation on template changes
- Graceful fallback when cache is unavailable
"""

import hashlib
import json
import time
from typing import Any, Dict, Optional

from cachetools import TTLCache

from prompt_service.config import get_config
from prompt_service.core.logger import get_logger

logger = get_logger(__name__)


class CacheEntry:
    """A cache entry with metadata.

    Attributes:
        key: The cache key
        value: The cached value
        created_at: Entry creation timestamp
        accessed_at: Last access timestamp
        access_count: Number of times accessed
    """

    def __init__(self, key: str, value: Any):
        """Initialize the cache entry.

        Args:
            key: The cache key
            value: The value to cache
        """
        self.key = key
        self.value = value
        self.created_at = time.time()
        self.accessed_at = self.created_at
        self.access_count = 0

    def touch(self) -> None:
        """Update access timestamp and count."""
        self.accessed_at = time.time()
        self.access_count += 1

    def age(self) -> float:
        """Get entry age in seconds.

        Returns:
            Age in seconds
        """
        return time.time() - self.created_at


class PromptCache:
    """L1 in-memory cache for prompt templates.

    This cache stores rendered prompts to avoid repeated retrieval
    and rendering operations. The cache uses LRU eviction and
    time-based expiration.

    Attributes:
        _cache: The underlying TTLCache instance
        _config: Service configuration
        _enabled: Whether caching is enabled
    """

    def __init__(self):
        """Initialize the prompt cache."""
        self._config = get_config()
        self._enabled = self._config.cache.enabled
        self._cache: Optional[TTLCache] = None

        if self._enabled:
            self._cache = TTLCache(
                maxsize=self._config.cache.max_size,
                ttl=self._config.cache.ttl_seconds,
            )
            logger.info(
                "Prompt cache initialized",
                extra={
                    "max_size": self._config.cache.max_size,
                    "ttl_seconds": self._config.cache.ttl_seconds,
                }
            )
        else:
            logger.info("Prompt cache disabled")

    def _generate_key(
        self,
        template_id: str,
        version: Optional[int] = None,
        variant_id: Optional[str] = None,
    ) -> str:
        """Generate a cache key for the prompt.

        The key includes template_id, version, and variant_id to ensure
        correct cache isolation.

        Args:
            template_id: The prompt template identifier
            version: Optional version number
            variant_id: Optional A/B test variant ID

        Returns:
            The cache key
        """
        key_parts = [template_id]

        if version is not None:
            key_parts.append(f"v{version}")
        else:
            key_parts.append("vactive")

        if variant_id:
            key_parts.append(variant_id)

        key_string = ":".join(key_parts)

        # Hash for shorter keys
        return hashlib.sha256(key_string.encode()).hexdigest()[:16]

    def get(
        self,
        template_id: str,
        version: Optional[int] = None,
        variant_id: Optional[str] = None,
    ) -> Optional[Any]:
        """Get a value from the cache.

        Args:
            template_id: The prompt template identifier
            version: Optional version number
            variant_id: Optional A/B test variant ID

        Returns:
            The cached value or None if not found/expired
        """
        if not self._enabled or self._cache is None:
            return None

        key = self._generate_key(template_id, version, variant_id)

        entry = self._cache.get(key)
        if entry is None:
            logger.debug(
                "Cache miss",
                extra={"template_id": template_id, "key": key}
            )
            return None

        # Update access statistics
        entry.touch()

        logger.debug(
            "Cache hit",
            extra={
                "template_id": template_id,
                "key": key,
                "access_count": entry.access_count,
                "age_seconds": entry.age(),
            }
        )

        return entry.value

    def set(
        self,
        template_id: str,
        value: Any,
        version: Optional[int] = None,
        variant_id: Optional[str] = None,
    ) -> None:
        """Set a value in the cache.

        Args:
            template_id: The prompt template identifier
            value: The value to cache
            version: Optional version number
            variant_id: Optional A/B test variant ID
        """
        if not self._enabled or self._cache is None:
            return

        key = self._generate_key(template_id, version, variant_id)
        entry = CacheEntry(key, value)

        self._cache[key] = entry

        logger.debug(
            "Cache set",
            extra={
                "template_id": template_id,
                "key": key,
                "cache_size": len(self._cache),
            }
        )

    def invalidate(
        self,
        template_id: str,
        version: Optional[int] = None,
    ) -> int:
        """Invalidate cache entries for a template.

        Args:
            template_id: The prompt template identifier
            version: Optional specific version to invalidate
                      (if None, invalidates all versions)

        Returns:
            Number of entries invalidated
        """
        if not self._enabled or self._cache is None:
            return 0

        invalidated = 0
        keys_to_remove = []

        # Find matching keys
        for key in list(self._cache.keys()):
            entry = self._cache[key]
            # Check if this entry matches the template
            # We need to check the key prefix since we stored the hash
            if template_id in str(entry.value):
                if version is None or f"v{version}" in str(entry.value):
                    keys_to_remove.append(key)

        # Remove matched keys
        for key in keys_to_remove:
            del self._cache[key]
            invalidated += 1

        logger.info(
            "Cache invalidated",
            extra={
                "template_id": template_id,
                "version": version,
                "invalidated_count": invalidated,
                "remaining_size": len(self._cache),
            }
        )

        return invalidated

    def clear(self) -> None:
        """Clear all cache entries."""
        if not self._enabled or self._cache is None:
            return

        size = len(self._cache)
        self._cache.clear()

        logger.info(
            "Cache cleared",
            extra={"cleared_count": size}
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Cache statistics dictionary
        """
        if not self._enabled or self._cache is None:
            return {
                "enabled": False,
            }

        return {
            "enabled": True,
            "size": len(self._cache),
            "max_size": self._cache.maxsize,
            "ttl_seconds": self._cache.ttl,
        }

    def cleanup(self) -> int:
        """Clean up expired entries.

        Note: TTLCache handles this automatically, but this method
        can be called manually if needed.

        Returns:
            Number of entries removed
        """
        if not self._enabled or self._cache is None:
            return 0

        # TTLCache automatically expires entries, but we can
        # trigger cleanup by iterating
        initial_size = len(self._cache)
        for key in list(self._cache.keys()):
            self._cache.get(key)  # Access to trigger expiration check

        return initial_size - len(self._cache)


# Global cache instance
_cache: Optional[PromptCache] = None


def get_cache() -> PromptCache:
    """Get the global prompt cache instance.

    Returns:
        Prompt cache instance
    """
    global _cache
    if _cache is None:
        _cache = PromptCache()
    return _cache


def reset_cache() -> None:
    """Reset the global cache instance.

    This is primarily useful for testing.
    """
    global _cache
    if _cache:
        _cache.clear()
    _cache = None
