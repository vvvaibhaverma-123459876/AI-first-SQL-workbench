from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.dashboards.models import Dashboard
from app.files.models import File
from app.sharing.models import SHARE_ROLES, ResourceShare
from app.workspaces.models import AuditLogEntry


class ShareTargetUserNotFoundError(Exception):
    """No account exists with the given email. Additive external grants
    require an existing account -- there is no invite-by-email/signup flow
    in this project (deliberately out of scope, see PR description)."""


class InvalidShareRoleError(Exception):
    pass


class ShareNotFoundError(Exception):
    pass


async def _resolve_user_by_email(session: AsyncSession, email: str) -> User:
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        raise ShareTargetUserNotFoundError(f"No account exists with email {email!r}")
    return user


async def create_share(
    session: AsyncSession, *, workspace_id: uuid.UUID, resource_type: str, resource_id: uuid.UUID, shared_by: uuid.UUID, email: str, role: str
) -> ResourceShare:
    if role not in SHARE_ROLES:
        raise InvalidShareRoleError(f"role must be one of {SHARE_ROLES}")
    if resource_type == "dashboard" and role != "viewer":
        # Editing someone else's dashboard tiles (which reference connections
        # the sharee has no other access to) is a real feature this phase
        # doesn't build -- restricting to viewer here keeps the surface
        # honest rather than accepting a role that silently does nothing.
        raise InvalidShareRoleError("dashboards can only be shared as 'viewer'")
    target_user = await _resolve_user_by_email(session, email)

    existing = await session.execute(
        select(ResourceShare).where(
            ResourceShare.resource_type == resource_type,
            ResourceShare.resource_id == resource_id,
            ResourceShare.shared_with_user_id == target_user.id,
        )
    )
    row = existing.scalar_one_or_none()
    if row is not None:
        row.role = role  # re-sharing updates the role rather than erroring or duplicating
    else:
        row = ResourceShare(
            workspace_id=workspace_id, resource_type=resource_type, resource_id=resource_id,
            shared_with_user_id=target_user.id, role=role, created_by=shared_by,
        )
        session.add(row)
    await session.flush()
    session.add(AuditLogEntry(workspace_id=workspace_id, user_id=shared_by, action=f"{resource_type}.shared", detail=f"{email} ({role})"))
    await session.commit()
    await session.refresh(row)
    return row


async def list_shares_for_resource(session: AsyncSession, *, resource_type: str, resource_id: uuid.UUID) -> list[tuple[ResourceShare, str]]:
    result = await session.execute(
        select(ResourceShare, User.email)
        .join(User, User.id == ResourceShare.shared_with_user_id)
        .where(ResourceShare.resource_type == resource_type, ResourceShare.resource_id == resource_id)
        .order_by(ResourceShare.created_at)
    )
    return [(row[0], row[1]) for row in result.all()]


async def revoke_share(session: AsyncSession, *, resource_type: str, resource_id: uuid.UUID, share_id: uuid.UUID) -> None:
    result = await session.execute(
        select(ResourceShare).where(ResourceShare.id == share_id, ResourceShare.resource_type == resource_type, ResourceShare.resource_id == resource_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise ShareNotFoundError(f"share {share_id} not found for {resource_type} {resource_id}")
    await session.delete(row)
    await session.commit()


async def get_share_for_resource(session: AsyncSession, *, resource_type: str, resource_id: uuid.UUID, user_id: uuid.UUID) -> ResourceShare | None:
    """The actual authorization check used by app/sharing/routes.py's
    top-level /shared/... endpoints -- deliberately the ONLY thing those
    routes check (no workspace-membership fallback), so a share grant is
    what's proven to matter, not latent workspace access."""
    result = await session.execute(
        select(ResourceShare).where(ResourceShare.resource_type == resource_type, ResourceShare.resource_id == resource_id, ResourceShare.shared_with_user_id == user_id)
    )
    return result.scalar_one_or_none()


async def delete_shares_for_resource(session: AsyncSession, *, resource_type: str, resource_id: uuid.UUID) -> None:
    """Called from files/service.py's delete_file and dashboards/service.py's
    delete_dashboard, in the SAME transaction as the resource delete --
    resource_id is polymorphic so there is no DB-level FK cascade to lean
    on here, unlike FileRevision's real foreign key to files.id."""
    result = await session.execute(select(ResourceShare).where(ResourceShare.resource_type == resource_type, ResourceShare.resource_id == resource_id))
    for row in result.scalars().all():
        await session.delete(row)


async def list_shared_with_me(session: AsyncSession, *, user_id: uuid.UUID) -> list[dict]:
    """Resolves each share to enough detail to render a "Shared with me"
    list -- resource_id is polymorphic, so this can't be a single JOIN;
    it looks up File or Dashboard rows separately per resource_type and
    silently drops any share whose target resource no longer exists
    (the defensive fallback for a cascade-delete that was somehow missed,
    degrading to a hidden row rather than a 500)."""
    result = await session.execute(select(ResourceShare).where(ResourceShare.shared_with_user_id == user_id).order_by(ResourceShare.created_at.desc()))
    shares = list(result.scalars().all())
    if not shares:
        return []

    file_ids = [s.resource_id for s in shares if s.resource_type == "file"]
    dashboard_ids = [s.resource_id for s in shares if s.resource_type == "dashboard"]

    files_by_id: dict[uuid.UUID, File] = {}
    if file_ids:
        rows = await session.execute(select(File).where(File.id.in_(file_ids)))
        files_by_id = {f.id: f for f in rows.scalars().all()}

    dashboards_by_id: dict[uuid.UUID, Dashboard] = {}
    if dashboard_ids:
        rows = await session.execute(select(Dashboard).where(Dashboard.id.in_(dashboard_ids)))
        dashboards_by_id = {d.id: d for d in rows.scalars().all()}

    out: list[dict] = []
    for share in shares:
        resource = files_by_id.get(share.resource_id) if share.resource_type == "file" else dashboards_by_id.get(share.resource_id)
        if resource is None:
            continue
        out.append(
            {
                "share_id": share.id,
                "resource_type": share.resource_type,
                "resource_id": share.resource_id,
                "resource_name": resource.name,
                "workspace_id": share.workspace_id,
                "role": share.role,
                "created_at": share.created_at,
            }
        )
    return out
