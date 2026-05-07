"""
FastAPI application entry point for RAG Service.

This module creates and configures the FastAPI application with
lifecycle management, middleware, and capability registration.

Architecture (3 Unified Capabilities):
- QueryCapability: Unified query pipeline with strategy switching
- ManagementCapability: Document management and model discovery
- TraceCapability: Health checks and trace observation
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from rag_service.api.unified_routes import router as unified_router
from rag_service.capabilities.base import get_capability_registry
from rag_service.capabilities.query_capability import QueryCapability
from rag_service.capabilities.management_capability import ManagementCapability
from rag_service.capabilities.trace_capability import TraceCapability
from rag_service.config import get_settings
from rag_service.core.logger import get_logger, set_trace_id
from rag_service.services.session_store import SessionStoreService
from rag_service.services.belief_state_store import BeliefStateStoreService


# Module logger
logger = get_logger(__name__)


# Redis client reference (for cleanup)
_redis_client: Optional[any] = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — startup and shutdown.

    Registers 3 unified capabilities, initializes Redis for session stores.
    """
    global _redis_client

    settings = get_settings()

    # Startup
    logger.info("Starting RAG Service")
    logger.info(f"Milvus: {settings.milvus.connection_url}")
    logger.info(f"Provider: {settings.litellm.provider} ({settings.litellm.model})")
    logger.info(f"Retrieval: {settings.query.retrieval_backend}")
    logger.info(f"Quality: {settings.query.quality_mode}")
    logger.info(f"Langfuse: {settings.langfuse.enabled}")

    # Initialize Redis connection for session stores
    try:
        import aioredis

        _redis_client = await aioredis.from_url(
            f"redis://{settings.query.redis_host}:{settings.query.redis_port}/{settings.query.redis_db}",
            password=settings.query.redis_password or None,
            encoding="utf-8",
            decode_responses=True,
        )

        # Configure session store with Redis client
        SessionStoreService.set_redis_client(
            redis_client=_redis_client,
            ttl_seconds=settings.query.redis_ttl,
        )

        # Configure belief state store with Redis client
        BeliefStateStoreService.set_redis_client(
            redis_client=_redis_client,
            ttl_seconds=settings.query.redis_ttl,
        )

        await _redis_client.ping()
        logger.info("Redis connection verified")

    except Exception as e:
        logger.warning(
            f"Redis connection failed: {e}. Session features will run without persistence.",
            extra={"error": str(e)},
        )
        _redis_client = None

    # Initialize capability registry
    registry = get_capability_registry()

    # Register 3 unified capabilities
    registry.register(QueryCapability())
    registry.register(ManagementCapability())
    registry.register(TraceCapability())

    logger.info(f"Registered capabilities: {registry.list_capabilities()}")

    yield

    # Shutdown
    logger.info("Shutting down RAG Service")

    if _redis_client:
        try:
            await _redis_client.close()
            logger.info("Redis connection closed")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    settings = get_settings()

    # Create FastAPI app
    app = FastAPI(
        title="RAG Service MVP",
        description="AI Component Validation Platform with RAG capabilities",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.server.cors_origins,
        allow_credentials=settings.server.cors_allow_credentials,
        allow_methods=settings.server.cors_allow_methods,
        allow_headers=settings.server.cors_allow_headers,
    )

    # Add request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next) -> Response:
        """Log all incoming requests with trace_id."""
        # Extract or generate trace_id
        trace_id = request.headers.get("X-Trace-ID", "")
        if not trace_id:
            import uuid
            trace_id = str(uuid.uuid4())[:8]

        # Set trace_id in context for logging
        set_trace_id(trace_id)

        # Log request
        logger.info(f"{request.method} {request.url.path}")

        # Process request
        response = await call_next(request)

        # Add trace_id to response headers
        response.headers["X-Trace-ID"] = trace_id

        return response

    # Exception handlers
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle all uncaught exceptions."""
        logger.error(f"Unhandled exception: {exc}", exc_info=True)

        return JSONResponse(
            status_code=500,
            content={
                "message": "Internal server error",
                "detail": str(exc) if settings.server.log_level == "DEBUG" else None,
            },
        )

    # Include routes
    app.include_router(unified_router, prefix="/api/v1")

    # Root endpoint
    @app.get("/")
    async def root() -> dict[str, str]:
        """Root endpoint with service information."""
        return {
            "service": "RAG Service MVP",
            "version": "0.1.0",
            "status": "running",
            "docs": "/docs",
        }

    return app


# Create app instance for uvicorn
app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()

    uvicorn.run(
        "rag_service.main:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=settings.server.reload,
        log_level=settings.server.log_level.lower(),
    )
