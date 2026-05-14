"""FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import BACKEND_ROOT, PROJECT_ROOT, get_settings
from app.db.init_metadata import init_metadata_db
from app.db.seed_demo_data import build

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    data_dir = BACKEND_ROOT / "data"
    analytics_db = data_dir / "demo_analytics.db"
    metadata_db = data_dir / "app_metadata.db"
    if not analytics_db.exists() or not metadata_db.exists():
        build()
    init_metadata_db()
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
