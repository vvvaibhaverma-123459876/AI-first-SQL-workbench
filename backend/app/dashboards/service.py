from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connections import service as connections_service
from app.dashboards.models import CHART_TYPES, Dashboard, DashboardItem
from app.workspaces.models import AuditLogEntry


class DashboardNotFoundError(Exception):
    pass


class DashboardItemNotFoundError(Exception):
    pass


class DuplicateDashboardNameError(Exception):
    pass


class InvalidDashboardItemError(Exception):
    """Bad chart_type, or SQL that isn't provably read-only. Dashboard tiles
    re-execute unattended on every reload with no live human role check in
    the loop, so -- same posture as scheduled queries -- only read-only SQL
    is ever accepted, regardless of the creator's role."""


async def _assert_valid_item(session: AsyncSession, *, workspace_id: uuid.UUID, connection_id: uuid.UUID, sql: str, chart_type: str) -> None:
    if chart_type not in CHART_TYPES:
        raise InvalidDashboardItemError(f"chart_type must be one of {CHART_TYPES}")
    try:
        connection = await connections_service.get_connection(session, workspace_id=workspace_id, connection_id=connection_id)
    except connections_service.ConnectionNotFoundError as exc:
        raise InvalidDashboardItemError(f"Connection {connection_id} not found in this workspace.") from exc
    if not connections_service.is_read_only_sql(sql, connector_type=connection.connector_type):
        raise InvalidDashboardItemError("Only read-only SELECT/WITH queries can be pinned to a dashboard.")


async def create_dashboard(session: AsyncSession, *, workspace_id: uuid.UUID, created_by: uuid.UUID, name: str) -> Dashboard:
    existing = await session.execute(select(Dashboard.id).where(Dashboard.workspace_id == workspace_id, Dashboard.name == name))
    if existing.scalar_one_or_none() is not None:
        raise DuplicateDashboardNameError(f"{name!r} already exists in this workspace")
    dashboard = Dashboard(workspace_id=workspace_id, name=name, created_by=created_by)
    session.add(dashboard)
    await session.flush()
    session.add(AuditLogEntry(workspace_id=workspace_id, user_id=created_by, action="dashboard.created", detail=name))
    await session.commit()
    await session.refresh(dashboard)
    return dashboard


async def list_dashboards(session: AsyncSession, *, workspace_id: uuid.UUID) -> list[Dashboard]:
    result = await session.execute(select(Dashboard).where(Dashboard.workspace_id == workspace_id).order_by(Dashboard.name))
    return list(result.scalars().all())


async def get_dashboard(session: AsyncSession, *, workspace_id: uuid.UUID, dashboard_id: uuid.UUID) -> Dashboard:
    result = await session.execute(select(Dashboard).where(Dashboard.id == dashboard_id, Dashboard.workspace_id == workspace_id))
    dashboard = result.scalar_one_or_none()
    if dashboard is None:
        raise DashboardNotFoundError(f"dashboard {dashboard_id} not found in workspace {workspace_id}")
    return dashboard


async def delete_dashboard(session: AsyncSession, *, workspace_id: uuid.UUID, dashboard_id: uuid.UUID, deleted_by: uuid.UUID) -> None:
    dashboard = await get_dashboard(session, workspace_id=workspace_id, dashboard_id=dashboard_id)
    await session.execute(delete(DashboardItem).where(DashboardItem.dashboard_id == dashboard.id))
    await session.delete(dashboard)
    session.add(AuditLogEntry(workspace_id=workspace_id, user_id=deleted_by, action="dashboard.deleted", detail=dashboard.name))
    await session.commit()


async def list_items(session: AsyncSession, *, dashboard_id: uuid.UUID) -> list[DashboardItem]:
    result = await session.execute(select(DashboardItem).where(DashboardItem.dashboard_id == dashboard_id).order_by(DashboardItem.sort_order))
    return list(result.scalars().all())


async def add_item(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    dashboard_id: uuid.UUID,
    created_by: uuid.UUID,
    connection_id: uuid.UUID,
    title: str,
    sql: str,
    chart_type: str,
    x_field: str | None,
    y_fields: list[str],
    width: int,
) -> DashboardItem:
    await get_dashboard(session, workspace_id=workspace_id, dashboard_id=dashboard_id)  # 404s if not in this workspace
    await _assert_valid_item(session, workspace_id=workspace_id, connection_id=connection_id, sql=sql, chart_type=chart_type)

    existing = await list_items(session, dashboard_id=dashboard_id)
    next_order = (max((i.sort_order for i in existing), default=-1)) + 1
    item = DashboardItem(
        dashboard_id=dashboard_id, connection_id=connection_id, title=title, sql=sql, chart_type=chart_type,
        x_field=x_field, y_fields=y_fields, width=max(1, min(3, width)), sort_order=next_order, created_by=created_by,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


async def _get_item(session: AsyncSession, *, dashboard_id: uuid.UUID, item_id: uuid.UUID) -> DashboardItem:
    result = await session.execute(select(DashboardItem).where(DashboardItem.id == item_id, DashboardItem.dashboard_id == dashboard_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise DashboardItemNotFoundError(f"item {item_id} not found on dashboard {dashboard_id}")
    return item


async def update_item(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    dashboard_id: uuid.UUID,
    item_id: uuid.UUID,
    title: str | None,
    sql: str | None,
    chart_type: str | None,
    x_field: str | None | object,
    y_fields: list[str] | None,
    width: int | None,
    sort_order: int | None,
) -> DashboardItem:
    await get_dashboard(session, workspace_id=workspace_id, dashboard_id=dashboard_id)
    item = await _get_item(session, dashboard_id=dashboard_id, item_id=item_id)

    new_sql = sql if sql is not None else item.sql
    new_chart_type = chart_type if chart_type is not None else item.chart_type
    if sql is not None or chart_type is not None:
        await _assert_valid_item(session, workspace_id=workspace_id, connection_id=item.connection_id, sql=new_sql, chart_type=new_chart_type)

    if title is not None:
        item.title = title
    item.sql = new_sql
    item.chart_type = new_chart_type
    if x_field is not ...:
        item.x_field = x_field
    if y_fields is not None:
        item.y_fields = y_fields
    if width is not None:
        item.width = max(1, min(3, width))
    if sort_order is not None:
        item.sort_order = sort_order

    await session.commit()
    await session.refresh(item)
    return item


async def delete_item(session: AsyncSession, *, workspace_id: uuid.UUID, dashboard_id: uuid.UUID, item_id: uuid.UUID) -> None:
    await get_dashboard(session, workspace_id=workspace_id, dashboard_id=dashboard_id)
    item = await _get_item(session, dashboard_id=dashboard_id, item_id=item_id)
    await session.delete(item)
    await session.commit()
