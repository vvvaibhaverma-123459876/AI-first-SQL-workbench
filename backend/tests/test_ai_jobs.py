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
