"""
FastAPI application entry point.

Configures the ASGI application with CORS middleware, lifespan management
for the database engine and Proxmox executor, and registers the API router.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import api_router
from app.core.config import get_settings
from app.db.core import close_db_engine, open_db_engine
from app.services.proxmox.executor import close_proxmox_executor


def _cors_origins() -> list[str]:
    """Resolve CORS origins from the ``FRONTEND_ALLOWED_ORIGINS`` environment setting.

    Splits the comma-separated string and strips whitespace from each origin.

    :returns: List of allowed origin URLs.
    :rtype: list[str]
    """
    raw = get_settings().frontend_allowed_origins
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Manage startup and shutdown of shared resources around the application lifetime.

    Opens the database engine on startup and closes the Proxmox executor and
    database engine on shutdown.

    :param _: The FastAPI application instance (unused).
    :type _: FastAPI
    """
    open_db_engine()
    try:
        yield
    finally:
        close_proxmox_executor()
        close_db_engine()


_settings = get_settings()
app = FastAPI(
    title=_settings.app_name,
    debug=_settings.app_debug,
    lifespan=lifespan,
    docs_url=None if _settings.is_production else "/docs",
    redoc_url=None if _settings.is_production else "/redoc",
    openapi_url=None if _settings.is_production else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.mount("/assets", StaticFiles(directory="/app/assets"), name="assets")
