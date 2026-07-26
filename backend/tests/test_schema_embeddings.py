"""tests/test_schema_embeddings.py

Phase 3d (v2 rebuild): pgvector-backed per-connection schema embeddings,
replacing keyword matching in AIService.suggest_tables() with real cosine-
similarity ranking against a connection's actual tables. Two constraints
shape these tests:

1. pgvector's cosine_distance() compiles to Postgres's `<=>` operator -- a
   hard SQL syntax error on sqlite, not a graceful no-match (verified
   empirically; see embedding_service._dialect_supports_pgvector_search).
   The control-plane DB is sqlite by default for this whole test suite
   (tests/conftest.py), and app.db.control_plane_sync's engine is bound to
   it at import time -- there is no way to swap CONTROL_PLANE_DB_URL to
   Postgres for a single test. So the real-ranking test below builds its
   own throwaway ControlPlaneBase schema directly against TEST_POSTGRES_URL
   (same pattern as test_files.py's real-Postgres FK regression test),
   bypassing the app's own control-plane wiring entirely.
2. Real ranking also needs a real embedding call, so that same test
   additionally skips unless Ollama is reachable with the configured
   embedding model pulled. This project has no other test that requires a
   live LLM (MockProvider covers everything else deterministically) -- this
   is the first, and it will legitimately never run in CI (no Ollama
   there), the same accepted gap already documented for the cloud
   connectors.

Everything else here (the two guard tests and the AIService wiring test)
runs unconditionally, no special environment needed.
"""
from __future__ import annotations

import os
import uuid

import pytest

# Import app.main first, not any connections/embedding module directly --
# see alembic/env.py for why: fastapi-users-db-sqlalchemy 7.0.0's import-
# order bug trips if anything touches fastapi_users_db_sqlalchemy.generics
# (every model's GUID column, embedding_models.SchemaEmbedding included)
# before app.auth.models has loaded. Every other test file in this suite
# guards the same way.
from app.main import app  # noqa: F401


def _test_postgres_url() -> str | None:
    return os.environ.get("TEST_POSTGRES_URL")


def _ollama_embedding_reachable() -> bool:
    from app.connections.embedding_service import embed_text

    try:
        return embed_text("connectivity check") is not None
    except Exception:
        return False


def test_ensure_embeddings_is_a_no_op_when_the_ai_provider_is_mock():
    """Guards the network-call gate: mock mode (this project's default
    posture for deterministic tests, and CI's e2e steps) must never attempt
    to reach Ollama's /api/embeddings endpoint."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.api.schemas import SchemaResponse
    from app.connections.embedding_service import ensure_embeddings

    # sqlite is fine here: provider_name is checked before the dialect
    # guard, so this never reaches a cosine_distance query either.
    engine = create_engine("sqlite:///:memory:", future=True)
    session = sessionmaker(bind=engine, future=True)()
    ready = ensure_embeddings(
        session,
        workspace_id=uuid.uuid4(),
        connection_id=uuid.uuid4(),
        schema=SchemaResponse(tables=[]),
        provider_name="mock",
    )
    assert ready is False


def test_find_relevant_tables_is_a_no_op_on_sqlite_even_when_provider_is_ollama():
    """The dialect guard, not just the provider-name guard: this is what
    actually protects this test suite's default sqlite control-plane DB
    (and any dev box running one) from a hard OperationalError, since
    AI_PROVIDER defaults to 'ollama' even with no live Ollama reachable."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.connections.embedding_service import find_relevant_tables

    engine = create_engine("sqlite:///:memory:", future=True)
    session = sessionmaker(bind=engine, future=True)()
    hits = find_relevant_tables(session, connection_id=uuid.uuid4(), question="anything", provider_name="ollama", top_k=5)
    assert hits is None


def test_suggest_tables_uses_embedding_ranked_results_when_available(monkeypatch):
    """AIService's own wiring, isolated from real Postgres/Ollama: when
    embedding_service reports results are ready, suggest_tables() must
    return them (not fall through to the LLM+keyword path), with no
    provider_fallback warning -- this is the "good" path, not a degraded
    one."""
    from app.api.schemas import ColumnSchema, SchemaResponse, TableSchema
    from app.connections.models import DataConnection
    from app.services import ai_service as ai_service_module
    from app.services.ai_service import AIService

    schema = SchemaResponse(tables=[TableSchema(name="transactions", columns=[ColumnSchema(name="amount", data_type="REAL")])])
    connection = DataConnection(
        id=uuid.uuid4(), workspace_id=uuid.uuid4(), name="fake", connector_type="postgres", encrypted_config="x", created_by=uuid.uuid4()
    )

    class _FakeHit:
        table_name = "transactions"
        column_names = ["amount"]

    class _FakeSession:
        def close(self):
            pass

    monkeypatch.setattr("app.db.control_plane_sync.get_sync_session", lambda: _FakeSession())
    monkeypatch.setattr("app.connections.embedding_service.ensure_embeddings", lambda *a, **k: True)
    monkeypatch.setattr("app.connections.embedding_service.find_relevant_tables", lambda *a, **k: [_FakeHit()])

    service = AIService()
    monkeypatch.setattr(service, "provider", ai_service_module.MockProvider())

    result = service.suggest_tables("top spend by month", schema=schema, connection=connection)
    assert result.provider_fallback is None
    assert [s.table_name for s in result.suggestions] == ["transactions"]
    assert result.suggestions[0].suggested_columns == ["amount"]


def test_schema_embeddings_rank_semantically_relevant_tables_above_irrelevant_ones_on_real_pgvector():
    """The actual payoff this phase exists for: given a question about
    spend, a 'transactions' or 'users' table should outrank an unrelated
    'widgets' table -- verified against real Postgres+pgvector (sqlite
    can't run this assertion at all, see module docstring), with a real
    nomic-embed-text call, not a stubbed vector."""
    postgres_url = _test_postgres_url()
    if not postgres_url:
        pytest.skip("TEST_POSTGRES_URL not set")
    if not _ollama_embedding_reachable():
        from app.core.config import get_settings

        pytest.skip(f"Ollama not reachable with embedding model {get_settings().schema_embedding_model} pulled")

    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    from app.api.schemas import ColumnSchema, SchemaResponse, TableSchema
    from app.auth.models import User
    from app.connections.embedding_service import ensure_embeddings, find_relevant_tables
    from app.connections.models import DataConnection
    from app.db.control_plane import ControlPlaneBase
    from app.db.control_plane_sync import _sync_url
    from app.workspaces.models import Workspace

    engine = create_engine(_sync_url(postgres_url), future=True)
    with engine.begin() as conn:
        # The vector extension is per-database, not per-cluster -- this test
        # bypasses Alembic's own migration (which only enables it in
        # sqlstudio) and builds its schema directly via create_all, same as
        # test_files.py's real-Postgres FK test, so it must ensure the
        # extension itself in whichever database TEST_POSTGRES_URL points
        # at (CI's is deliberately a separate `postgres` db, not sqlstudio).
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        ControlPlaneBase.metadata.create_all(conn)
    session = sessionmaker(bind=engine, future=True)()

    user_id = uuid.uuid4()
    session.add(User(id=user_id, email=f"{user_id}@example.com", hashed_password="x", display_name="Embedding Test", is_active=True, is_superuser=False, is_verified=False))
    workspace = Workspace(name="embedding-test", created_by=user_id)
    session.add(workspace)
    session.flush()
    connection = DataConnection(workspace_id=workspace.id, name="embedding-test-conn", connector_type="sqlite", encrypted_config="x", created_by=user_id)
    session.add(connection)
    session.commit()

    schema = SchemaResponse(
        tables=[
            TableSchema(name="users", columns=[ColumnSchema(name="user_id", data_type="INTEGER"), ColumnSchema(name="full_name", data_type="TEXT"), ColumnSchema(name="email", data_type="TEXT")]),
            TableSchema(name="transactions", columns=[ColumnSchema(name="id", data_type="INTEGER"), ColumnSchema(name="user_id", data_type="INTEGER"), ColumnSchema(name="amount", data_type="REAL")]),
            TableSchema(name="widgets", columns=[ColumnSchema(name="id", data_type="INTEGER"), ColumnSchema(name="label", data_type="TEXT")]),
        ]
    )

    try:
        ready = ensure_embeddings(session, workspace_id=workspace.id, connection_id=connection.id, schema=schema, provider_name="ollama")
        assert ready is True

        hits = find_relevant_tables(session, connection_id=connection.id, question="top users by total spend", provider_name="ollama", top_k=5)
        assert hits is not None
        names = [h.table_name for h in hits]
        assert names[-1] == "widgets", f"expected the irrelevant table to rank last, got {names}"
        assert names[0] in ("users", "transactions"), f"expected a spend-relevant table to rank first, got {names}"
    finally:
        session.execute(text("DELETE FROM schema_embeddings WHERE connection_id = :cid"), {"cid": str(connection.id)})
        session.execute(text("DELETE FROM data_connections WHERE id = :cid"), {"cid": str(connection.id)})
        session.execute(text("DELETE FROM workspaces WHERE id = :wid"), {"wid": str(workspace.id)})
        session.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": str(user_id)})
        session.commit()
        session.close()
