"""Phase 5b: favorites. A purely personal bookmark on a file or dashboard
the user already has access to -- unlike sharing (Phase 5a), this changes
no one's visibility, so it carries no permission-model risk and needs no
top-level /shared/... style route split.

resource_id is polymorphic (file or dashboard id), same as
app.sharing.models.ResourceShare, so it cannot carry a real foreign key --
delete_favorites_for_resource must be called from files/service.py and
dashboards/service.py's delete_* functions, mirroring the sharing cascade."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.control_plane import ControlPlaneBase

FAVORITE_RESOURCE_TYPES = ("file", "dashboard")


class Favorite(ControlPlaneBase):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "resource_type", "resource_id", name="uq_favorite_target"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("workspaces.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("users.id"), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(16), nullable=False)  # one of FAVORITE_RESOURCE_TYPES
    resource_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
