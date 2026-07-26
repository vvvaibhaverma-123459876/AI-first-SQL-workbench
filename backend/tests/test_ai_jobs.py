"""tests/test_ai_jobs.py

Phase 3 part A (v2 rebuild): the RQ job queue every AI call runs through,
plus per-task model configuration. Uses a real Redis (skipped if
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


def test_investigate_task_type_is_not_yet_creatable(client, auth_headers, workspace_id):
    """"investigate" is a valid AiJob.task_type at the model/DB level (a
    later phase's job function), but this phase never implemented a worker
    function for it -- the API must reject creating one, not queue a job
    that will sit forever with no function to process it."""
    r = client.post(
        f"/api/workspaces/{workspace_id}/ai/jobs",
        json={"task_type": "investigate", "input": {}},
        headers=auth_headers,
    )
    assert r.status_code == 400


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
