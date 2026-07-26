from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class FileCreate(BaseModel):
    name: str
    is_folder: bool = False
    parent_id: uuid.UUID | None = None
    content: str = ""


class FileUpdate(BaseModel):
    content: str | None = None
    name: str | None = None
    parent_id: uuid.UUID | None = None


class FileNode(BaseModel):
    """Tree-listing shape -- no content, so listing a workspace with many
    files stays cheap. Fetch a single file's content via GET /files/{id}."""

    id: uuid.UUID
    parent_id: uuid.UUID | None
    name: str
    is_folder: bool
    updated_at: datetime

    model_config = {"from_attributes": True}


class FileDetail(FileNode):
    content: str


class FileRevisionRead(BaseModel):
    id: uuid.UUID
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class FileSearchResult(BaseModel):
    file_id: uuid.UUID
    name: str
    snippet: str
