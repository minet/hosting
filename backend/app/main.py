"""
FastAPI application entry point.

Configures the ASGI application with CORS middleware, lifespan management
for the database engine and Proxmox executor, and registers the API router.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import api_router
from app.core.config import get_settings
from app.db.core import close_db_engine, open_db_engine
from app.services.proxmox.executor import close_proxmox_executor

logger = logging.getLogger(__name__)


def _cors_origins() -> list[str]:
    """Resolve CORS origins from the ``FRONTEND_ALLOWED_ORIGINS`` environment setting.

    Splits the comma-separated string and strips whitespace from each origin.

    :returns: List of allowed origin URLs.
    :rtype: list[str]
    """
    raw = get_settings().frontend_allowed_origins
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


async def _purge_loop() -> None:
    """Background loop that runs the expired-membership VM purge daily."""
    await asyncio.sleep(30)  # wait for app to fully start
    while True:
        try:
            from app.core.config import get_settings as _gs
            from app.db.core.engine import get_session_factory
            from app.services.proxmox.gateway import get_proxmox_gateway
            from app.services.vm.purge import run_purge

            settings = _gs()
            if not settings.proxmox_configured:
                logger.debug("purge_loop: Proxmox not configured, skipping")
            else:
                session = get_session_factory()()
                try:
                    run_purge(db=session, gateway=get_proxmox_gateway(), settings=settings)
                finally:
                    session.close()
        except Exception:
            logger.exception("purge_loop: unhandled error")
        await asyncio.sleep(24 * 3600)  # run once per day


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Manage startup and shutdown of shared resources around the application lifetime."""
    open_db_engine()
    purge_task = asyncio.create_task(_purge_loop())
    try:
        yield
    finally:
        purge_task.cancel()
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
