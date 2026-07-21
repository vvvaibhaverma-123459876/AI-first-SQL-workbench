"""FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# app.auth.backend (and transitively app.auth.models) MUST import before
# app.api.routes -- fastapi-users-db-sqlalchemy 7.0.0 has an import-order bug
# where touching fastapi_users_db_sqlalchemy.generics (which every model
# module's GUID column type does) before fastapi_users.db's own top-level
# import leaves SQLAlchemyBaseUserTableUUID undefined there (its ImportError
# gets silently swallowed by a bare `except ImportError` upstream). This bit
# app.api.routes specifically once app.assistant.orchestrator started
# importing app.connections.models (Phase 3c, connection-aware AI) ahead of
# auth's own import -- same root cause already documented in alembic/env.py
# and app/worker.py, now also live here. Keep this import first.
from app.auth.backend import auth_backend, fastapi_users
from app.auth.schemas import UserCreate, UserRead, UserUpdate

from app.api.routes import router
from app.core.config import BACKEND_ROOT, PROJECT_ROOT, get_settings
from app.db.control_plane import init_control_plane_db
from app.db.init_metadata import init_metadata_db
from app.db.seed_demo_data import build
from app.ai_jobs.routes import router as ai_jobs_router
from app.connections.routes import router as connections_router
from app.files.routes import router as files_router
from app.workspaces.routes import router as workspaces_router

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    data_dir = BACKEND_ROOT / "data"
    analytics_db = data_dir / "demo_analytics.db"
    metadata_db = data_dir / "app_metadata.db"
    if not analytics_db.exists() or not metadata_db.exists():
        build()
    init_metadata_db()
    # create_all is checkfirst/idempotent — safe against both a fresh SQLite
    # dev file and a fresh Postgres instance. Alembic (backend/alembic/)
    # covers real migrations as the schema evolves across phases.
    await init_control_plane_db()
    yield


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# New product API namespace.
app.include_router(router, prefix=settings.api_prefix)
app.include_router(fastapi_users.get_auth_router(auth_backend), prefix=f"{settings.api_prefix}/auth/jwt", tags=["auth"])
app.include_router(fastapi_users.get_register_router(UserRead, UserCreate), prefix=f"{settings.api_prefix}/auth", tags=["auth"])
app.include_router(fastapi_users.get_users_router(UserRead, UserUpdate), prefix=f"{settings.api_prefix}/users", tags=["users"])
app.include_router(workspaces_router, prefix=settings.api_prefix)
app.include_router(files_router, prefix=settings.api_prefix)
app.include_router(connections_router, prefix=settings.api_prefix)
app.include_router(ai_jobs_router, prefix=settings.api_prefix)

# Backward compatibility for older frontend/tests/scripts that still call root endpoints.
app.include_router(router)


frontend_dist = PROJECT_ROOT / "frontend" / "dist"
if frontend_dist.exists():
    assets_dir = frontend_dist / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_react_app(full_path: str):
        requested_file = frontend_dist / full_path
        if requested_file.exists() and requested_file.is_file():
            return FileResponse(requested_file)
        return FileResponse(frontend_dist / "index.html")
