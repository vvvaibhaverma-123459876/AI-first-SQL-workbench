from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class DashboardCreate(BaseModel):
    name: str


class DashboardRead(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DashboardItemCreate(BaseModel):
    connection_id: uuid.UUID
    title: str
    sql: str
    chart_type: str = "table"
    x_field: str | None = None
    y_fields: list[str] = []
    width: int = 1


class DashboardItemUpdate(BaseModel):
    title: str | None = None
    sql: str | None = None
    chart_type: str | None = None
    x_field: str | None = None
    y_fields: list[str] | None = None
    width: int | None = None
    sort_order: int | None = None


class DashboardItemRead(BaseModel):
    id: uuid.UUID
    dashboard_id: uuid.UUID
    connection_id: uuid.UUID
    title: str
    sql: str
    chart_type: str
    x_field: str | None
    y_fields: list[str]
    width: int
    sort_order: int
    created_at: datetime

    model_config = {"from_attributes": True}


class DashboardDetail(DashboardRead):
    items: list[DashboardItemRead]
