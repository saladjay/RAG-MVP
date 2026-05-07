"""
Embedding Service for RAG Service.

This module provides text vectorization using multiple backends:
- OpenAI Embeddings API
- HTTP Cloud Embedding Services

It handles:
- Text to vector conversion using embeddings APIs
- Batch embedding support for efficiency
- Error handling and retry logic
- Caching for frequently embedded texts

API Reference:
- Location: src/rag_service/retrieval/embeddings.py
- Class: EmbeddingService
- Class: HTTPEmbeddingService
- Method: embed_text() -> Convert single text to vector
- Method: embed_batch() -> Convert multiple texts to vectors
"""

import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from rag_service.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class EmbeddingResult:
    """Result of text embedding.

    Attributes:
        text: Original text that was embedded
        vector: Embedding vector
        model: Model used for embedding
        dimension: Vector dimension
    """
    text: str
    vector: List[float]
    model: str
    dimension: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "text": self.text,
            "vector": self.vector,
            "model": self.model,
            "dimension": self.dimension,
        }


class EmbeddingService:
    """
    Service for generating text embeddings using OpenAI API.

    This service uses OpenAI's text-embedding-3-small model by default,
    which produces 1536-dimensional vectors. It supports both single
    text and batch embedding operations.

    Attributes:
        model: OpenAI embedding model to use
        dimension: Vector dimension for the model
        client: OpenAI client instance
        cache: Optional cache for frequently embedded texts
    """

    # Model configurations
    MODELS = {
        "text-embedding-3-small": {"dimension": 1536, "max_tokens": 8191},
        "text-embedding-3-large": {"dimension": 3072, "max_tokens": 8191},
        "text-embedding-ada-002": {"dimension": 1536, "max_tokens": 8191},
    }

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        api_key: Optional[str] = None,
        cache_enabled: bool = True,
        cache_size: int = 1000,
    ):
        """Initialize the embedding service.

        Args:
            model: OpenAI embedding model to use
            api_key: Optional OpenAI API key (defaults to env var)
            cache_enabled: Whether to cache embedding results
            cache_size: Maximum number of cached embeddings
        """
        if model not in self.MODELS:
            raise ValueError(
                f"Unknown model: {model}. "
                f"Valid models: {list(self.MODELS.keys())}"
            )

        self.model = model
        self.dimension = self.MODELS[model]["dimension"]
        self._cache_enabled = cache_enabled
        self._cache: Dict[str, List[float]] = {} if cache_enabled else None

        # Initialize OpenAI client
        self._init_client(api_key)

    def _init_client(self, api_key: Optional[str]) -> None:
        """Initialize OpenAI client.

        Args:
            api_key: Optional API key
        """
        try:
            from openai import OpenAI

            client_kwargs = {}
            if api_key:
                client_kwargs["api_key"] = api_key

            self.client = OpenAI(**client_kwargs)

            logger.info(
                "Initialized OpenAI embedding service",
                extra={"model": self.model, "dimension": self.dimension},
            )

        except ImportError:
            logger.error(
                "OpenAI package not installed. "
                "Install with: uv add openai"
            )
            raise
        except Exception as e:
            logger.error(
                f"Failed to initialize OpenAI client: {e}"
            )
            raise

    def embed_text(
        self,
        text: str,
        use_cache: bool = True,
    ) -> List[float]:
        """
        Generate embedding vector for a single text.

        Args:
            text: Text to embed
            use_cache: Whether to use cached result if available

        Returns:
            Embedding vector as list of floats

        Raises:
            ValueError: If text is empty
            RuntimeError: If embedding generation fails
        """
        if not text or not text.strip():
            raise ValueError("Cannot embed empty text")

        # Check cache
        if self._cache_enabled and use_cache:
            cached = self._cache.get(text)
            if cached is not None:
                logger.debug("Using cached embedding", extra={"text_length": len(text)})
                return cached

        try:
            response = self.client.embeddings.create(
                input=text,
                model=self.model,
            )

            vector = response.data[0].embedding

            # Validate vector dimension
            if len(vector) != self.dimension:
                logger.warning(
                    "Embedding dimension mismatch",
                    extra={
                        "expected": self.dimension,
                        "actual": len(vector),
                    }
                )

            # Cache result
            if self._cache_enabled and use_cache:
                self._cache[text] = vector
                # Limit cache size
                if len(self._cache) > self._cache_size if hasattr(self, '_cache_size') else False:
                    # Remove oldest entry (simple FIFO)
                    oldest_key = next(iter(self._cache))
                    del self._cache[oldest_key]

            logger.debug(
                "Generated embedding",
                extra={
                    "text_length": len(text),
                    "dimension": len(vector),
                },
            )

            return vector

        except Exception as e:
            logger.error(
                "Failed to generate embedding",
                extra={"error": str(e), "text_length": len(text)},
            )
            raise RuntimeError(f"Embedding generation failed: {e}")

    def embed_batch(
        self,
        texts: List[str],
        use_cache: bool = True,
    ) -> List[List[float]]:
        """
        Generate embedding vectors for multiple texts.

        More efficient than calling embed_text multiple times
        as it processes multiple embeddings in a single API call.

        Args:
            texts: List of texts to embed
            use_cache: Whether to use cached results where available

        Returns:
            List of embedding vectors

        Raises:
            ValueError: If texts list is empty
            RuntimeError: If embedding generation fails
        """
        if not texts:
            raise ValueError("Cannot embed empty text list")

        # Filter out texts that are cached
        uncached_texts = []
        uncached_indices = []
        results = [None] * len(texts)

        if self._cache_enabled and use_cache:
            for i, text in enumerate(texts):
                if not text or not text.strip():
                    raise ValueError(f"Cannot embed empty text at index {i}")

                cached = self._cache.get(text)
                if cached is not None:
                    results[i] = cached
                else:
                    uncached_texts.append(text)
                    uncached_indices.append(i)
        else:
            uncached_texts = texts
            uncached_indices = list(range(len(texts)))

        # If all cached, return immediately
        if not uncached_texts:
            logger.debug("All embeddings retrieved from cache")
            return results

        try:
            # Batch embed uncached texts
            response = self.client.embeddings.create(
                input=uncached_texts,
                model=self.model,
            )

            # Map results back to original indices
            for i, embedding_result in enumerate(response.data):
                original_index = uncached_indices[i]
                vector = embedding_result.embedding
                results[original_index] = vector

                # Cache result
                if self._cache_enabled and use_cache:
                    text = uncached_texts[i]
                    self._cache[text] = vector

            logger.info(
                "Generated batch embeddings",
                extra={
                    "total": len(texts),
                    "cached": len(texts) - len(uncached_texts),
                    "generated": len(uncached_texts),
                },
            )

            return results

        except Exception as e:
            logger.error(
                "Failed to generate batch embeddings",
                extra={"error": str(e), "batch_size": len(texts)},
            )
            raise RuntimeError(f"Batch embedding generation failed: {e}")

    async def aembed_text(
        self,
        text: str,
        use_cache: bool = True,
    ) -> List[float]:
        """
        Async version of embed_text.

        Args:
            text: Text to embed
            use_cache: Whether to use cached result

        Returns:
            Embedding vector as list of floats
        """
        # Run blocking embed_text in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.embed_text,
            text,
            use_cache,
        )

    async def aembed_batch(
        self,
        texts: List[str],
        use_cache: bool = True,
    ) -> List[List[float]]:
        """
        Async version of embed_batch.

        Args:
            texts: List of texts to embed
            use_cache: Whether to use cached results

        Returns:
            List of embedding vectors
        """
        # Run blocking embed_batch in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.embed_batch,
            texts,
            use_cache,
        )

    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        if self._cache_enabled and self._cache:
            self._cache.clear()
            logger.debug("Cleared embedding cache")

    def get_cache_size(self) -> int:
        """Get current cache size.

        Returns:
            Number of cached embeddings
        """
        return len(self._cache) if self._cache else 0


# Global singleton instance
_embedding_service: Optional[EmbeddingService] = None
_service_lock = asyncio.Lock()


async def get_embedding_service() -> EmbeddingService:
    """Get or create the global embedding service singleton.

    Returns:
        The global EmbeddingService instance
    """
    global _embedding_service

    async with _service_lock:
        if _embedding_service is None:
            # Read configuration from environment
            import os

            model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
            api_key = os.getenv("OPENAI_API_KEY")
            cache_enabled = os.getenv("EMBEDDING_CACHE_ENABLED", "true").lower() == "true"

            _embedding_service = EmbeddingService(
                model=model,
                api_key=api_key,
                cache_enabled=cache_enabled,
            )
            logger.info("Initialized global embedding service")

    return _embedding_service


def reset_embedding_service() -> None:
    """Reset the global embedding service instance.

    This is primarily used for testing to ensure clean state between tests.
    """
    global _embedding_service
    _embedding_service = None
    logger.debug("Reset global embedding service")


# ============================================================================
# HTTP Embedding Service
# ============================================================================

class HTTPEmbeddingService:
    """
    Service for generating text embeddings using HTTP cloud API.

    This service uses cloud-hosted embedding models via HTTP API,
    supporting models like bge-m3, text-embedding-3-small, etc.

    Attributes:
        gateway: HTTP embedding gateway
        model: Model name
        dimension: Vector dimension
        cache: Optional cache for frequently embedded texts
    """

    def __init__(
        self,
        url: str,
        model: str = "bge-m3",
        timeout: int = 30,
        auth_token: str = "",
        cache_enabled: bool = True,
        cache_size: int = 1000,
    ):
        """Initialize the HTTP embedding service.

        Args:
            url: Embedding API endpoint URL
            model: Model name
            timeout: Request timeout in seconds
            auth_token: Basic auth token (format: "username:password")
            cache_enabled: Whether to cache embedding results
            cache_size: Maximum number of cached embeddings
        """
        from rag_service.inference.gateway import HTTPEmbeddingGateway

        self.gateway = HTTPEmbeddingGateway(
            url=url,
            model=model,
            timeout=timeout,
            auth_token=auth_token,
        )
        self.model = model
        self.dimension = None  # Will be set on first embedding
        self._cache_enabled = cache_enabled
        self._cache: Dict[str, List[float]] = {} if cache_enabled else None
        self._cache_size = cache_size

        logger.info(
            "Initialized HTTP embedding service",
            extra={"url": url, "model": model},
        )

    async def embed_text(
        self,
        text: str,
        use_cache: bool = True,
    ) -> List[float]:
        """Generate embedding vector for a single text.

        Args:
            text: Text to embed
            use_cache: Whether to use cached result if available

        Returns:
            Embedding vector as list of floats

        Raises:
            ValueError: If text is empty
            RuntimeError: If embedding generation fails
        """
        if not text or not text.strip():
            raise ValueError("Cannot embed empty text")

        # Check cache
        if self._cache_enabled and use_cache:
            cached = self._cache.get(text)
            if cached is not None:
                logger.debug("Using cached embedding", extra={"text_length": len(text)})
                return cached

        # Generate embedding
        result = await self.gateway.embed(text)

        # Set dimension on first call
        if self.dimension is None:
            self.dimension = result.dimension

        vector = result.embedding

        # Validate vector dimension
        if self.dimension and len(vector) != self.dimension:
            logger.warning(
                "Embedding dimension mismatch",
                extra={
                    "expected": self.dimension,
                    "actual": len(vector),
                }
            )

        # Cache result
        if self._cache_enabled and use_cache:
            self._cache[text] = vector
            # Limit cache size
            if len(self._cache) > self._cache_size:
                # Remove oldest entry (simple FIFO)
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]

        logger.debug(
            "Generated HTTP embedding",
            extra={
                "text_length": len(text),
                "dimension": len(vector),
                "latency_ms": result.latency_ms,
            },
        )

        return vector

    async def embed_batch(
        self,
        texts: List[str],
        use_cache: bool = True,
    ) -> List[List[float]]:
        """Generate embedding vectors for multiple texts.

        Args:
            texts: List of texts to embed
            use_cache: Whether to use cached results where available

        Returns:
            List of embedding vectors

        Raises:
            ValueError: If texts list is empty
            RuntimeError: If embedding generation fails
        """
        if not texts:
            raise ValueError("Cannot embed empty text list")

        # Filter out texts that are cached
        uncached_texts = []
        uncached_indices = []
        results = [None] * len(texts)

        if self._cache_enabled and use_cache:
            for i, text in enumerate(texts):
                if not text or not text.strip():
                    raise ValueError(f"Cannot embed empty text at index {i}")

                cached = self._cache.get(text)
                if cached is not None:
                    results[i] = cached
                else:
                    uncached_texts.append(text)
                    uncached_indices.append(i)
        else:
            uncached_texts = texts
            uncached_indices = list(range(len(texts)))

        # Generate embeddings for uncached texts
        if uncached_texts:
            embedding_results = await self.gateway.embed_batch(uncached_texts)

            for i, result in enumerate(embedding_results):
                idx = uncached_indices[i]
                results[idx] = result.embedding

                # Set dimension on first call
                if self.dimension is None:
                    self.dimension = result.dimension

                # Cache result
                if self._cache_enabled and use_cache:
                    self._cache[uncached_texts[i]] = result.embedding

        logger.info(
            "Generated HTTP batch embeddings",
            extra={
                "total": len(texts),
                "cached": len(texts) - len(uncached_texts),
                "generated": len(uncached_texts),
            },
        )

        return results

    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        if self._cache_enabled and self._cache:
            self._cache.clear()
            logger.debug("Cleared HTTP embedding cache")

    def get_cache_size(self) -> int:
        """Get current cache size.

        Returns:
            Number of cached embeddings
        """
        return len(self._cache) if self._cache else 0


# Global HTTP embedding service instance
_http_embedding_service: Optional[HTTPEmbeddingService] = None
_http_service_lock = asyncio.Lock()


async def get_http_embedding_service() -> HTTPEmbeddingService:
    """Get or create the global HTTP embedding service singleton.

    Returns:
        The global HTTPEmbeddingService instance

    Raises:
        RuntimeError: If cloud embedding is not configured
    """
    global _http_embedding_service

    async with _http_service_lock:
        if _http_embedding_service is None:
            from rag_service.config import get_settings

            settings = get_settings()

            if not settings.cloud_embedding.enabled:
                raise RuntimeError(
                    "Cloud embedding is not configured. "
                    "Set CLOUD_EMBEDDING_URL environment variable."
                )

            _http_embedding_service = HTTPEmbeddingService(
                url=settings.cloud_embedding.url,
                model=settings.cloud_embedding.model,
                timeout=settings.cloud_embedding.timeout,
                auth_token=settings.cloud_embedding.auth_token,
            )
            logger.info("Initialized global HTTP embedding service")

    return _http_embedding_service


def reset_http_embedding_service() -> None:
    """Reset the global HTTP embedding service instance.

    This is primarily used for testing.
    """
    global _http_embedding_service
    _http_embedding_service = None
    logger.debug("Reset global HTTP embedding service")
