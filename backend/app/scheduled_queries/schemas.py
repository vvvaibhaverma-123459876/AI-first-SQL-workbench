from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class ScheduledQueryCreate(BaseModel):
    connection_id: uuid.UUID
    name: str
    sql: str
    cron_expression: str
    condition: str = "always"
    condition_value: float | None = None
    notify_webhook_url: str | None = None
    notify_email: str | None = None


class ScheduledQueryUpdate(BaseModel):
    name: str | None = None
    sql: str | None = None
    cron_expression: str | None = None
    condition: str | None = None
    condition_value: float | None = None
    notify_webhook_url: str | None = None
    notify_email: str | None = None
    is_active: bool | None = None


class ScheduledQueryRead(BaseModel):
    id: uuid.UUID
    connection_id: uuid.UUID
    name: str
    sql: str
    cron_expression: str
    condition: str
    condition_value: float | None
    notify_webhook_url: str | None
    notify_email: str | None
    is_active: bool
    last_enqueued_at: datetime | None
    last_run_at: datetime | None
    last_status: str | None
    last_row_count: int | None
    last_notified_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RunNowResult(BaseModel):
    status: str
    row_count: int | None = None
