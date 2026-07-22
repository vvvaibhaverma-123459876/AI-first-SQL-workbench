from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dashboards.models import Dashboard
from app.favorites.models import Favorite
from app.files.models import File


async def add_favorite(session: AsyncSession, *, workspace_id: uuid.UUID, resource_type: str, resource_id: uuid.UUID, user_id: uuid.UUID) -> Favorite:
    existing = await session.execute(
        select(Favorite).where(Favorite.user_id == user_id, Favorite.resource_type == resource_type, Favorite.resource_id == resource_id)
    )
    row = existing.scalar_one_or_none()
    if row is not None:
        return row  # idempotent: favoriting an already-favorited resource is a no-op, not an error
    row = Favorite(workspace_id=workspace_id, user_id=user_id, resource_type=resource_type, resource_id=resource_id)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def remove_favorite(session: AsyncSession, *, resource_type: str, resource_id: uuid.UUID, user_id: uuid.UUID) -> None:
    result = await session.execute(
        select(Favorite).where(Favorite.user_id == user_id, Favorite.resource_type == resource_type, Favorite.resource_id == resource_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return  # idempotent: unfavoriting something not favorited is a no-op, not an error
    await session.delete(row)
    await session.commit()


async def delete_favorites_for_resource(session: AsyncSession, *, resource_type: str, resource_id: uuid.UUID) -> None:
    """Called from files/service.py's delete_file and dashboards/service.py's
    delete_dashboard, same site and same reasoning as
    app.sharing.service.delete_shares_for_resource -- resource_id is
    polymorphic so there is no DB-level FK cascade to lean on."""
    result = await session.execute(select(Favorite).where(Favorite.resource_type == resource_type, Favorite.resource_id == resource_id))
    for row in result.scalars().all():
        await session.delete(row)


async def list_favorites_for_user(session: AsyncSession, *, workspace_id: uuid.UUID, user_id: uuid.UUID) -> list[dict]:
    result = await session.execute(
        select(Favorite)
        .where(Favorite.workspace_id == workspace_id, Favorite.user_id == user_id)
        .order_by(Favorite.created_at.desc())
    )
    favorites = list(result.scalars().all())
    if not favorites:
        return []

    file_ids = [f.resource_id for f in favorites if f.resource_type == "file"]
    dashboard_ids = [f.resource_id for f in favorites if f.resource_type == "dashboard"]

    files_by_id: dict[uuid.UUID, File] = {}
    if file_ids:
        rows = await session.execute(select(File).where(File.id.in_(file_ids)))
        files_by_id = {f.id: f for f in rows.scalars().all()}

    dashboards_by_id: dict[uuid.UUID, Dashboard] = {}
    if dashboard_ids:
        rows = await session.execute(select(Dashboard).where(Dashboard.id.in_(dashboard_ids)))
        dashboards_by_id = {d.id: d for d in rows.scalars().all()}

    out: list[dict] = []
    for fav in favorites:
        resource = files_by_id.get(fav.resource_id) if fav.resource_type == "file" else dashboards_by_id.get(fav.resource_id)
        if resource is None:
            continue  # defensive: same orphan-tolerance as list_shared_with_me, in case a cascade site is ever missed
        out.append(
            {
                "favorite_id": fav.id,
                "resource_type": fav.resource_type,
                "resource_id": fav.resource_id,
                "resource_name": resource.name,
                "created_at": fav.created_at,
            }
        )
    return out
