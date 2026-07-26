"""Sync counterpart to control_plane.py, for the RQ worker process.

RQ jobs run synchronously (one job function, start to finish, no event
loop) -- reusing the async control-plane session from control_plane.py
would mean either wrapping every job body in asyncio.run() as a retrofit,
or giving the worker its own async runtime for no benefit. Since
ControlPlaneBase's models are plain SQLAlchemy declarative models with no
async-specific behavior, they work identically against a sync engine --
this module just derives one from the same CONTROL_PLANE_DB_URL by
swapping the driver.
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def _sync_url(async_url: str) -> str:
    if async_url.startswith("postgresql+asyncpg://"):
        return async_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    if async_url.startswith("sqlite+aiosqlite://"):
        return async_url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    raise ValueError(f"Unrecognized async control-plane URL scheme: {async_url!r}")


_sync_engine = create_engine(_sync_url(get_settings().control_plane_db_url), future=True)
ControlPlaneSyncSessionLocal = sessionmaker(bind=_sync_engine, autoflush=False, autocommit=False, future=True)


def get_sync_session() -> Session:
    return ControlPlaneSyncSessionLocal()
