"""Semantic table retrieval for real connections' schemas: embeds each
table (name + columns) via a local Ollama embedding model and ranks
candidates against a question by cosine similarity (pgvector). This is the
Phase 3d replacement for AIService.suggest_tables()'s keyword-matching
fallback, scoped per connection (see embedding_models.SchemaEmbedding).

Every function here degrades to `None`/`False` rather than raising --
callers (ai_service.py) are expected to fall back to the existing
LLM+keyword path and surface that as a provider_fallback message, the same
"visible degradation, never silent" posture used everywhere else AI calls
can fail in this project. Deliberately never attempted when the AI
provider is "mock" (no Ollama running, e.g. CI's e2e/mock steps) --
checked via provider_name rather than a network probe, to avoid a slow
timeout on every mock-mode call.
"""
from __future__ import annotations

import uuid

import requests
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.schemas import SchemaResponse
from app.connections.embedding_models import SchemaEmbedding
from app.core.config import get_settings
from app.utils.schema_text import schema_to_prompt_text


def embed_text(text: str) -> list[float] | None:
    settings = get_settings()
    try:
        response = requests.post(
            f"{settings.ollama_base_url.rstrip('/')}/api/embeddings",
            json={"model": settings.schema_embedding_model, "prompt": text},
            timeout=30,
        )
        response.raise_for_status()
        embedding = response.json().get("embedding")
        return embedding if embedding else None
    except Exception:
        return None


def _table_text(table_name: str, schema: SchemaResponse) -> tuple[str, list[str]] | None:
    for table in schema.tables:
        if table.name == table_name:
            single = SchemaResponse(tables=[table])
            return schema_to_prompt_text(single), [col.name for col in table.columns]
    return None


def _compute_and_store(session: Session, *, workspace_id: uuid.UUID, connection_id: uuid.UUID, schema: SchemaResponse) -> bool:
    settings = get_settings()
    tables = schema.tables[: settings.schema_embedding_max_tables]
    rows: list[SchemaEmbedding] = []
    for table in tables:
        rendered = _table_text(table.name, schema)
        if rendered is None:
            continue
        text, column_names = rendered
        vector = embed_text(text)
        if vector is None:
            return False  # embedding model unreachable partway through -- abort, don't store a half-embedded connection
        rows.append(
            SchemaEmbedding(
                workspace_id=workspace_id,
                connection_id=connection_id,
                table_name=table.name,
                schema_text=text,
                column_names=column_names,
                embedding=vector,
            )
        )
    if not rows:
        return False
    session.add_all(rows)
    session.commit()
    return True


def _dialect_supports_pgvector_search(session: Session) -> bool:
    """cosine_distance() compiles to Postgres's `<=>` operator, which is a
    hard SQL syntax error on any other dialect (verified against sqlite --
    it's not a graceful no-match, it's an OperationalError). The control-
    plane DB defaults to sqlite for a fresh clone/dev box and for the whole
    test suite (see tests/conftest.py), so this must be checked before ever
    building a query that uses it, not just before calling Ollama."""
    return session.bind is not None and session.bind.dialect.name == "postgresql"


def ensure_embeddings(session: Session, *, workspace_id: uuid.UUID, connection_id: uuid.UUID, schema: SchemaResponse, provider_name: str) -> bool:
    """Computes embeddings for this connection on first use; a no-op if
    they already exist (no schema-drift detection -- see refresh_embeddings
    for the manual fix). Returns whether embeddings are ready to query."""
    if provider_name != "ollama" or not _dialect_supports_pgvector_search(session):
        return False
    existing = session.execute(select(SchemaEmbedding.id).where(SchemaEmbedding.connection_id == connection_id).limit(1)).first()
    if existing is not None:
        return True
    return _compute_and_store(session, workspace_id=workspace_id, connection_id=connection_id, schema=schema)


def refresh_embeddings(session: Session, *, workspace_id: uuid.UUID, connection_id: uuid.UUID, schema: SchemaResponse, provider_name: str) -> bool:
    """Force-recomputes embeddings for this connection, e.g. after its real
    schema changed. Deletes existing rows first so a partial recompute
    failure can't leave stale and fresh rows mixed together."""
    if provider_name != "ollama" or not _dialect_supports_pgvector_search(session):
        return False
    session.execute(delete(SchemaEmbedding).where(SchemaEmbedding.connection_id == connection_id))
    session.commit()
    return _compute_and_store(session, workspace_id=workspace_id, connection_id=connection_id, schema=schema)


def find_relevant_tables(session: Session, *, connection_id: uuid.UUID, question: str, provider_name: str, top_k: int = 5) -> list[SchemaEmbedding] | None:
    if provider_name != "ollama" or not _dialect_supports_pgvector_search(session):
        return None
    query_vector = embed_text(question)
    if query_vector is None:
        return None
    result = session.execute(
        select(SchemaEmbedding)
        .where(SchemaEmbedding.connection_id == connection_id)
        .order_by(SchemaEmbedding.embedding.cosine_distance(query_vector))
        .limit(top_k)
    )
    hits = list(result.scalars().all())
    return hits if hits else None
