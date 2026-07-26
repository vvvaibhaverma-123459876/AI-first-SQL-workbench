"""Phase 4b: scheduled queries -- a query re-run on a cron schedule
against a real connection, notifying via webhook and/or email when its
condition fires. Runs entirely unattended (no live human role check in the
loop, same posture as Phase 4a's dashboard tiles), so only provably
read-only SQL is ever accepted, and a connection is always required (no
legacy-demo fallback).

last_enqueued_at vs. last_run_at is the whole double-fire-prevention story:
last_enqueued_at is stamped by app/scheduler.py's tick() the moment a row
is decided to be due, BEFORE the RQ job actually runs -- so a later tick
(every ~30s) checks cron-due-ness against last_enqueued_at, not
last_run_at, and never re-enqueues a row whose job just hasn't finished
yet. last_run_at/last_status/last_row_count/last_notified_at are stamped
by the job itself on completion, for reporting.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.control_plane import ControlPlaneBase

CONDITIONS = ("always", "threshold", "diff")


class ScheduledQuery(ControlPlaneBase):
    __tablename__ = "scheduled_queries"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("workspaces.id"), nullable=False, index=True)
    connection_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("data_connections.id"), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sql: Mapped[str] = mapped_column(Text, nullable=False)
    cron_expression: Mapped[str] = mapped_column(String(100), nullable=False)
    condition: Mapped[str] = mapped_column(String(16), nullable=False, default="always")  # one of CONDITIONS
    condition_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Deliberately no validation/allowlisting on this URL (SSRF is a known,
    # documented, un-fixed gap here -- same "acknowledge, don't silently
    # fix or silently ignore" precedent as Phase 2's own SSRF gap on
    # user-supplied connection hosts).
    notify_webhook_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    notify_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    last_enqueued_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
