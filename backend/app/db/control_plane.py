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
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

settings = get_settings()

# NullPool, not the default pooled engine -- asyncpg connections are bound
# to the event loop that created them. This engine is a module-level
# singleton (created once at import time), but the test suite spins up a
# fresh TestClient (and therefore a fresh event loop) per test module --
# with connection pooling, a connection opened under one module's loop gets
# handed to a later module's different loop and asyncpg raises "Future
# attached to a different loop". NullPool opens a fresh physical connection
# per checkout instead of reusing one across calls, which sidesteps this
# entirely. Fine for this control plane's query volume; a real
# high-throughput deployment would front Postgres with something like
# PgBouncer rather than reintroduce in-process pooling here.
control_plane_engine = create_async_engine(settings.control_plane_db_url, future=True, poolclass=NullPool)
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
