"""
FastAPI application entry point for RAG Service.

This module creates and configures the FastAPI application with
lifecycle management, middleware, and capability registration.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from rag_service.api.routes import router
from rag_service.api.qa_routes import router as qa_router
from rag_service.api.kb_upload_routes import router as kb_upload_router
from rag_service.capabilities.base import get_capability_registry
from rag_service.capabilities.external_kb_query import ExternalKBQueryCapability
from rag_service.capabilities.health_check import HealthCheckCapability
from rag_service.capabilities.knowledge_query import KnowledgeQueryCapability
from rag_service.capabilities.model_discovery import ModelDiscoveryCapability
from rag_service.capabilities.model_inference import ModelInferenceCapability
from rag_service.capabilities.trace_observation import TraceObservationCapability
from rag_service.capabilities.document_management import DocumentManagementCapability
from rag_service.capabilities.milvus_kb_upload import MilvusKBUploadCapability
from rag_service.config import get_settings
from rag_service.core.logger import get_logger, set_trace_id


# Module logger
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager.

    Handles startup and shutdown events for the FastAPI application.
    """
    settings = get_settings()

    # Startup
    logger.info("Starting RAG Service MVP")
    logger.info(f"Milvus: {settings.milvus.connection_url}")

    # Show model configuration based on default gateway
    if settings.default_gateway == "http" and settings.cloud_completion.url:
        logger.info(f"Model Gateway: HTTP (Cloud Completion)")
        logger.info(f"Model: {settings.cloud_completion.model}")
        logger.info(f"Cloud URL: {settings.cloud_completion.url}")
    else:
        logger.info(f"Model Gateway: LiteLLM")
        logger.info(f"Model: {settings.litellm.model}")

    logger.info(f"Langfuse Enabled: {settings.langfuse.enabled}")

    # Initialize capability registry
    registry = get_capability_registry()

    # Register capabilities
    # Note: Components are injected as None for now - will be wired up properly
    registry.register(HealthCheckCapability(capabilities=registry._capabilities))
    registry.register(KnowledgeQueryCapability(milvus_client=None))
    registry.register(ExternalKBQueryCapability())
    registry.register(ModelInferenceCapability(litellm_client=None))
    registry.register(TraceObservationCapability(trace_manager=None))
    registry.register(DocumentManagementCapability(knowledge_base=None))
    registry.register(ModelDiscoveryCapability(litellm_client=None))
    registry.register(MilvusKBUploadCapability())

    logger.info(f"Registered capabilities: {registry.list_capabilities()}")

    yield

    # Shutdown
    logger.info("Shutting down RAG Service MVP")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

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
        allow_origins=settings.cors.origins,
        allow_credentials=settings.cors.allow_credentials,
        allow_methods=settings.cors.allow_methods,
        allow_headers=settings.cors.allow_headers,
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
    app.include_router(router)
    app.include_router(qa_router)
    app.include_router(kb_upload_router)

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
