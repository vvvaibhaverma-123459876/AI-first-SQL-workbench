from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.files.models import File, FileRevision
from app.workspaces.models import AuditLogEntry

# Revisions are throttled, not one-per-keystroke: a snapshot is only taken
# if this long has passed since the file's last revision. Autosave still
# writes `content` on every debounced save; this just bounds how many
# recovery points pile up for a file someone is actively typing in.
MIN_SECONDS_BETWEEN_REVISIONS = 30


class FileNotFoundError(Exception):
    pass


class DuplicateNameError(Exception):
    pass


async def _assert_name_available(
    session: AsyncSession, *, workspace_id: uuid.UUID, parent_id: uuid.UUID | None, name: str, exclude_id: uuid.UUID | None = None
) -> None:
    """The DB's UniqueConstraint on (workspace_id, parent_id, name) does not
    catch duplicate root-level names, because SQL treats every NULL
    parent_id as distinct from every other NULL -- so this is enforced here
    instead, uniformly for root and non-root alike."""
    stmt = select(File.id).where(File.workspace_id == workspace_id, File.name == name)
    stmt = stmt.where(File.parent_id == parent_id) if parent_id is not None else stmt.where(File.parent_id.is_(None))
    if exclude_id is not None:
        stmt = stmt.where(File.id != exclude_id)
    result = await session.execute(stmt)
    if result.scalar_one_or_none() is not None:
        raise DuplicateNameError(f"{name!r} already exists in this folder")


async def create_file(
    session: AsyncSession, *, workspace_id: uuid.UUID, created_by: uuid.UUID, name: str, is_folder: bool, parent_id: uuid.UUID | None, content: str
) -> File:
    await _assert_name_available(session, workspace_id=workspace_id, parent_id=parent_id, name=name)
    file = File(workspace_id=workspace_id, parent_id=parent_id, name=name, is_folder=is_folder, content="" if is_folder else content, created_by=created_by)
    session.add(file)
    await session.flush()
    session.add(AuditLogEntry(workspace_id=workspace_id, user_id=created_by, action="file.created", detail=name))
    await session.commit()
    await session.refresh(file)
    return file


async def list_files(session: AsyncSession, *, workspace_id: uuid.UUID) -> list[File]:
    result = await session.execute(select(File).where(File.workspace_id == workspace_id).order_by(File.is_folder.desc(), File.name))
    return list(result.scalars().all())


async def get_file(session: AsyncSession, *, workspace_id: uuid.UUID, file_id: uuid.UUID) -> File:
    result = await session.execute(select(File).where(File.id == file_id, File.workspace_id == workspace_id))
    file = result.scalar_one_or_none()
    if file is None:
        raise FileNotFoundError(f"file {file_id} not found in workspace {workspace_id}")
    return file


async def _maybe_snapshot_revision(session: AsyncSession, *, file: File, user_id: uuid.UUID) -> None:
    result = await session.execute(
        select(FileRevision.created_at).where(FileRevision.file_id == file.id).order_by(FileRevision.created_at.desc()).limit(1)
    )
    last = result.scalar_one_or_none()
    if last is not None and datetime.utcnow() - last < timedelta(seconds=MIN_SECONDS_BETWEEN_REVISIONS):
        return
    session.add(FileRevision(file_id=file.id, content=file.content, created_by=user_id))


async def update_file(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    file_id: uuid.UUID,
    updated_by: uuid.UUID,
    content: str | None = None,
    name: str | None = None,
    parent_id: uuid.UUID | None | object = ...,  # sentinel: `...` means "not provided", None means "move to root"
) -> File:
    file = await get_file(session, workspace_id=workspace_id, file_id=file_id)

    new_parent_id = file.parent_id if parent_id is ... else parent_id
    new_name = name if name is not None else file.name
    if new_name != file.name or new_parent_id != file.parent_id:
        await _assert_name_available(session, workspace_id=workspace_id, parent_id=new_parent_id, name=new_name, exclude_id=file.id)
        file.name = new_name
        file.parent_id = new_parent_id

    if content is not None and content != file.content and not file.is_folder:
        await _maybe_snapshot_revision(session, file=file, user_id=updated_by)
        file.content = content

    session.add(AuditLogEntry(workspace_id=workspace_id, user_id=updated_by, action="file.updated", detail=file.name))
    await session.commit()
    await session.refresh(file)
    return file


async def delete_file(session: AsyncSession, *, workspace_id: uuid.UUID, file_id: uuid.UUID, deleted_by: uuid.UUID) -> None:
    file = await get_file(session, workspace_id=workspace_id, file_id=file_id)
    all_files = await list_files(session, workspace_id=workspace_id)
    by_parent: dict[uuid.UUID | None, list[File]] = {}
    for f in all_files:
        by_parent.setdefault(f.parent_id, []).append(f)

    # DFS collects every node before its own children are pushed, so in this
    # list a parent always precedes its descendants -- reversed(), every
    # child is deleted before its parent. Neither files.parent_id nor
    # file_revisions.file_id cascades on delete, and Postgres enforces that
    # immediately (unlike aiosqlite, which doesn't enforce FKs by default),
    # so deleting in the wrong order, or leaving revisions behind, 500s on
    # a real deployment even though it looks fine against sqlite tests.
    subtree: list[File] = []
    stack = [file]
    while stack:
        current = stack.pop()
        subtree.append(current)
        stack.extend(by_parent.get(current.id, []))

    from app.favorites.service import delete_favorites_for_resource  # local: avoids a module-level files<->favorites import cycle
    from app.sharing.service import delete_shares_for_resource  # local: avoids a module-level files<->sharing import cycle

    for f in reversed(subtree):
        await session.execute(delete(FileRevision).where(FileRevision.file_id == f.id))
        await delete_shares_for_resource(session, resource_type="file", resource_id=f.id)
        await delete_favorites_for_resource(session, resource_type="file", resource_id=f.id)
        await session.delete(f)
    session.add(AuditLogEntry(workspace_id=workspace_id, user_id=deleted_by, action="file.deleted", detail=file.name))
    await session.commit()


async def list_revisions(session: AsyncSession, *, workspace_id: uuid.UUID, file_id: uuid.UUID) -> list[FileRevision]:
    await get_file(session, workspace_id=workspace_id, file_id=file_id)  # 404s if not in this workspace
    result = await session.execute(select(FileRevision).where(FileRevision.file_id == file_id).order_by(FileRevision.created_at.desc()))
    return list(result.scalars().all())


def _snippet(content: str, query: str, *, context: int = 40) -> str:
    idx = content.lower().find(query.lower())
    if idx == -1:
        return content[:context * 2]
    start = max(0, idx - context)
    end = min(len(content), idx + len(query) + context)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(content) else ""
    return f"{prefix}{content[start:end]}{suffix}"


async def search_files(session: AsyncSession, *, workspace_id: uuid.UUID, query: str) -> list[tuple[File, str]]:
    """Full-text-ish content search. A plain case-insensitive substring scan
    rather than Postgres tsvector/GIN -- deliberately simple for a personal-
    scale workspace; the plan's tsvector suggestion is a reasonable later
    upgrade if file counts ever make this slow, not a Phase 1 requirement."""
    if not query.strip():
        return []
    files = await list_files(session, workspace_id=workspace_id)
    matches = [f for f in files if not f.is_folder and query.lower() in f.content.lower()]
    return [(f, _snippet(f.content, query)) for f in matches]
