"""Phase 5a: additive external sharing. Workspace visibility is unchanged
by this (every member still sees every file/dashboard in their workspace,
same as Phases 0-4) -- a ResourceShare grants a SPECIFIC file or dashboard
to a user who is NOT necessarily a workspace member at all. Read access to
a shared resource goes through brand-new top-level routes
(app/sharing/routes.py's /shared/... endpoints), never through the
existing workspace-scoped routes -- keeps every prior phase's permission
test and route untouched.

resource_id is polymorphic (a file or dashboard id) so it cannot carry a
real foreign key -- explicit cascade-delete in files/service.py and
dashboards/service.py is required when a shared resource is deleted, and
list_shared_with_me must tolerate an orphaned row as a defensive fallback
in case a cascade is ever missed (degrade to a hidden row, not a 500)."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi_users_db_sqlalchemy.generics import GUID
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.control_plane import ControlPlaneBase

RESOURCE_TYPES = ("file", "dashboard")
SHARE_ROLES = ("viewer", "editor")


class ResourceShare(ControlPlaneBase):
    __tablename__ = "resource_shares"
    __table_args__ = (UniqueConstraint("resource_type", "resource_id", "shared_with_user_id", name="uq_resource_share_target"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("workspaces.id"), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(16), nullable=False)  # one of RESOURCE_TYPES
    resource_id: Mapped[uuid.UUID] = mapped_column(GUID, nullable=False, index=True)
    shared_with_user_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("users.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # one of SHARE_ROLES
    created_by: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
