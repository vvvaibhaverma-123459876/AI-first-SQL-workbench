from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class FavoriteRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    resource_type: str
    resource_id: uuid.UUID
    created_at: datetime


class FavoriteSummary(BaseModel):
    favorite_id: uuid.UUID
    resource_type: str
    resource_id: uuid.UUID
    resource_name: str
    created_at: datetime
