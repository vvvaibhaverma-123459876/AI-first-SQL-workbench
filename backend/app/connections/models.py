"""A DataConnection is a workspace's saved link to an external database --
Postgres, MySQL, SQLite, Snowflake, BigQuery, or Databricks. Credentials live
only as an encrypted blob (see crypto.py); the plaintext config is never
persisted and never round-tripped back through the API after creation."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.control_plane import ControlPlaneBase

CONNECTOR_TYPES = ("postgres", "mysql", "sqlite", "snowflake", "bigquery", "databricks")


class DataConnection(ControlPlaneBase):
    __tablename__ = "data_connections"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_connection_name_within_workspace"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    connector_type: Mapped[str] = mapped_column(String(32), nullable=False)  # one of CONNECTOR_TYPES
    encrypted_config: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_test_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
