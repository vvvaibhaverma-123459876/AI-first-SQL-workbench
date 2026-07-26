from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.workspaces.models import AuditLogEntry, Workspace, WorkspaceMembership

ROLE_RANK = {"viewer": 0, "editor": 1, "owner": 2}


class NotAMemberError(Exception):
    pass


class InsufficientRoleError(Exception):
    pass


async def create_workspace(session: AsyncSession, *, name: str, owner_id: uuid.UUID) -> Workspace:
    workspace = Workspace(name=name, created_by=owner_id)
    session.add(workspace)
    await session.flush()
    session.add(WorkspaceMembership(workspace_id=workspace.id, user_id=owner_id, role="owner"))
    session.add(AuditLogEntry(workspace_id=workspace.id, user_id=owner_id, action="workspace.created", detail=name))
    await session.commit()
    await session.refresh(workspace)
    return workspace


async def list_workspaces_for_user(session: AsyncSession, *, user_id: uuid.UUID) -> list[tuple[Workspace, str]]:
    result = await session.execute(
        select(Workspace, WorkspaceMembership.role)
        .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id)
        .where(WorkspaceMembership.user_id == user_id)
        .order_by(Workspace.created_at)
    )
    return [(row[0], row[1]) for row in result.all()]


async def get_membership(session: AsyncSession, *, workspace_id: uuid.UUID, user_id: uuid.UUID) -> WorkspaceMembership | None:
    result = await session.execute(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def require_role(session: AsyncSession, *, workspace_id: uuid.UUID, user_id: uuid.UUID, min_role: str) -> WorkspaceMembership:
    """Raises NotAMemberError / InsufficientRoleError rather than returning a
    falsy value — callers translate those into HTTP 404/403 at the route
    boundary, keeping this service layer transport-agnostic."""
    membership = await get_membership(session, workspace_id=workspace_id, user_id=user_id)
    if membership is None:
        raise NotAMemberError(f"user {user_id} is not a member of workspace {workspace_id}")
    if ROLE_RANK[membership.role] < ROLE_RANK[min_role]:
        raise InsufficientRoleError(f"role {membership.role!r} does not meet required role {min_role!r}")
    return membership
