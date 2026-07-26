from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.backend import current_active_user
from app.auth.models import User
from app.db.control_plane import get_control_plane_session
from app.workspaces import service
from app.workspaces.schemas import WorkspaceCreate, WorkspaceRead

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.post("", response_model=WorkspaceRead)
async def create_workspace(
    payload: WorkspaceCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> WorkspaceRead:
    workspace = await service.create_workspace(session, name=payload.name, owner_id=user.id)
    return WorkspaceRead(id=workspace.id, name=workspace.name, role="owner", created_at=workspace.created_at)


@router.get("", response_model=list[WorkspaceRead])
async def list_workspaces(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> list[WorkspaceRead]:
    rows = await service.list_workspaces_for_user(session, user_id=user.id)
    return [WorkspaceRead(id=w.id, name=w.name, role=role, created_at=w.created_at) for w, role in rows]


@router.get("/{workspace_id}", response_model=WorkspaceRead)
async def get_workspace(
    workspace_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> WorkspaceRead:
    try:
        membership = await service.require_role(session, workspace_id=workspace_id, user_id=user.id, min_role="viewer")
    except service.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Workspace not found") from exc
    workspace = membership.workspace_id
    rows = await service.list_workspaces_for_user(session, user_id=user.id)
    for w, role in rows:
        if w.id == workspace:
            return WorkspaceRead(id=w.id, name=w.name, role=role, created_at=w.created_at)
    raise HTTPException(status_code=404, detail="Workspace not found")
