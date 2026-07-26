from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.auth.backend import current_active_user
from app.auth.models import User
from app.db.control_plane import get_control_plane_session
from app.scheduled_queries import service
from app.scheduled_queries.schemas import RunNowResult, ScheduledQueryCreate, ScheduledQueryRead, ScheduledQueryUpdate
from app.scheduled_queries.tasks import run_scheduled_query
from app.workspaces import service as workspace_service

router = APIRouter(prefix="/workspaces/{workspace_id}/scheduled-queries", tags=["scheduled-queries"])


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


@router.post("", response_model=ScheduledQueryRead)
async def create_scheduled_query(
    workspace_id: uuid.UUID,
    payload: ScheduledQueryCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> ScheduledQueryRead:
    await _require_editor(session, workspace_id, user.id)
    try:
        row = await service.create_scheduled_query(
            session, workspace_id=workspace_id, created_by=user.id, connection_id=payload.connection_id,
            name=payload.name, sql=payload.sql, cron_expression=payload.cron_expression,
            condition=payload.condition, condition_value=payload.condition_value,
            notify_webhook_url=payload.notify_webhook_url, notify_email=payload.notify_email,
        )
    except service.InvalidScheduledQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ScheduledQueryRead.model_validate(row)


@router.get("", response_model=list[ScheduledQueryRead])
async def list_scheduled_queries(
    workspace_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> list[ScheduledQueryRead]:
    await _require_viewer(session, workspace_id, user.id)
    rows = await service.list_scheduled_queries(session, workspace_id=workspace_id)
    return [ScheduledQueryRead.model_validate(r) for r in rows]


@router.get("/{scheduled_query_id}", response_model=ScheduledQueryRead)
async def get_scheduled_query(
    workspace_id: uuid.UUID,
    scheduled_query_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> ScheduledQueryRead:
    await _require_viewer(session, workspace_id, user.id)
    try:
        row = await service.get_scheduled_query(session, workspace_id=workspace_id, scheduled_query_id=scheduled_query_id)
    except service.ScheduledQueryNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Scheduled query not found") from exc
    return ScheduledQueryRead.model_validate(row)


@router.patch("/{scheduled_query_id}", response_model=ScheduledQueryRead)
async def update_scheduled_query(
    workspace_id: uuid.UUID,
    scheduled_query_id: uuid.UUID,
    payload: ScheduledQueryUpdate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> ScheduledQueryRead:
    await _require_editor(session, workspace_id, user.id)
    fields = payload.model_fields_set
    try:
        row = await service.update_scheduled_query(
            session, workspace_id=workspace_id, scheduled_query_id=scheduled_query_id,
            name=payload.name, sql=payload.sql, cron_expression=payload.cron_expression, condition=payload.condition,
            condition_value=payload.condition_value if "condition_value" in fields else ...,
            notify_webhook_url=payload.notify_webhook_url if "notify_webhook_url" in fields else ...,
            notify_email=payload.notify_email if "notify_email" in fields else ...,
            is_active=payload.is_active,
        )
    except service.ScheduledQueryNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Scheduled query not found") from exc
    except service.InvalidScheduledQueryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ScheduledQueryRead.model_validate(row)


@router.delete("/{scheduled_query_id}", status_code=204, response_model=None)
async def delete_scheduled_query(
    workspace_id: uuid.UUID,
    scheduled_query_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> None:
    await _require_editor(session, workspace_id, user.id)
    try:
        await service.delete_scheduled_query(session, workspace_id=workspace_id, scheduled_query_id=scheduled_query_id)
    except service.ScheduledQueryNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Scheduled query not found") from exc


@router.post("/{scheduled_query_id}/run", response_model=RunNowResult)
async def run_now(
    workspace_id: uuid.UUID,
    scheduled_query_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> RunNowResult:
    """Manual trigger, same precedent as Phase 3d's embeddings-refresh
    endpoint: runs the exact same job body the scheduler would enqueue,
    synchronously, for immediate feedback -- does not touch
    last_enqueued_at (that's only meaningful for the cron-driven path in
    app/scheduler.py), only the reporting fields."""
    await _require_editor(session, workspace_id, user.id)
    try:
        await service.get_scheduled_query(session, workspace_id=workspace_id, scheduled_query_id=scheduled_query_id)
    except service.ScheduledQueryNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Scheduled query not found") from exc
    result = await run_in_threadpool(run_scheduled_query, str(scheduled_query_id))
    return RunNowResult(status=result.get("status", "unknown"), row_count=result.get("row_count"))
