from __future__ import annotations

import uuid

from croniter import CroniterBadCronError, croniter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connections import service as connections_service
from app.scheduled_queries.models import CONDITIONS, ScheduledQuery
from app.workspaces.models import AuditLogEntry


class ScheduledQueryNotFoundError(Exception):
    pass


class InvalidScheduledQueryError(Exception):
    """Bad cron expression, bad condition, or SQL that isn't provably
    read-only. A scheduled query runs unattended, so -- same posture as
    Phase 4a's dashboard tiles -- only read-only SQL is ever accepted,
    regardless of the creator's role."""


def _validate_cron(cron_expression: str) -> None:
    try:
        croniter(cron_expression)
    except (CroniterBadCronError, ValueError) as exc:
        raise InvalidScheduledQueryError(f"Invalid cron expression: {exc}") from exc


async def _assert_valid(
    session: AsyncSession, *, workspace_id: uuid.UUID, connection_id: uuid.UUID, sql: str, cron_expression: str, condition: str, condition_value: float | None
) -> None:
    if condition not in CONDITIONS:
        raise InvalidScheduledQueryError(f"condition must be one of {CONDITIONS}")
    if condition in ("threshold", "diff") and condition_value is None:
        raise InvalidScheduledQueryError(f"condition_value is required for condition={condition!r}")
    _validate_cron(cron_expression)
    try:
        connection = await connections_service.get_connection(session, workspace_id=workspace_id, connection_id=connection_id)
    except connections_service.ConnectionNotFoundError as exc:
        raise InvalidScheduledQueryError(f"Connection {connection_id} not found in this workspace.") from exc
    if not connections_service.is_read_only_sql(sql, connector_type=connection.connector_type):
        raise InvalidScheduledQueryError("Only read-only SELECT/WITH queries can be scheduled.")


async def create_scheduled_query(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    created_by: uuid.UUID,
    connection_id: uuid.UUID,
    name: str,
    sql: str,
    cron_expression: str,
    condition: str,
    condition_value: float | None,
    notify_webhook_url: str | None,
    notify_email: str | None,
) -> ScheduledQuery:
    await _assert_valid(session, workspace_id=workspace_id, connection_id=connection_id, sql=sql, cron_expression=cron_expression, condition=condition, condition_value=condition_value)
    row = ScheduledQuery(
        workspace_id=workspace_id, connection_id=connection_id, created_by=created_by, name=name, sql=sql,
        cron_expression=cron_expression, condition=condition, condition_value=condition_value,
        notify_webhook_url=notify_webhook_url, notify_email=notify_email,
    )
    session.add(row)
    await session.flush()
    session.add(AuditLogEntry(workspace_id=workspace_id, user_id=created_by, action="scheduled_query.created", detail=name))
    await session.commit()
    await session.refresh(row)
    return row


async def list_scheduled_queries(session: AsyncSession, *, workspace_id: uuid.UUID) -> list[ScheduledQuery]:
    result = await session.execute(select(ScheduledQuery).where(ScheduledQuery.workspace_id == workspace_id).order_by(ScheduledQuery.name))
    return list(result.scalars().all())


async def get_scheduled_query(session: AsyncSession, *, workspace_id: uuid.UUID, scheduled_query_id: uuid.UUID) -> ScheduledQuery:
    result = await session.execute(select(ScheduledQuery).where(ScheduledQuery.id == scheduled_query_id, ScheduledQuery.workspace_id == workspace_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise ScheduledQueryNotFoundError(f"scheduled query {scheduled_query_id} not found in workspace {workspace_id}")
    return row


async def update_scheduled_query(
    session: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    scheduled_query_id: uuid.UUID,
    name: str | None,
    sql: str | None,
    cron_expression: str | None,
    condition: str | None,
    condition_value: float | None | object,
    notify_webhook_url: str | None | object,
    notify_email: str | None | object,
    is_active: bool | None,
) -> ScheduledQuery:
    row = await get_scheduled_query(session, workspace_id=workspace_id, scheduled_query_id=scheduled_query_id)

    new_sql = sql if sql is not None else row.sql
    new_cron = cron_expression if cron_expression is not None else row.cron_expression
    new_condition = condition if condition is not None else row.condition
    new_condition_value = row.condition_value if condition_value is ... else condition_value
    if sql is not None or cron_expression is not None or condition is not None or condition_value is not ...:
        await _assert_valid(session, workspace_id=workspace_id, connection_id=row.connection_id, sql=new_sql, cron_expression=new_cron, condition=new_condition, condition_value=new_condition_value)

    if name is not None:
        row.name = name
    row.sql = new_sql
    row.cron_expression = new_cron
    row.condition = new_condition
    row.condition_value = new_condition_value
    if notify_webhook_url is not ...:
        row.notify_webhook_url = notify_webhook_url
    if notify_email is not ...:
        row.notify_email = notify_email
    if is_active is not None:
        row.is_active = is_active

    await session.commit()
    await session.refresh(row)
    return row


async def delete_scheduled_query(session: AsyncSession, *, workspace_id: uuid.UUID, scheduled_query_id: uuid.UUID) -> None:
    row = await get_scheduled_query(session, workspace_id=workspace_id, scheduled_query_id=scheduled_query_id)
    await session.delete(row)
    await session.commit()
