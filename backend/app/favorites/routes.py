from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.backend import current_active_user
from app.auth.models import User
from app.db.control_plane import get_control_plane_session
from app.favorites import service
from app.favorites.schemas import FavoriteSummary
from app.workspaces import service as workspace_service

router = APIRouter(prefix="/workspaces/{workspace_id}/favorites", tags=["favorites"])


@router.get("", response_model=list[FavoriteSummary])
async def list_favorites(
    workspace_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> list[FavoriteSummary]:
    try:
        await workspace_service.require_role(session, workspace_id=workspace_id, user_id=user.id, min_role="viewer")
    except workspace_service.NotAMemberError as exc:
        raise HTTPException(status_code=404, detail="Workspace not found") from exc
    rows = await service.list_favorites_for_user(session, workspace_id=workspace_id, user_id=user.id)
    return [FavoriteSummary(**row) for row in rows]
