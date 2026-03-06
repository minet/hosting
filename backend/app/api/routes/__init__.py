"""
Routes package for the hosting backend API.

This module re-exports the main API router for use by the application
entry point.
"""

from app.api.routes.api import router as api_router

__all__ = ["api_router"]
