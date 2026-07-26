"""Top-level, non-workspace-scoped routes for READING a shared resource.
Deliberately separate from files/routes.py and dashboards/routes.py: these
endpoints check ONLY sharing.service.get_share_for_resource -- never
workspace membership -- so a share grant is what's proven to matter, and
every prior phase's workspace-scoped route/test is completely untouched
by this module's existence.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.auth.backend import current_active_user
from app.auth.models import User
from app.connections import service as connections_service
from app.connections.models import DataConnection
from app.dashboards.models import Dashboard, DashboardItem
from app.db.control_plane import get_control_plane_session
from app.files import service as files_service
from app.files.models import File
from app.sharing import service as sharing_service
from app.sharing.schemas import SharedDashboardItemRead, SharedDashboardRead, SharedDashboardTileResult, SharedFileRead, SharedFileUpdate, SharedResourceSummary

router = APIRouter(tags=["sharing"])


@router.get("/shared-with-me", response_model=list[SharedResourceSummary])
async def shared_with_me(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> list[SharedResourceSummary]:
    rows = await sharing_service.list_shared_with_me(session, user_id=user.id)
    return [SharedResourceSummary(**row) for row in rows]


@router.get("/shared/files/{file_id}", response_model=SharedFileRead)
async def get_shared_file(
    file_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> SharedFileRead:
    share = await sharing_service.get_share_for_resource(session, resource_type="file", resource_id=file_id, user_id=user.id)
    if share is None:
        raise HTTPException(status_code=404, detail="File not found")
    result = await session.execute(select(File).where(File.id == file_id))
    file = result.scalar_one_or_none()
    if file is None:
        raise HTTPException(status_code=404, detail="File not found")
    return SharedFileRead(id=file.id, name=file.name, content=file.content, role=share.role)


@router.patch("/shared/files/{file_id}", response_model=SharedFileRead)
async def update_shared_file(
    file_id: uuid.UUID,
    payload: SharedFileUpdate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> SharedFileRead:
    share = await sharing_service.get_share_for_resource(session, resource_type="file", resource_id=file_id, user_id=user.id)
    if share is None:
        raise HTTPException(status_code=404, detail="File not found")
    if share.role != "editor":
        raise HTTPException(status_code=403, detail="This file was shared with view-only access")
    try:
        file = await files_service.update_file(session, workspace_id=share.workspace_id, file_id=file_id, updated_by=user.id, content=payload.content)
    except files_service.FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="File not found") from exc
    return SharedFileRead(id=file.id, name=file.name, content=file.content, role=share.role)


@router.get("/shared/dashboards/{dashboard_id}", response_model=SharedDashboardRead)
async def get_shared_dashboard(
    dashboard_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> SharedDashboardRead:
    share = await sharing_service.get_share_for_resource(session, resource_type="dashboard", resource_id=dashboard_id, user_id=user.id)
    if share is None:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    result = await session.execute(select(Dashboard).where(Dashboard.id == dashboard_id))
    dashboard = result.scalar_one_or_none()
    if dashboard is None:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    items_result = await session.execute(select(DashboardItem).where(DashboardItem.dashboard_id == dashboard_id).order_by(DashboardItem.sort_order))
    items = items_result.scalars().all()
    return SharedDashboardRead(
        id=dashboard.id,
        name=dashboard.name,
        role=share.role,
        items=[
            SharedDashboardItemRead(
                id=i.id, title=i.title, sql=i.sql, chart_type=i.chart_type, x_field=i.x_field, y_fields=i.y_fields, width=i.width, sort_order=i.sort_order
            )
            for i in items
        ],
    )


def _run_tile_sync(connection: DataConnection, sql: str) -> SharedDashboardTileResult:
    result = connections_service.run_query_sync(connection, sql)
    return SharedDashboardTileResult(columns=result.columns, rows=result.rows, row_count=result.row_count, truncated=result.truncated)


@router.post("/shared/dashboards/{dashboard_id}/items/{item_id}/run", response_model=SharedDashboardTileResult)
async def run_shared_dashboard_tile(
    dashboard_id: uuid.UUID,
    item_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> SharedDashboardTileResult:
    """The only route that lets a non-member's browser pull real
    connection data -- so it re-derives everything from scratch rather
    than trusting the client: (1) a share grant on dashboard_id, (2) the
    item actually belongs to that SAME dashboard_id (not just any item_id
    in the database -- the IDOR this endpoint exists to prevent), and (3)
    the item's stored SQL is STILL provably read-only at execution time,
    same "never trust stored SQL without re-checking" posture as Phase 4b's
    scheduled-query execution path."""
    share = await sharing_service.get_share_for_resource(session, resource_type="dashboard", resource_id=dashboard_id, user_id=user.id)
    if share is None:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    item_result = await session.execute(select(DashboardItem).where(DashboardItem.id == item_id, DashboardItem.dashboard_id == dashboard_id))
    item = item_result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Dashboard item not found")

    connection_result = await session.execute(select(DataConnection).where(DataConnection.id == item.connection_id))
    connection = connection_result.scalar_one_or_none()
    if connection is None:
        raise HTTPException(status_code=404, detail="Connection no longer exists")

    if not connections_service.is_read_only_sql(item.sql, connector_type=connection.connector_type):
        raise HTTPException(status_code=400, detail="This tile's SQL is no longer provably read-only")

    try:
        return await run_in_threadpool(_run_tile_sync, connection, item.sql)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Query failed: {exc}") from exc
