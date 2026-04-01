"""
API package - HTTP interface layer.

This package provides the HTTP API endpoints using FastAPI.
All routes use capability interfaces ONLY, never direct component access.
"""

from rag_service.api.routes import router

__all__ = ["router"]
