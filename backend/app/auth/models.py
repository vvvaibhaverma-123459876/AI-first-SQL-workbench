"""The user table. Extra profile fields go here as they're needed —
fastapi-users' base class already provides id/email/hashed_password/
is_active/is_superuser/is_verified."""
from __future__ import annotations

from datetime import datetime

from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.control_plane import ControlPlaneBase


class User(SQLAlchemyBaseUserTableUUID, ControlPlaneBase):
    __tablename__ = "users"

    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
