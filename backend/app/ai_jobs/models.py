"""An AiJob tracks one queued AI call (generate/explain/repair/suggest, and
investigate in a later phase) from creation through the RQ worker picking
it up and writing back a result or error. The API creates the row and
enqueues the job in one call; the worker process (app/worker.py) is the
only thing that ever transitions status away from "queued"."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.control_plane import ControlPlaneBase

TASK_TYPES = ("generate", "explain", "repair", "suggest", "investigate")
STATUSES = ("queued", "running", "done", "failed")


class AiJob(ControlPlaneBase):
    __tablename__ = "ai_jobs"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("workspaces.id"), nullable=False, index=True)
    task_type: Mapped[str] = mapped_column(String(32), nullable=False)  # one of TASK_TYPES
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")  # one of STATUSES
    input: Mapped[dict] = mapped_column(JSON, nullable=False)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
