from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class ShareCreate(BaseModel):
    email: str
    role: str = "viewer"


class ShareRead(BaseModel):
    id: uuid.UUID
    shared_with_email: str
    role: str
    created_at: datetime


class SharedResourceSummary(BaseModel):
    share_id: uuid.UUID
    resource_type: str
    resource_id: uuid.UUID
    resource_name: str
    workspace_id: uuid.UUID
    role: str
    created_at: datetime


class SharedFileRead(BaseModel):
    id: uuid.UUID
    name: str
    content: str
    role: str


class SharedFileUpdate(BaseModel):
    content: str


class SharedDashboardItemRead(BaseModel):
    id: uuid.UUID
    title: str
    sql: str
    chart_type: str
    x_field: str | None
    y_fields: list[str]
    width: int
    sort_order: int


class SharedDashboardRead(BaseModel):
    id: uuid.UUID
    name: str
    role: str
    items: list[SharedDashboardItemRead]


class SharedDashboardTileResult(BaseModel):
    columns: list[str]
    rows: list[dict]
    row_count: int
    truncated: bool
