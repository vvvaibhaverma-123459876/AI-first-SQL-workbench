"""Async control-plane database: users, workspaces, memberships, audit log.

Kept separate from the existing (sync) analytics_engine/metadata_engine —
this is the app's own multi-user state, not the user's connected data
sources. fastapi-users' SQLAlchemy adapter requires an async session, which
is the main reason this engine is async while the rest of the codebase is
still sync (that migration, if it happens, is a later phase's concern, not
Phase 0's).
"""
from __future__ import annotations

import sys
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

settings = get_settings()

# This engine is a module-level singleton (created once at import time), and
# asyncpg connections are bound to the event loop that created them. The test
# suite spins up a fresh TestClient (and therefore a fresh event loop) per
# test module -- with the default pooled engine, a connection opened under
# one module's loop gets handed to a later module's different loop and
# asyncpg raises "Future attached to a different loop". That's a test-harness
# problem (module-scoped TestClients each minting their own loop over one
# shared engine), not a production one -- production runs a single event
# loop where pooling is correct and wanted, so forcing NullPool unconditionally
# would silently trade away real connection pooling on every request just to
# satisfy the test fixtures. Gate it to test runs only ("pytest" lands in
# sys.modules as soon as the pytest process starts, well before this module
# is imported during collection); production keeps its default pool.
_engine_kwargs: dict[str, object] = {"future": True}
if "pytest" in sys.modules:
    _engine_kwargs["poolclass"] = NullPool
control_plane_engine = create_async_engine(settings.control_plane_db_url, **_engine_kwargs)
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
