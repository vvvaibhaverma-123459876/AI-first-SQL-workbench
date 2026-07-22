from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.backend import current_active_user
from app.auth.models import User
from app.db.control_plane import get_control_plane_session
from app.favorites import service as favorites_service
from app.favorites.schemas import FavoriteRead
from app.files import service
from app.files.schemas import FileCreate, FileDetail, FileNode, FileRevisionRead, FileSearchResult, FileUpdate
from app.sharing import service as sharing_service
from app.sharing.schemas import ShareCreate, ShareRead
from app.workspaces import service as workspace_service

router = APIRouter(prefix="/workspaces/{workspace_id}/files", tags=["files"])


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


@router.get("", response_model=list[FileNode])
async def list_files(
    workspace_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> list[FileNode]:
    await _require_viewer(session, workspace_id, user.id)
    files = await service.list_files(session, workspace_id=workspace_id)
    return [FileNode.model_validate(f) for f in files]


@router.post("", response_model=FileDetail)
async def create_file(
    workspace_id: uuid.UUID,
    payload: FileCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> FileDetail:
    await _require_editor(session, workspace_id, user.id)
    try:
        file = await service.create_file(
            session, workspace_id=workspace_id, created_by=user.id, name=payload.name,
            is_folder=payload.is_folder, parent_id=payload.parent_id, content=payload.content,
        )
    except service.DuplicateNameError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return FileDetail.model_validate(file)


@router.get("/search", response_model=list[FileSearchResult])
async def search_files(
    workspace_id: uuid.UUID,
    q: str,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> list[FileSearchResult]:
    await _require_viewer(session, workspace_id, user.id)
    results = await service.search_files(session, workspace_id=workspace_id, query=q)
    return [FileSearchResult(file_id=f.id, name=f.name, snippet=snippet) for f, snippet in results]


@router.get("/{file_id}", response_model=FileDetail)
async def get_file(
    workspace_id: uuid.UUID,
    file_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> FileDetail:
    await _require_viewer(session, workspace_id, user.id)
    try:
        file = await service.get_file(session, workspace_id=workspace_id, file_id=file_id)
    except service.FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="File not found") from exc
    return FileDetail.model_validate(file)


@router.patch("/{file_id}", response_model=FileDetail)
async def update_file(
    workspace_id: uuid.UUID,
    file_id: uuid.UUID,
    payload: FileUpdate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> FileDetail:
    await _require_editor(session, workspace_id, user.id)
    try:
        file = await service.update_file(
            session, workspace_id=workspace_id, file_id=file_id, updated_by=user.id,
            content=payload.content, name=payload.name,
            parent_id=payload.parent_id if "parent_id" in payload.model_fields_set else ...,
        )
    except service.FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="File not found") from exc
    except service.DuplicateNameError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return FileDetail.model_validate(file)


@router.delete("/{file_id}", status_code=204, response_model=None)
async def delete_file(
    workspace_id: uuid.UUID,
    file_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> None:
    await _require_editor(session, workspace_id, user.id)
    try:
        await service.delete_file(session, workspace_id=workspace_id, file_id=file_id, deleted_by=user.id)
    except service.FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="File not found") from exc


@router.get("/{file_id}/revisions", response_model=list[FileRevisionRead])
async def list_revisions(
    workspace_id: uuid.UUID,
    file_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> list[FileRevisionRead]:
    await _require_viewer(session, workspace_id, user.id)
    try:
        revisions = await service.list_revisions(session, workspace_id=workspace_id, file_id=file_id)
    except service.FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="File not found") from exc
    return [FileRevisionRead.model_validate(r) for r in revisions]


@router.post("/{file_id}/shares", response_model=ShareRead)
async def create_share(
    workspace_id: uuid.UUID,
    file_id: uuid.UUID,
    payload: ShareCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> ShareRead:
    # editor+ to share: a deliberate call, not owner-only -- sharing is a
    # form of write to the resource's visibility, the same bar as editing
    # its content, not a workspace-administration action.
    await _require_editor(session, workspace_id, user.id)
    try:
        await service.get_file(session, workspace_id=workspace_id, file_id=file_id)
    except service.FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="File not found") from exc
    try:
        share = await sharing_service.create_share(
            session, workspace_id=workspace_id, resource_type="file", resource_id=file_id, shared_by=user.id, email=payload.email, role=payload.role
        )
    except sharing_service.ShareTargetUserNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except sharing_service.InvalidShareRoleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ShareRead(id=share.id, shared_with_email=payload.email, role=share.role, created_at=share.created_at)


@router.get("/{file_id}/shares", response_model=list[ShareRead])
async def list_shares(
    workspace_id: uuid.UUID,
    file_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> list[ShareRead]:
    await _require_editor(session, workspace_id, user.id)
    try:
        await service.get_file(session, workspace_id=workspace_id, file_id=file_id)
    except service.FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="File not found") from exc
    shares = await sharing_service.list_shares_for_resource(session, resource_type="file", resource_id=file_id)
    return [ShareRead(id=share.id, shared_with_email=email, role=share.role, created_at=share.created_at) for share, email in shares]


@router.delete("/{file_id}/shares/{share_id}", status_code=204, response_model=None)
async def revoke_share(
    workspace_id: uuid.UUID,
    file_id: uuid.UUID,
    share_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> None:
    await _require_editor(session, workspace_id, user.id)
    try:
        await sharing_service.revoke_share(session, resource_type="file", resource_id=file_id, share_id=share_id)
    except sharing_service.ShareNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Share not found") from exc


@router.put("/{file_id}/favorite", response_model=FavoriteRead)
async def favorite_file(
    workspace_id: uuid.UUID,
    file_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> FavoriteRead:
    # viewer+, not editor+: favoriting is a personal bookmark, not a write
    # to the resource itself.
    await _require_viewer(session, workspace_id, user.id)
    try:
        await service.get_file(session, workspace_id=workspace_id, file_id=file_id)
    except service.FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="File not found") from exc
    favorite = await favorites_service.add_favorite(session, workspace_id=workspace_id, resource_type="file", resource_id=file_id, user_id=user.id)
    return FavoriteRead.model_validate(favorite)


@router.delete("/{file_id}/favorite", status_code=204, response_model=None)
async def unfavorite_file(
    workspace_id: uuid.UUID,
    file_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> None:
    await _require_viewer(session, workspace_id, user.id)
    await favorites_service.remove_favorite(session, resource_type="file", resource_id=file_id, user_id=user.id)
