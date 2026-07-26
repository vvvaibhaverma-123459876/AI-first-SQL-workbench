"""tests/test_scheduled_queries.py

Phase 4b (v2 rebuild): scheduled queries. The phase's literal acceptance
bar is "a scheduled query actually fires on schedule and notifies" --
proven here two ways, deliberately avoiding a flaky wall-clock cron wait:
1. Pure cron-timing correctness is tests/test_scheduled_queries_timing.py.
2. The job -> webhook path is proven by actually running the job (via the
   "run now" manual-trigger endpoint, same precedent as Phase 3d's
   embeddings-refresh endpoint) against a REAL local HTTP listener and
   inspecting the request it actually received -- not by waiting for a
   real cron tick.
The tick()-level double-fire prevention (the correctness issue the
advisor's design review flagged as blocking before any code was written)
is proven directly against real Redis: two ticks on one due row must
enqueue exactly once.
"""
from __future__ import annotations

import http.server
import json
import sqlite3
import tempfile
import threading

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def auth_headers(client):
    email = "scheduled-queries-owner@example.com"
    client.post("/api/auth/register", json={"email": email, "password": "correcthorsebatterystaple", "display_name": "Scheduled Queries Owner"})
    r = client.post("/api/auth/jwt/login", data={"username": email, "password": "correcthorsebatterystaple"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def workspace_id(client, auth_headers):
    r = client.post("/api/workspaces", json={"name": "Scheduled Queries Test Workspace"}, headers=auth_headers)
    return r.json()["id"]


@pytest.fixture(scope="module")
def connection_id(client, auth_headers, workspace_id):
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    conn = sqlite3.connect(tmp.name)
    conn.execute("CREATE TABLE widgets (id INTEGER PRIMARY KEY, label TEXT NOT NULL)")
    conn.execute("INSERT INTO widgets (label) VALUES ('alpha'), ('beta'), ('gamma')")
    conn.commit()
    conn.close()
    r = client.post(
        f"/api/workspaces/{workspace_id}/connections",
        json={"name": "scheduled-queries-sqlite", "config": {"connector_type": "sqlite", "path": tmp.name}},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_create_list_get_update_delete_scheduled_query(client, auth_headers, workspace_id, connection_id):
    r = client.post(
        f"/api/workspaces/{workspace_id}/scheduled-queries",
        json={"connection_id": connection_id, "name": "Widget count", "sql": "SELECT * FROM widgets", "cron_expression": "*/5 * * * *"},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    row = r.json()
    assert row["is_active"] is True
    assert row["condition"] == "always"
    scheduled_id = row["id"]

    r = client.get(f"/api/workspaces/{workspace_id}/scheduled-queries", headers=auth_headers)
    assert any(s["id"] == scheduled_id for s in r.json())

    r = client.get(f"/api/workspaces/{workspace_id}/scheduled-queries/{scheduled_id}", headers=auth_headers)
    assert r.status_code == 200

    r = client.patch(f"/api/workspaces/{workspace_id}/scheduled-queries/{scheduled_id}", json={"is_active": False, "cron_expression": "0 * * * *"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["is_active"] is False
    assert r.json()["cron_expression"] == "0 * * * *"

    r = client.delete(f"/api/workspaces/{workspace_id}/scheduled-queries/{scheduled_id}", headers=auth_headers)
    assert r.status_code == 204
    r = client.get(f"/api/workspaces/{workspace_id}/scheduled-queries/{scheduled_id}", headers=auth_headers)
    assert r.status_code == 404


def test_a_non_read_only_sql_schedule_is_rejected_at_creation(client, auth_headers, workspace_id, connection_id):
    r = client.post(
        f"/api/workspaces/{workspace_id}/scheduled-queries",
        json={"connection_id": connection_id, "name": "Bad", "sql": "DELETE FROM widgets", "cron_expression": "*/5 * * * *"},
        headers=auth_headers,
    )
    assert r.status_code == 400


def test_a_non_read_only_sql_update_is_rejected_and_does_not_partially_apply(client, auth_headers, workspace_id, connection_id):
    r = client.post(
        f"/api/workspaces/{workspace_id}/scheduled-queries",
        json={"connection_id": connection_id, "name": "Update Reject Test", "sql": "SELECT * FROM widgets", "cron_expression": "*/5 * * * *"},
        headers=auth_headers,
    )
    scheduled_id = r.json()["id"]
    r = client.patch(f"/api/workspaces/{workspace_id}/scheduled-queries/{scheduled_id}", json={"sql": "DROP TABLE widgets"}, headers=auth_headers)
    assert r.status_code == 400
    r = client.get(f"/api/workspaces/{workspace_id}/scheduled-queries/{scheduled_id}", headers=auth_headers)
    assert r.json()["sql"] == "SELECT * FROM widgets"


def test_an_invalid_cron_expression_is_rejected(client, auth_headers, workspace_id, connection_id):
    r = client.post(
        f"/api/workspaces/{workspace_id}/scheduled-queries",
        json={"connection_id": connection_id, "name": "Bad Cron", "sql": "SELECT 1", "cron_expression": "not a cron"},
        headers=auth_headers,
    )
    assert r.status_code == 400


def test_threshold_condition_without_a_condition_value_is_rejected(client, auth_headers, workspace_id, connection_id):
    r = client.post(
        f"/api/workspaces/{workspace_id}/scheduled-queries",
        json={"connection_id": connection_id, "name": "No Threshold", "sql": "SELECT 1", "cron_expression": "*/5 * * * *", "condition": "threshold"},
        headers=auth_headers,
    )
    assert r.status_code == 400


def test_a_connection_from_another_workspace_cannot_be_scheduled(client, auth_headers, workspace_id, connection_id):
    r = client.post("/api/workspaces", json={"name": "Other Scheduled Queries Workspace"}, headers=auth_headers)
    other_workspace_id = r.json()["id"]
    r = client.post(
        f"/api/workspaces/{other_workspace_id}/scheduled-queries",
        json={"connection_id": connection_id, "name": "Cross-workspace", "sql": "SELECT 1", "cron_expression": "*/5 * * * *"},
        headers=auth_headers,
    )
    assert r.status_code == 400


def test_a_viewer_can_read_but_cannot_create_or_run(client, auth_headers, workspace_id, connection_id):
    import asyncio

    from app.db.control_plane import ControlPlaneSessionLocal
    from app.workspaces.models import WorkspaceMembership

    email = "scheduled-queries-viewer@example.com"
    client.post("/api/auth/register", json={"email": email, "password": "correcthorsebatterystaple", "display_name": "Scheduled Queries Viewer"})
    r = client.post("/api/auth/jwt/login", data={"username": email, "password": "correcthorsebatterystaple"})
    viewer_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    me = client.get("/api/users/me", headers=viewer_headers).json()

    async def _add_viewer_membership():
        async with ControlPlaneSessionLocal() as session:
            session.add(WorkspaceMembership(workspace_id=workspace_id, user_id=me["id"], role="viewer"))
            await session.commit()

    asyncio.run(_add_viewer_membership())

    r = client.post(
        f"/api/workspaces/{workspace_id}/scheduled-queries",
        json={"connection_id": connection_id, "name": "Owner's schedule", "sql": "SELECT 1", "cron_expression": "*/5 * * * *"},
        headers=auth_headers,
    )
    scheduled_id = r.json()["id"]

    r = client.get(f"/api/workspaces/{workspace_id}/scheduled-queries/{scheduled_id}", headers=viewer_headers)
    assert r.status_code == 200

    r = client.post(
        f"/api/workspaces/{workspace_id}/scheduled-queries",
        json={"connection_id": connection_id, "name": "Viewer Should Not Create", "sql": "SELECT 1", "cron_expression": "*/5 * * * *"},
        headers=viewer_headers,
    )
    assert r.status_code == 403

    r = client.post(f"/api/workspaces/{workspace_id}/scheduled-queries/{scheduled_id}/run", headers=viewer_headers)
    assert r.status_code == 403


def test_run_now_executes_the_query_and_reports_no_channel_configured(client, auth_headers, workspace_id, connection_id):
    r = client.post(
        f"/api/workspaces/{workspace_id}/scheduled-queries",
        json={"connection_id": connection_id, "name": "Run Now Test", "sql": "SELECT * FROM widgets", "cron_expression": "*/5 * * * *"},
        headers=auth_headers,
    )
    scheduled_id = r.json()["id"]

    r = client.post(f"/api/workspaces/{workspace_id}/scheduled-queries/{scheduled_id}/run", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["row_count"] == 3
    assert "no webhook/email configured" in body["status"]

    r = client.get(f"/api/workspaces/{workspace_id}/scheduled-queries/{scheduled_id}", headers=auth_headers)
    row = r.json()
    assert row["last_row_count"] == 3
    assert row["last_run_at"] is not None
    assert row["last_notified_at"] is None  # nothing was actually sent


class _CapturingWebhookHandler(http.server.BaseHTTPRequestHandler):
    received: list[dict] = []

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        _CapturingWebhookHandler.received.append(json.loads(body))
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):  # noqa: A002
        pass  # keep test output quiet


def test_run_now_fires_a_real_webhook_with_the_correct_payload(client, auth_headers, workspace_id, connection_id):
    _CapturingWebhookHandler.received = []
    server = http.server.HTTPServer(("127.0.0.1", 0), _CapturingWebhookHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        r = client.post(
            f"/api/workspaces/{workspace_id}/scheduled-queries",
            json={
                "connection_id": connection_id,
                "name": "Webhook Test",
                "sql": "SELECT * FROM widgets",
                "cron_expression": "*/5 * * * *",
                "notify_webhook_url": f"http://127.0.0.1:{port}/hook",
            },
            headers=auth_headers,
        )
        scheduled_id = r.json()["id"]

        r = client.post(f"/api/workspaces/{workspace_id}/scheduled-queries/{scheduled_id}/run", headers=auth_headers)
        assert r.status_code == 200, r.text
        assert "notified via webhook" in r.json()["status"]

        assert len(_CapturingWebhookHandler.received) == 1
        payload = _CapturingWebhookHandler.received[0]
        assert payload["name"] == "Webhook Test"
        assert payload["row_count"] == 3
        assert payload["columns"] == ["id", "label"]
        assert len(payload["sample_rows"]) == 3

        r = client.get(f"/api/workspaces/{workspace_id}/scheduled-queries/{scheduled_id}", headers=auth_headers)
        assert r.json()["last_notified_at"] is not None
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_tick_enqueues_a_due_schedule_exactly_once_across_two_ticks(client, auth_headers, workspace_id, connection_id):
    """The blocking correctness issue the advisor flagged before any code
    was written: a 30s-interval tick must not re-enqueue a row whose job
    hasn't run (and therefore hasn't updated last_run_at) yet. Proven
    directly against real Redis -- skipped if unreachable, same pattern as
    test_ai_jobs.py."""
    from redis import Redis
    from redis.exceptions import ConnectionError as RedisConnectionError

    from app.core.config import get_settings

    try:
        Redis.from_url(get_settings().redis_url).ping()
    except RedisConnectionError:
        pytest.skip("Redis not reachable at REDIS_URL -- set it to a running Redis to run this test")

    import uuid as uuid_module
    from datetime import datetime, timedelta

    from app.db.control_plane_sync import get_sync_session
    from app.scheduled_queries.models import ScheduledQuery
    from app.scheduled_queries.timing import tick

    r = client.post(
        f"/api/workspaces/{workspace_id}/scheduled-queries",
        json={"connection_id": connection_id, "name": "Tick Double-Fire Test", "sql": "SELECT 1", "cron_expression": "* * * * *"},
        headers=auth_headers,
    )
    scheduled_id = r.json()["id"]
    target_id = uuid_module.UUID(scheduled_id)

    session = get_sync_session()
    try:
        # croniter's next_due() is always strictly in the future relative
        # to its anchor, so a just-created row's anchor (created_at, since
        # last_enqueued_at is still unset) is never itself due -- backdate
        # it so this test doesn't depend on however much real wall-clock
        # time happens to elapse during the test run.
        row = session.get(ScheduledQuery, target_id)
        row.created_at = datetime.utcnow() - timedelta(minutes=2)
        session.commit()

        # Other pre-existing schedules in this same shared test DB (from
        # earlier tests in this module) are real too, but their cron
        # intervals (*/5, hourly) and recent created_at mean they won't be
        # due yet -- these assertions only care about OUR row regardless.
        first = tick(session)
        second = tick(session)
    finally:
        session.close()

    assert target_id in first
    assert target_id not in second, "the second tick re-enqueued a row the first tick already picked up"
