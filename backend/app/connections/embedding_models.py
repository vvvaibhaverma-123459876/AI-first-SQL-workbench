"""Per-connection, per-table schema embeddings (pgvector) used to rank
tables by semantic relevance to a question -- the replacement for keyword
matching in AIService.suggest_tables() when a real connection is attached
(Phase 3d). Computed lazily on first use per connection and cached
indefinitely; there is no automatic invalidation when a connection's real
schema changes underneath it -- see the refresh endpoint in
connections/routes.py for the manual fix.

nomic-embed-text (Ollama, 768-dim) is the only model this has been
verified against (see sql-studio-v2-rebuild memory for the cosine-
similarity sanity check). Vector(768) hardcodes that dimensionality:
changing OLLAMA_EMBEDDING_MODEL to a model with a different embedding size
requires a migration, not just a config change.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi_users_db_sqlalchemy.generics import GUID
from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.control_plane import ControlPlaneBase

EMBEDDING_DIMENSIONS = 768


class SchemaEmbedding(ControlPlaneBase):
    __tablename__ = "schema_embeddings"
    __table_args__ = (UniqueConstraint("connection_id", "table_name", name="uq_schema_embedding_connection_table"),)

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("workspaces.id"), nullable=False, index=True)
    connection_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("data_connections.id"), nullable=False, index=True)
    table_name: Mapped[str] = mapped_column(String(255), nullable=False)
    schema_text: Mapped[str] = mapped_column(Text, nullable=False)  # exact text embedded, kept for debugging/inspection
    column_names: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
