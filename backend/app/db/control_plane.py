"""Async control-plane database: users, workspaces, memberships, audit log.

Kept separate from the existing (sync) analytics_engine/metadata_engine —
this is the app's own multi-user state, not the user's connected data
sources. fastapi-users' SQLAlchemy adapter requires an async session, which
is the main reason this engine is async while the rest of the codebase is
still sync (that migration, if it happens, is a later phase's concern, not
Phase 0's).
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

control_plane_engine = create_async_engine(settings.control_plane_db_url, future=True)
ControlPlaneSessionLocal = async_sessionmaker(control_plane_engine, expire_on_commit=False)


class ControlPlaneBase(DeclarativeBase):
    pass


async def get_control_plane_session() -> AsyncGenerator[AsyncSession, None]:
    async with ControlPlaneSessionLocal() as session:
        yield session


async def init_control_plane_db() -> None:
    """Dev/test convenience: create tables directly from the ORM models.

    Real deployments use Alembic (backend/alembic/) instead — see
    alembic/versions/0001_initial_control_plane.py for the same schema
    expressed as a migration.
    """
    async with control_plane_engine.begin() as conn:
        await conn.run_sync(ControlPlaneBase.metadata.create_all)
