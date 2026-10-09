"""The ASGI application.

    uvicorn --factory teeter_api.app:create_app      or      teeter-api serve

Serves the API under /v1 and, when TEETER_SITE_DIR points at the website, the
site and the app at /. Served from here, the app finds /v1/health and runs
live against this server; served anywhere else, it stays the prototype.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import __version__
from .db import Database
from .errors import ApiError, api_error_handler, validation_handler
from .routes import ROUTERS
from .settings import Settings, get_settings
from .storage import make_storage


def create_app(settings: Settings | None = None, db: Database | None = None) -> FastAPI:
    settings = settings or get_settings()
    db = db or Database(settings.database_url, pool_size=settings.db_pool_size,
                        direct_url=settings.database_url_direct)
    if not db.is_postgres:
        db.create_all()       # SQLite, for tests and dev; Postgres is migrated (teeter-api migrate)

    app = FastAPI(title="Teeter API", version=__version__, docs_url="/v1/docs",
                  openapi_url="/v1/openapi.json", redoc_url=None)
    app.state.settings, app.state.db = settings, db
    app.state.storage = make_storage(settings)
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_handler)
    if settings.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins),
                           allow_methods=["GET", "POST", "PUT", "DELETE"],
                           allow_headers=["Authorization", "Content-Type"])

    @app.middleware("http")
    async def headers(request, call_next):
        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        if request.url.path.startswith("/v1/"):
            resp.headers.setdefault("Cache-Control", "no-store")
        return resp

    for router in ROUTERS:
        app.include_router(router)

    site = Path(settings.site_dir) if settings.site_dir else None
    if site and (site / "app" / "index.html").exists():
        app.mount("/", StaticFiles(directory=site, html=True), name="site")
    return app
