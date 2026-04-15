"""FastAPI application entrypoint."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.core.config import get_settings
from pathlib import Path
from app.db.init_metadata import init_metadata_db
from app.db.seed_demo_data import build

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    data_dir = Path(__file__).resolve().parents[1] / "data"
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
app.include_router(router)
