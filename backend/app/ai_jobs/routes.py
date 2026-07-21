from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_jobs import service
from app.ai_jobs.schemas import AiJobCreate, AiJobRead
from app.auth.backend import current_active_user
from app.auth.models import User
from app.db.control_plane import get_control_plane_session
from app.workspaces import service as workspace_service

router = APIRouter(prefix="/workspaces/{workspace_id}/ai/jobs", tags=["ai-jobs"])


async def _require_viewer(session: AsyncSession, workspace_id: uuid.UUID, user_id: uuid.UUID) -> None:
    try:
        await workspace_service.require_role(session, workspace_id=workspace_id, user_id=user_id, min_role="viewer")
    except workspace_service.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Workspace not found") from exc


@router.post("", response_model=AiJobRead)
async def create_job(
    workspace_id: uuid.UUID,
    payload: AiJobCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> AiJobRead:
    # Viewer, not editor+: these AI calls only produce suggestions/text --
    # generate_sql/suggest_tables don't touch a file or run against a real
    # connection here, and explain/repair operate on SQL text the caller
    # already has. Mirrors "viewer can read" from files/connections.
    await _require_viewer(session, workspace_id, user.id)
    try:
        job = await service.create_job(
            session, workspace_id=workspace_id, created_by=user.id, task_type=payload.task_type, input=payload.input
        )
    except service.InvalidTaskTypeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AiJobRead.model_validate(job)


@router.get("/{job_id}", response_model=AiJobRead)
async def get_job(
    workspace_id: uuid.UUID,
    job_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> AiJobRead:
    await _require_viewer(session, workspace_id, user.id)
    try:
        job = await service.get_job(session, workspace_id=workspace_id, job_id=job_id)
    except service.AiJobNotFoundError as exc:
        raise HTTPException(status_code=404, detail="AI job not found") from exc
    return AiJobRead.model_validate(job)
