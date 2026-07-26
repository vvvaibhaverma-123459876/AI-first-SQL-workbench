from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.backend import current_active_user
from app.auth.models import User
from app.dashboards import service
from app.dashboards.schemas import DashboardCreate, DashboardDetail, DashboardItemCreate, DashboardItemRead, DashboardItemUpdate, DashboardRead
from app.db.control_plane import get_control_plane_session
from app.workspaces import service as workspace_service

router = APIRouter(prefix="/workspaces/{workspace_id}/dashboards", tags=["dashboards"])


async def _require_viewer(session: AsyncSession, workspace_id: uuid.UUID, user_id: uuid.UUID) -> None:
    try:
        await workspace_service.require_role(session, workspace_id=workspace_id, user_id=user_id, min_role="viewer")
    except workspace_service.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Workspace not found") from exc


async def _require_editor(session: AsyncSession, workspace_id: uuid.UUID, user_id: uuid.UUID) -> None:
    try:
        await workspace_service.require_role(session, workspace_id=workspace_id, user_id=user_id, min_role="editor")
    except workspace_service.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Workspace not found") from exc
    except workspace_service.InsufficientRoleError as exc:
        raise HTTPException(status_code=403, detail="Editor or owner role required") from exc


@router.post("", response_model=DashboardRead)
async def create_dashboard(
    workspace_id: uuid.UUID,
    payload: DashboardCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> DashboardRead:
    await _require_editor(session, workspace_id, user.id)
    try:
        dashboard = await service.create_dashboard(session, workspace_id=workspace_id, created_by=user.id, name=payload.name)
    except service.DuplicateDashboardNameError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return DashboardRead.model_validate(dashboard)


@router.get("", response_model=list[DashboardRead])
async def list_dashboards(
    workspace_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> list[DashboardRead]:
    await _require_viewer(session, workspace_id, user.id)
    dashboards = await service.list_dashboards(session, workspace_id=workspace_id)
    return [DashboardRead.model_validate(d) for d in dashboards]


@router.get("/{dashboard_id}", response_model=DashboardDetail)
async def get_dashboard(
    workspace_id: uuid.UUID,
    dashboard_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> DashboardDetail:
    await _require_viewer(session, workspace_id, user.id)
    try:
        dashboard = await service.get_dashboard(session, workspace_id=workspace_id, dashboard_id=dashboard_id)
    except service.DashboardNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Dashboard not found") from exc
    items = await service.list_items(session, dashboard_id=dashboard.id)
    return DashboardDetail(**DashboardRead.model_validate(dashboard).model_dump(), items=[DashboardItemRead.model_validate(i) for i in items])


@router.delete("/{dashboard_id}", status_code=204, response_model=None)
async def delete_dashboard(
    workspace_id: uuid.UUID,
    dashboard_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> None:
    await _require_editor(session, workspace_id, user.id)
    try:
        await service.delete_dashboard(session, workspace_id=workspace_id, dashboard_id=dashboard_id, deleted_by=user.id)
    except service.DashboardNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Dashboard not found") from exc


@router.post("/{dashboard_id}/items", response_model=DashboardItemRead)
async def add_item(
    workspace_id: uuid.UUID,
    dashboard_id: uuid.UUID,
    payload: DashboardItemCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> DashboardItemRead:
    await _require_editor(session, workspace_id, user.id)
    try:
        item = await service.add_item(
            session, workspace_id=workspace_id, dashboard_id=dashboard_id, created_by=user.id,
            connection_id=payload.connection_id, title=payload.title, sql=payload.sql,
            chart_type=payload.chart_type, x_field=payload.x_field, y_fields=payload.y_fields, width=payload.width,
        )
    except service.DashboardNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Dashboard not found") from exc
    except service.InvalidDashboardItemError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DashboardItemRead.model_validate(item)


@router.patch("/{dashboard_id}/items/{item_id}", response_model=DashboardItemRead)
async def update_item(
    workspace_id: uuid.UUID,
    dashboard_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: DashboardItemUpdate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> DashboardItemRead:
    await _require_editor(session, workspace_id, user.id)
    try:
        item = await service.update_item(
            session, workspace_id=workspace_id, dashboard_id=dashboard_id, item_id=item_id,
            title=payload.title, sql=payload.sql, chart_type=payload.chart_type,
            x_field=payload.x_field if "x_field" in payload.model_fields_set else ...,
            y_fields=payload.y_fields, width=payload.width, sort_order=payload.sort_order,
        )
    except service.DashboardNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Dashboard not found") from exc
    except service.DashboardItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Dashboard item not found") from exc
    except service.InvalidDashboardItemError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DashboardItemRead.model_validate(item)


@router.delete("/{dashboard_id}/items/{item_id}", status_code=204, response_model=None)
async def delete_item(
    workspace_id: uuid.UUID,
    dashboard_id: uuid.UUID,
    item_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> None:
    await _require_editor(session, workspace_id, user.id)
    try:
        await service.delete_item(session, workspace_id=workspace_id, dashboard_id=dashboard_id, item_id=item_id)
    except service.DashboardNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Dashboard not found") from exc
    except service.DashboardItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Dashboard item not found") from exc
