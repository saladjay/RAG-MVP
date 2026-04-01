"""
FastAPI application entry point for Prompt Management Service.

This module initializes the FastAPI application with:
- Lifespan context manager for resource management
- CORS middleware configuration
- Health check endpoint
- API router registration
- Global exception handlers

Main Application:
- The app instance is created at module import time
- Resources are initialized during lifespan startup
- All routes are registered under /api/v1 prefix
"""

import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from prompt_service.config import get_config
from prompt_service.core.exceptions import PromptServiceError
from prompt_service.core.logger import get_logger, setup_logging
from prompt_service.services.langfuse_client import (
    LangfuseClientWrapper,
    get_langfuse_client,
)

logger = get_logger(__name__)

# Store application start time
_app_start_time: float = 0.0


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for application startup/shutdown.

    Initializes resources on startup and performs cleanup on shutdown.

    Args:
        app: The FastAPI application instance

    Yields:
        None
    """
    global _app_start_time
    _app_start_time = time.time()

    config = get_config()

    # Setup logging
    setup_logging(
        level=config.service.log_level,
        log_format="json" if config.is_production() else "text",
    )

    logger.info(
        "Starting Prompt Management Service",
        extra={
            "environment": config.service.environment,
            "port": config.service.port,
        }
    )

    # Initialize Langfuse client
    langfuse_client: LangfuseClientWrapper = get_langfuse_client()

    # Log Langfuse status
    health = langfuse_client.health()
    logger.info(
        "Langfuse connection status",
        extra={"langfuse_status": health["status"]}
    )

    # Store client and start time in app state for access in routes
    app.state.langfuse_client = langfuse_client
    app.state.config = config
    app.state.start_time = _app_start_time

    yield

    # Shutdown: Flush Langfuse client
    logger.info("Shutting down Prompt Management Service")
    langfuse_client.flush()


# Create FastAPI application
app = FastAPI(
    title="Prompt Management Service",
    description="Middleware for Langfuse prompt operations with A/B testing and analytics",
    version="0.1.0",
    lifespan=lifespan,
)


# Configure CORS middleware
config = get_config()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if config.is_development() else [
        "https://your-production-domain.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Trace-ID"],
)


# ============================================================================
# Health Check Endpoint
# ============================================================================

@app.get("/health", tags=["health"])
async def health_check(request: Request) -> dict:
    """Get service health status.

    Returns the overall health status and component statuses.

    Returns:
        Health status dictionary
    """
    langfuse_client = get_langfuse_client()
    langfuse_health = langfuse_client.health()

    # Calculate uptime from app state
    uptime_ms = 0.0
    if hasattr(request.app.state, "start_time"):
        uptime_ms = (time.time() - request.app.state.start_time) * 1000

    return {
        "status": "healthy" if langfuse_health["status"] == "connected" else "degraded",
        "version": "0.1.0",
        "components": {
            "langfuse": langfuse_health["status"],
            "cache": "enabled" if config.cache.enabled else "disabled",
        },
        "uptime_ms": uptime_ms,
    }


# ============================================================================
# Global Exception Handlers
# ============================================================================

@app.exception_handler(PromptServiceError)
async def prompt_service_error_handler(
    request: Request,
    exc: PromptServiceError,
) -> JSONResponse:
    """Handle PromptServiceError exceptions.

    Args:
        request: The incoming request
        exc: The exception that was raised

    Returns:
        JSON response with error details
    """
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        if exc.error_code == "SERVICE_UNAVAILABLE"
        else status.HTTP_400_BAD_REQUEST,
        content=exc.to_dict(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Handle all other exceptions.

    Args:
        request: The incoming request
        exc: The exception that was raised

    Returns:
        JSON response with error details
    """
    logger.error(
        "Unhandled exception",
        extra={
            "path": str(request.url.path),
            "method": request.method,
            "error": str(exc),
        },
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
        },
    )


# ============================================================================
# API Router Registration
# ============================================================================

# Import and register API routes
from prompt_service.api.routes import router as api_router
app.include_router(api_router)


# ============================================================================
# Root Endpoint
# ============================================================================

@app.get("/", tags=["root"])
async def root() -> dict:
    """Root endpoint with service information.

    Returns:
        Service information dictionary
    """
    return {
        "service": "Prompt Management Service",
        "version": "0.1.0",
        "status": "running",
        "docs_url": "/docs",
        "health_url": "/health",
    }


# ============================================================================
# Application Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    config = get_config()

    uvicorn.run(
        "prompt_service.main:app",
        host=config.service.host,
        port=config.service.port,
        reload=config.is_development(),
        log_level=config.service.log_level.lower(),
    )
