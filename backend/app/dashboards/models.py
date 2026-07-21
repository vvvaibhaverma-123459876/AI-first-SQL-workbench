"""Phase 4a: dashboards -- named, workspace-scoped grids of pinned queries
with a chart type each. Unlike investigate's write-ups (Phase 3b), a
dashboard is an interactive live grid of re-run queries, not narrative text,
so it's its own entity rather than file-tree content.

Every item requires a connection_id (no legacy-demo fallback) -- same
posture Phase 3c's Investigate panel established: real workspace data only,
no silent fallback."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.control_plane import ControlPlaneBase

CHART_TYPES = ("table", "bar", "line", "pie", "scatter")


class Dashboard(ControlPlaneBase):
    __tablename__ = "dashboards"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_dashboard_name_within_workspace"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("workspaces.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DashboardItem(ControlPlaneBase):
    """A pinned query + chart config. `sort_order` and `width` (grid columns
    spanned, 1-3) are the whole "arrange in a grid" story -- a simple
    reorder/resize model, not freeform drag-and-drop, since the acceptance
    bar is persistence across reload, not pixel-perfect layout."""

    __tablename__ = "dashboard_items"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    dashboard_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("dashboards.id"), nullable=False, index=True)
    connection_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("data_connections.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    sql: Mapped[str] = mapped_column(Text, nullable=False)
    chart_type: Mapped[str] = mapped_column(String(16), nullable=False, default="table")  # one of CHART_TYPES
    x_field: Mapped[str | None] = mapped_column(String(200), nullable=True)
    y_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    width: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
