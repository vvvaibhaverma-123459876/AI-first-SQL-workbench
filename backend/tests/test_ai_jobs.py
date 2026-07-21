"""tests/test_ai_jobs.py

Phase 3 parts A and B (v2 rebuild): the RQ job queue every AI call runs
through, per-task model configuration, and the multi-step investigate
agent built on top of it. Uses a real Redis (skipped if
TEST_REDIS_URL/REDIS_URL isn't reachable) and RQ's SimpleWorker in burst
mode to process queued jobs synchronously and deterministically -- no
background worker process needed for the test itself, but this exercises
the exact same job function (app.ai_jobs.tasks.run_ai_task) the real
worker (app/worker.py) runs.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from rq import SimpleWorker

from app.core.config import get_settings
from app.main import app


def _redis_reachable() -> bool:
    try:
        Redis.from_url(get_settings().redis_url).ping()
        return True
    except RedisConnectionError:
        return False


pytestmark = pytest.mark.skipif(not _redis_reachable(), reason="Redis not reachable at REDIS_URL -- set it to a running Redis to run this suite")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def auth_headers(client):
    email = "ai-jobs-owner@example.com"
    client.post("/api/auth/register", json={"email": email, "password": "correcthorsebatterystaple", "display_name": "AI Jobs Owner"})
    r = client.post("/api/auth/jwt/login", data={"username": email, "password": "correcthorsebatterystaple"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def workspace_id(client, auth_headers):
    r = client.post("/api/workspaces", json={"name": "AI Jobs Test Workspace"}, headers=auth_headers)
    return r.json()["id"]


def _run_pending_jobs():
    """Drains the ai_tasks queue synchronously -- the in-process stand-in
    for `python -m app.worker` during tests."""
    from app.ai_jobs.queue import ai_queue, redis_conn

    SimpleWorker([ai_queue], connection=redis_conn).work(burst=True)


def test_generate_job_runs_end_to_end(client, auth_headers, workspace_id):
    r = client.post(
        f"/api/workspaces/{workspace_id}/ai/jobs",
        json={"task_type": "generate", "input": {"prompt": "top users by spend"}},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    job_id = r.json()["id"]
    assert r.json()["status"] == "queued"

    _run_pending_jobs()

    r = client.get(f"/api/workspaces/{workspace_id}/ai/jobs/{job_id}", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "done", body
    assert body["result"]["sql"]


def test_generate_job_produces_dialect_correct_sql_for_a_real_postgres_connection(client, auth_headers, workspace_id, monkeypatch):
    """Phase 3c: the AI pipeline used to be hardwired to the bundled demo
    SQLite database regardless of which connection a job named -- this is
    the test that would have caught it. Forces mock mode (a fresh AIService()
    is constructed per job execution in tasks.py, unlike the app.api.routes
    singletons -- see test_demo_quality_audit.py for why that distinction
    matters) so this asserts on prompt-engineering/plumbing correctness
    deterministically, not on a live model's non-deterministic output.

    Specifically checks a *dialect-divergent* case, not just row count:
    SQLite's strftime() has no equivalent in Postgres, which needs to_char()
    instead. Schema-correct-but-wrong-dialect SQL looks fine as text and
    fails only at execution -- so this also actually runs the generated SQL
    against the real connection, not just inspects it."""
    import os

    from app.core.config import get_settings
    from app.llm.providers import get_provider

    if not os.environ.get("TEST_POSTGRES_URL"):
        pytest.skip("TEST_POSTGRES_URL not set")

    from sqlalchemy.engine import make_url

    url = make_url(os.environ["TEST_POSTGRES_URL"])
    pg_config = {"connector_type": "postgres", "host": url.host, "port": url.port or 5432, "database": url.database, "username": url.username, "password": url.password}

    import psycopg2

    seed_conn = psycopg2.connect(host=pg_config["host"], port=pg_config["port"], dbname=pg_config["database"], user=pg_config["username"], password=pg_config["password"])
    seed_conn.autocommit = True
    with seed_conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS transactions")
        cur.execute("CREATE TABLE transactions (transaction_at TIMESTAMP, amount NUMERIC, status TEXT)")
        cur.execute("INSERT INTO transactions VALUES ('2026-01-15', 100, 'success'), ('2026-02-15', 200, 'success')")
    seed_conn.close()

    r = client.post(f"/api/workspaces/{workspace_id}/connections", json={"name": "dialect-test-postgres", "config": pg_config}, headers=auth_headers)
    assert r.status_code == 200, r.text
    connection_id = r.json()["id"]

    prior_ai_mode = os.environ.get("AI_MODE")
    os.environ["AI_MODE"] = "mock"
    get_settings.cache_clear()
    get_provider.cache_clear()
    try:
        r = client.post(
            f"/api/workspaces/{workspace_id}/ai/jobs",
            json={"task_type": "generate", "input": {"prompt": "monthly revenue", "connection_id": connection_id}},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        job_id = r.json()["id"]
        _run_pending_jobs()

        r = client.get(f"/api/workspaces/{workspace_id}/ai/jobs/{job_id}", headers=auth_headers)
        body = r.json()
        assert body["status"] == "done", body
        sql = body["result"]["sql"]
        assert "to_char(" in sql.lower(), sql
        assert "strftime" not in sql.lower(), sql
    finally:
        if prior_ai_mode is None:
            os.environ.pop("AI_MODE", None)
        else:
            os.environ["AI_MODE"] = prior_ai_mode
        get_settings.cache_clear()
        get_provider.cache_clear()

    # Not just syntactically plausible -- actually valid Postgres SQL.
    r = client.post(f"/api/workspaces/{workspace_id}/connections/{connection_id}/query", json={"sql": sql}, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["rows"], r.json()


def test_investigate_job_uses_a_real_connections_schema_not_the_demo_data(client, auth_headers, workspace_id, tmp_path):
    """Same regression this phase closes, from the investigate side: a
    question answered against a connection whose schema shares no table
    names with the bundled demo (users/transactions/...) must produce a
    report about THIS connection's data, not the demo's."""
    import sqlite3

    db_path = tmp_path / "widgets_fixture.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE widgets (id INTEGER PRIMARY KEY, label TEXT)")
    conn.executemany("INSERT INTO widgets (label) VALUES (?)", [("alpha",), ("beta",), ("gamma",)])
    conn.commit()
    conn.close()

    r = client.post(
        f"/api/workspaces/{workspace_id}/connections",
        json={"name": "widgets-sqlite", "config": {"connector_type": "sqlite", "path": str(db_path)}},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    connection_id = r.json()["id"]

    r = client.post(
        f"/api/workspaces/{workspace_id}/ai/jobs",
        json={"task_type": "investigate", "input": {"question": "how many widgets are there", "connection_id": connection_id}},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    job_id = r.json()["id"]
    _run_pending_jobs()

    r = client.get(f"/api/workspaces/{workspace_id}/ai/jobs/{job_id}", headers=auth_headers)
    body = r.json()
    assert body["status"] == "done", body

    r = client.get(f"/api/workspaces/{workspace_id}/files/{body['result']['file_id']}", headers=auth_headers)
    content = r.json()["content"]
    assert "widgets" in content.lower(), content
    assert "users" not in content.lower(), content
    assert "transactions" not in content.lower(), content


def test_invalid_connection_id_is_rejected_at_creation_not_left_queued(client, auth_headers, workspace_id):
    r = client.post(
        f"/api/workspaces/{workspace_id}/ai/jobs",
        json={"task_type": "generate", "input": {"prompt": "x", "connection_id": "00000000-0000-0000-0000-000000000000"}},
        headers=auth_headers,
    )
    assert r.status_code == 400


def test_invalid_task_type_is_rejected(client, auth_headers, workspace_id):
    r = client.post(
        f"/api/workspaces/{workspace_id}/ai/jobs",
        json={"task_type": "not-a-real-task", "input": {}},
        headers=auth_headers,
    )
    assert r.status_code == 400


def test_investigate_job_chains_a_followup_and_writes_a_report_file(client, auth_headers, workspace_id):
    """The multi-step investigate agent: runs the primary question, an
    automatic follow-up drawn from the orchestrator's own next_questions,
    then writes a synthesis tying both together as a new file in the
    workspace's file tree (not a separate report entity -- this project's
    file-centric IDE identity means AI write-ups are just files, openable
    and editable like anything else)."""
    r = client.post(
        f"/api/workspaces/{workspace_id}/ai/jobs",
        json={"task_type": "investigate", "input": {"question": "top users by spend"}},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    job_id = r.json()["id"]

    _run_pending_jobs()

    r = client.get(f"/api/workspaces/{workspace_id}/ai/jobs/{job_id}", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "done", body
    assert body["result"]["file_id"]
    assert body["result"]["summary"]

    r = client.get(f"/api/workspaces/{workspace_id}/files/{body['result']['file_id']}", headers=auth_headers)
    assert r.status_code == 200, r.text
    file_body = r.json()
    assert file_body["name"].startswith("Investigation - ")
    assert "## Summary" in file_body["content"]
    assert "## Step 1" in file_body["content"]


def test_a_viewer_cannot_start_an_investigation_but_can_start_other_ai_tasks(client, auth_headers, workspace_id):
    """investigate writes a new file into the workspace (unlike
    generate/explain/repair/suggest, which only produce text) -- it needs
    the same editor+ bar as files.routes.create_file, or a viewer could use
    it to write files despite having no write access anywhere else."""
    from app.db.control_plane import ControlPlaneSessionLocal
    from app.workspaces.models import WorkspaceMembership
    import asyncio

    email = "ai-jobs-viewer@example.com"
    client.post("/api/auth/register", json={"email": email, "password": "correcthorsebatterystaple", "display_name": "AI Jobs Viewer"})
    r = client.post("/api/auth/jwt/login", data={"username": email, "password": "correcthorsebatterystaple"})
    viewer_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    me = client.get("/api/users/me", headers=viewer_headers).json()

    async def _add_viewer_membership():
        async with ControlPlaneSessionLocal() as session:
            session.add(WorkspaceMembership(workspace_id=workspace_id, user_id=me["id"], role="viewer"))
            await session.commit()

    asyncio.run(_add_viewer_membership())

    r = client.post(
        f"/api/workspaces/{workspace_id}/ai/jobs",
        json={"task_type": "investigate", "input": {"question": "x"}},
        headers=viewer_headers,
    )
    assert r.status_code == 403

    r = client.post(
        f"/api/workspaces/{workspace_id}/ai/jobs",
        json={"task_type": "generate", "input": {"prompt": "x"}},
        headers=viewer_headers,
    )
    assert r.status_code == 200, r.text


def test_repair_job_uses_the_repair_task_model_route(client, auth_headers, workspace_id):
    r = client.post(
        f"/api/workspaces/{workspace_id}/ai/jobs",
        json={"task_type": "repair", "input": {"sql": "SELECT * FROM userz", "error_message": "no such table: userz"}},
        headers=auth_headers,
    )
    job_id = r.json()["id"]
    _run_pending_jobs()
    r = client.get(f"/api/workspaces/{workspace_id}/ai/jobs/{job_id}", headers=auth_headers)
    body = r.json()
    assert body["status"] == "done", body
    assert "repaired_sql" in body["result"]


def test_a_nonmember_cannot_see_another_workspaces_job(client, auth_headers, workspace_id):
    """Direct role-enforcement check, same shape as files/connections: a
    user with no membership at all gets 404, not someone else's job data."""
    email = "ai-jobs-outsider@example.com"
    client.post("/api/auth/register", json={"email": email, "password": "correcthorsebatterystaple", "display_name": "Outsider"})
    r = client.post("/api/auth/jwt/login", data={"username": email, "password": "correcthorsebatterystaple"})
    outsider_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = client.post(f"/api/workspaces/{workspace_id}/ai/jobs", json={"task_type": "generate", "input": {"prompt": "x"}}, headers=outsider_headers)
    assert r.status_code == 404


def test_model_for_task_falls_back_to_default_when_no_override_set():
    settings = get_settings()
    assert settings.model_for_task("generate") == settings.ollama_model
    assert settings.model_for_task("repair") == settings.ollama_model


def test_model_for_task_uses_override_when_set(monkeypatch):
    from app.core.config import Settings

    settings = Settings(ollama_model="mistral:7b", ollama_repair_model="llama3:latest")
    assert settings.model_for_task("repair") == "llama3:latest"
    assert settings.model_for_task("generate") == "mistral:7b"
