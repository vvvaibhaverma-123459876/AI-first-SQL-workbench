from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.auth.backend import current_active_user
from app.auth.models import User
from app.connections import service
from app.connections.drivers import ConnectorNotInstalledError
from app.connections.schemas import (
    DataConnectionCreate,
    DataConnectionRead,
    QueryRequest,
    QueryResponse,
    TableInfo,
    TestConnectionResult,
)
from app.db.control_plane import get_control_plane_session
from app.workspaces import service as workspace_service

router = APIRouter(prefix="/workspaces/{workspace_id}/connections", tags=["connections"])


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


@router.post("", response_model=DataConnectionRead)
async def create_connection(
    workspace_id: uuid.UUID,
    payload: DataConnectionCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> DataConnectionRead:
    await _require_editor(session, workspace_id, user.id)
    try:
        connection = await service.create_connection(
            session, workspace_id=workspace_id, created_by=user.id, name=payload.name, config=payload.config
        )
    except service.DuplicateConnectionNameError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return DataConnectionRead.model_validate(connection)


@router.get("", response_model=list[DataConnectionRead])
async def list_connections(
    workspace_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> list[DataConnectionRead]:
    await _require_viewer(session, workspace_id, user.id)
    connections = await service.list_connections(session, workspace_id=workspace_id)
    return [DataConnectionRead.model_validate(c) for c in connections]


@router.delete("/{connection_id}", status_code=204, response_model=None)
async def delete_connection(
    workspace_id: uuid.UUID,
    connection_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> None:
    await _require_editor(session, workspace_id, user.id)
    try:
        await service.delete_connection(session, workspace_id=workspace_id, connection_id=connection_id)
    except service.ConnectionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Connection not found") from exc


@router.post("/{connection_id}/test", response_model=TestConnectionResult)
async def test_connection(
    workspace_id: uuid.UUID,
    connection_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> TestConnectionResult:
    await _require_viewer(session, workspace_id, user.id)
    try:
        connection = await service.get_connection(session, workspace_id=workspace_id, connection_id=connection_id)
    except service.ConnectionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Connection not found") from exc
    result = await run_in_threadpool(service.test_connection_sync, connection)
    await service.record_test_result(session, connection=connection, ok=result.ok)
    return result


@router.get("/{connection_id}/schema", response_model=list[TableInfo])
async def get_schema(
    workspace_id: uuid.UUID,
    connection_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> list[TableInfo]:
    await _require_viewer(session, workspace_id, user.id)
    try:
        connection = await service.get_connection(session, workspace_id=workspace_id, connection_id=connection_id)
    except service.ConnectionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Connection not found") from exc
    try:
        return await run_in_threadpool(service.get_schema_sync, connection)
    except ConnectorNotInstalledError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not read schema: {exc}") from exc


def _refresh_embeddings_sync(connection) -> bool:
    # Local imports: this function runs in a threadpool worker at request
    # time, long after app startup has finished, so there's no import-order
    # risk here -- but kept local anyway for consistency with the same
    # defensive pattern used in ai_service.py (see its TYPE_CHECKING note).
    from app.assistant.orchestrator import schema_for_connection
    from app.connections.embedding_service import refresh_embeddings
    from app.db.control_plane_sync import get_sync_session
    from app.llm.providers import get_provider

    schema = schema_for_connection(connection)
    session = get_sync_session()
    try:
        return refresh_embeddings(
            session,
            workspace_id=connection.workspace_id,
            connection_id=connection.id,
            schema=schema,
            provider_name=get_provider().provider_name,
        )
    finally:
        session.close()


@router.post("/{connection_id}/schema/embeddings/refresh")
async def refresh_schema_embeddings(
    workspace_id: uuid.UUID,
    connection_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> dict:
    """Force-recomputes this connection's semantic table-retrieval
    embeddings (app/connections/embedding_service.py). The one known gap in
    Phase 3d: embeddings are computed once on first use and never
    auto-invalidated when the connection's real schema changes underneath
    them, so this is the manual fix. Editor+ only -- it's a write to
    control-plane state, same bar as creating a connection."""
    await _require_editor(session, workspace_id, user.id)
    try:
        connection = await service.get_connection(session, workspace_id=workspace_id, connection_id=connection_id)
    except service.ConnectionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Connection not found") from exc
    try:
        refreshed = await run_in_threadpool(_refresh_embeddings_sync, connection)
    except ConnectorNotInstalledError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not refreshed:
        return {
            "status": "unavailable",
            "detail": (
                "Semantic retrieval is unavailable right now (AI_MODE is not 'ollama', "
                "the embedding model is unreachable, or this connection has no tables) -- "
                "keyword-based suggestion will still be used."
            ),
        }
    return {"status": "refreshed"}


@router.post("/{connection_id}/query", response_model=QueryResponse)
async def run_query(
    workspace_id: uuid.UUID,
    connection_id: uuid.UUID,
    payload: QueryRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_control_plane_session),
) -> QueryResponse:
    # Viewers may run read-only statements against a connection (this is a
    # read action on the workspace, mirroring "viewer can read files, not
    # write them"); anything sqlglot can't prove is read-only requires
    # editor+, the same bar as writing a file.
    try:
        connection = await service.get_connection(session, workspace_id=workspace_id, connection_id=connection_id)
    except service.ConnectionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Connection not found") from exc

    if service.is_read_only_sql(payload.sql, connector_type=connection.connector_type):
        await _require_viewer(session, workspace_id, user.id)
    else:
        await _require_editor(session, workspace_id, user.id)

    try:
        return await run_in_threadpool(service.run_query_sync, connection, payload.sql)
    except ConnectorNotInstalledError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
