"""Control-plane CRUD for DataConnection rows (async, like the rest of the
control plane) plus the actual external-database operations -- test, browse
schema, run a query (all synchronous: the driver libraries for every one of
these six connector types are blocking, and running them inside an async
route would freeze the event loop for every user on the server, not just the
one running the query). Routes call the sync functions below via
starlette.concurrency.run_in_threadpool.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime

import sqlglot
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.connections.crypto import decrypt_config, encrypt_config
from app.connections.drivers import SQLGLOT_DIALECT_BY_TYPE, ConnectorNotInstalledError, build_engine
from app.connections.models import DataConnection
from app.connections.schemas import CONFIG_MODELS_BY_TYPE, ColumnInfo, ConnectionConfig, QueryResponse, TableInfo, TestConnectionResult
from app.core.config import get_settings


class ConnectionNotFoundError(Exception):
    pass


class DuplicateConnectionNameError(Exception):
    pass


# ---------------------------------------------------------------------------
# Control-plane CRUD (async)
# ---------------------------------------------------------------------------


async def create_connection(
    session: AsyncSession, *, workspace_id: uuid.UUID, created_by: uuid.UUID, name: str, config: ConnectionConfig
) -> DataConnection:
    existing = await session.execute(
        select(DataConnection).where(DataConnection.workspace_id == workspace_id, DataConnection.name == name)
    )
    if existing.scalar_one_or_none() is not None:
        raise DuplicateConnectionNameError(f"A connection named {name!r} already exists in this workspace.")

    connection = DataConnection(
        workspace_id=workspace_id,
        name=name,
        connector_type=config.connector_type,
        encrypted_config=encrypt_config(config.model_dump(by_alias=True)),
        created_by=created_by,
    )
    session.add(connection)
    await session.commit()
    await session.refresh(connection)
    return connection


async def list_connections(session: AsyncSession, *, workspace_id: uuid.UUID) -> list[DataConnection]:
    result = await session.execute(
        select(DataConnection).where(DataConnection.workspace_id == workspace_id).order_by(DataConnection.created_at)
    )
    return list(result.scalars().all())


async def get_connection(session: AsyncSession, *, workspace_id: uuid.UUID, connection_id: uuid.UUID) -> DataConnection:
    result = await session.execute(
        select(DataConnection).where(DataConnection.workspace_id == workspace_id, DataConnection.id == connection_id)
    )
    connection = result.scalar_one_or_none()
    if connection is None:
        raise ConnectionNotFoundError(f"Connection {connection_id} not found in workspace {workspace_id}")
    return connection


async def delete_connection(session: AsyncSession, *, workspace_id: uuid.UUID, connection_id: uuid.UUID) -> None:
    connection = await get_connection(session, workspace_id=workspace_id, connection_id=connection_id)
    await session.delete(connection)
    await session.commit()


async def record_test_result(session: AsyncSession, *, connection: DataConnection, ok: bool) -> None:
    connection.last_tested_at = datetime.utcnow()
    connection.last_test_ok = ok
    await session.commit()


def _load_config(connection: DataConnection) -> ConnectionConfig:
    raw = decrypt_config(connection.encrypted_config)
    model = CONFIG_MODELS_BY_TYPE[connection.connector_type]
    return model.model_validate(raw)


def is_read_only_sql(sql: str, *, connector_type: str) -> bool:
    """Best-effort classification used only to decide whether a viewer (who
    may read but not write) may run this statement. Anything sqlglot can't
    parse is treated as NOT read-only -- fail closed, not open. This is a
    permission check, not a SQL validator: a statement that passes here can
    still fail against the real database for any number of real reasons."""
    dialect = SQLGLOT_DIALECT_BY_TYPE.get(connector_type)
    try:
        statements = sqlglot.parse(sql, read=dialect)
    except Exception:
        return False
    if not statements:
        return False
    return all(isinstance(stmt, sqlglot.exp.Select) for stmt in statements)


# ---------------------------------------------------------------------------
# External-database operations (sync -- call via run_in_threadpool)
# ---------------------------------------------------------------------------


def test_connection_sync(connection: DataConnection) -> TestConnectionResult:
    try:
        config = _load_config(connection)
        engine = build_engine(config)
    except ConnectorNotInstalledError as exc:
        return TestConnectionResult(ok=False, message=str(exc))
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return TestConnectionResult(ok=True, message="Connected successfully.")
    except SQLAlchemyError as exc:
        reason = str(getattr(exc, "orig", None) or exc)
        return TestConnectionResult(ok=False, message=reason)
    finally:
        engine.dispose()


def get_schema_sync(connection: DataConnection) -> list[TableInfo]:
    config = _load_config(connection)
    engine = build_engine(config)
    try:
        inspector = inspect(engine)
        tables: list[TableInfo] = []
        schema_names = inspector.get_schema_names() if hasattr(inspector, "get_schema_names") else [None]
        for schema_name in schema_names or [None]:
            for table_name in inspector.get_table_names(schema=schema_name):
                columns = inspector.get_columns(table_name, schema=schema_name)
                tables.append(
                    TableInfo(
                        schema_name=schema_name,
                        name=table_name,
                        columns=[ColumnInfo(name=c["name"], type=str(c["type"]), nullable=bool(c["nullable"])) for c in columns],
                    )
                )
        return tables
    finally:
        engine.dispose()


def run_query_sync(connection: DataConnection, sql: str) -> QueryResponse:
    config = _load_config(connection)
    engine = build_engine(config)
    row_limit = get_settings().default_row_limit
    started = time.perf_counter()
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            columns = list(result.keys())
            rows = []
            truncated = False
            for i, row in enumerate(result):
                if i >= row_limit:
                    truncated = True
                    break
                rows.append(dict(row._mapping))
        return QueryResponse(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            truncated=truncated,
            execution_ms=int((time.perf_counter() - started) * 1000),
        )
    except SQLAlchemyError as exc:
        reason = str(getattr(exc, "orig", None) or exc)
        raise ValueError(reason) from exc
    finally:
        engine.dispose()
