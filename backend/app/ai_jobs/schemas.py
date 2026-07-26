from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AiJobCreate(BaseModel):
    task_type: str
    input: dict[str, Any]


class AiJobRead(BaseModel):
    id: uuid.UUID
    task_type: str
    status: str
    result: dict[str, Any] | None
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}
