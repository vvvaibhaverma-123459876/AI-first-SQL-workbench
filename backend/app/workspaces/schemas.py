from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class WorkspaceCreate(BaseModel):
    name: str


class WorkspaceRead(BaseModel):
    id: uuid.UUID
    name: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}
