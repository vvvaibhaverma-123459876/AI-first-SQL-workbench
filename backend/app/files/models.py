"""The IDE's file tree: folders and files, scoped to a workspace. A File
row with is_folder=True never has content and only exists to nest other
rows under it via parent_id (NULL = workspace root).

FileRevision is the safety net for autosave: without it, a debounced
"save on every keystroke pause" model could silently overwrite a good
version with a bad one and there would be no way back."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.control_plane import ControlPlaneBase


class File(ControlPlaneBase):
    __tablename__ = "files"
    __table_args__ = (UniqueConstraint("workspace_id", "parent_id", "name", name="uq_file_name_within_parent"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("workspaces.id"), nullable=False, index=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("files.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_folder: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FileRevision(ControlPlaneBase):
    """A throttled snapshot of a file's content, taken before an autosave
    overwrites it (see service.MIN_SECONDS_BETWEEN_REVISIONS) -- not one row
    per keystroke."""

    __tablename__ = "file_revisions"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    file_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("files.id"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
