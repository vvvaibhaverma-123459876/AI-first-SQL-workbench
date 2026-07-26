from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.backend import current_active_user
from app.auth.models import User
from app.db.control_plane import get_control_plane_session
from app.files import service
from app.files.schemas import FileCreate, FileDetail, FileNode, FileRevisionRead, FileSearchResult, FileUpdate
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
