"""tests/test_sharing.py

Phase 5a (v2 rebuild): additive external sharing. User-decided model
(explicitly put to the user via AskUserQuestion, since the phase's own
spec was internally ambiguous about whether sharing changes default
workspace visibility): workspace membership visibility is completely
UNCHANGED by this phase -- every member still sees every file/dashboard
in their workspace, same as Phases 0-4. A ResourceShare instead grants a
SPECIFIC resource to a user who is NOT necessarily a workspace member,
readable only through brand-new top-level /shared/... routes that check
nothing but the share grant.

The single most important assertion in this file, repeated in the first
real test below: account 2 must be unable to see the resource via EITHER
route before the share exists, and after sharing must be able to read it
via /shared/... while STILL being blocked from the workspace-scoped
route. That's what proves the share grant -- not latent workspace access
-- is what's doing the work.
"""
from __future__ import annotations

import sqlite3
import tempfile

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _register_and_login(client, email: str) -> dict:
    client.post("/api/auth/register", json={"email": email, "password": "correcthorsebatterystaple", "display_name": email.split("@")[0]})
    r = client.post("/api/auth/jwt/login", data={"username": email, "password": "correcthorsebatterystaple"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def owner_headers(client):
    return _register_and_login(client, "sharing-owner@example.com")


@pytest.fixture(scope="module")
def recipient_headers(client):
    """A user with NO membership in owner_headers's workspace at all --
    this is the account every "before sharing" assertion checks against."""
    return _register_and_login(client, "sharing-recipient@example.com")


@pytest.fixture(scope="module")
def workspace_id(client, owner_headers):
    r = client.post("/api/workspaces", json={"name": "Sharing Test Workspace"}, headers=owner_headers)
    return r.json()["id"]


@pytest.fixture(scope="module")
def connection_id(client, owner_headers, workspace_id):
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    conn = sqlite3.connect(tmp.name)
    conn.execute("CREATE TABLE widgets (id INTEGER PRIMARY KEY, label TEXT NOT NULL)")
    conn.execute("INSERT INTO widgets (label) VALUES ('alpha'), ('beta')")
    conn.commit()
    conn.close()
    r = client.post(
        f"/api/workspaces/{workspace_id}/connections",
        json={"name": "sharing-sqlite", "config": {"connector_type": "sqlite", "path": tmp.name}},
        headers=owner_headers,
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_a_file_is_invisible_to_a_non_member_until_shared_then_readable_but_still_workspace_gated(client, owner_headers, recipient_headers, workspace_id):
    r = client.post(f"/api/workspaces/{workspace_id}/files", json={"name": "shared.sql", "content": "select 1"}, headers=owner_headers)
    assert r.status_code == 200, r.text
    file_id = r.json()["id"]

    # Before sharing: recipient has no access via either route.
    r = client.get(f"/api/shared/files/{file_id}", headers=recipient_headers)
    assert r.status_code == 404
    r = client.get(f"/api/workspaces/{workspace_id}/files/{file_id}", headers=recipient_headers)
    assert r.status_code == 404

    r = client.post(f"/api/workspaces/{workspace_id}/files/{file_id}/shares", json={"email": "sharing-recipient@example.com", "role": "viewer"}, headers=owner_headers)
    assert r.status_code == 200, r.text
    assert r.json()["shared_with_email"] == "sharing-recipient@example.com"
    assert r.json()["role"] == "viewer"

    # After sharing: the share route works...
    r = client.get(f"/api/shared/files/{file_id}", headers=recipient_headers)
    assert r.status_code == 200, r.text
    assert r.json()["content"] == "select 1"
    assert r.json()["role"] == "viewer"

    # ...but the load-bearing assertion: the workspace-scoped route STILL
    # 404s for this user. If this failed, the share would be a symptom of
    # some other (broken) access path, not proof sharing itself works.
    r = client.get(f"/api/workspaces/{workspace_id}/files/{file_id}", headers=recipient_headers)
    assert r.status_code == 404


def test_viewer_shared_file_cannot_be_patched_editor_shared_file_can(client, owner_headers, recipient_headers, workspace_id):
    r = client.post(f"/api/workspaces/{workspace_id}/files", json={"name": "editable.sql", "content": "v1"}, headers=owner_headers)
    file_id = r.json()["id"]
    client.post(f"/api/workspaces/{workspace_id}/files/{file_id}/shares", json={"email": "sharing-recipient@example.com", "role": "viewer"}, headers=owner_headers)

    r = client.patch(f"/api/shared/files/{file_id}", json={"content": "v2 from viewer"}, headers=recipient_headers)
    assert r.status_code == 403

    r = client.post(f"/api/workspaces/{workspace_id}/files/{file_id}/shares", json={"email": "sharing-recipient@example.com", "role": "editor"}, headers=owner_headers)
    assert r.status_code == 200  # re-sharing updates the role rather than erroring

    r = client.patch(f"/api/shared/files/{file_id}", json={"content": "v2 from editor"}, headers=recipient_headers)
    assert r.status_code == 200, r.text
    assert r.json()["content"] == "v2 from editor"

    r = client.get(f"/api/workspaces/{workspace_id}/files/{file_id}", headers=owner_headers)
    assert r.json()["content"] == "v2 from editor"


def test_sharing_to_an_email_with_no_account_is_rejected(client, owner_headers, workspace_id):
    r = client.post(f"/api/workspaces/{workspace_id}/files", json={"name": "no-account.sql", "content": "x"}, headers=owner_headers)
    file_id = r.json()["id"]
    r = client.post(f"/api/workspaces/{workspace_id}/files/{file_id}/shares", json={"email": "nobody-real@example.com", "role": "viewer"}, headers=owner_headers)
    assert r.status_code == 404


def test_a_viewer_of_the_workspace_cannot_share_a_file_editor_can(client, owner_headers, workspace_id):
    import asyncio

    from app.db.control_plane import ControlPlaneSessionLocal
    from app.workspaces.models import WorkspaceMembership

    viewer_headers = _register_and_login(client, "sharing-workspace-viewer@example.com")
    me = client.get("/api/users/me", headers=viewer_headers).json()

    async def _add_viewer_membership():
        async with ControlPlaneSessionLocal() as session:
            session.add(WorkspaceMembership(workspace_id=workspace_id, user_id=me["id"], role="viewer"))
            await session.commit()

    asyncio.run(_add_viewer_membership())

    r = client.post(f"/api/workspaces/{workspace_id}/files", json={"name": "viewer-share-test.sql", "content": "x"}, headers=owner_headers)
    file_id = r.json()["id"]

    r = client.post(f"/api/workspaces/{workspace_id}/files/{file_id}/shares", json={"email": "sharing-recipient@example.com", "role": "viewer"}, headers=viewer_headers)
    assert r.status_code == 403


def test_revoking_a_share_removes_access(client, owner_headers, recipient_headers, workspace_id):
    r = client.post(f"/api/workspaces/{workspace_id}/files", json={"name": "revoke-me.sql", "content": "x"}, headers=owner_headers)
    file_id = r.json()["id"]
    r = client.post(f"/api/workspaces/{workspace_id}/files/{file_id}/shares", json={"email": "sharing-recipient@example.com", "role": "viewer"}, headers=owner_headers)
    share_id = r.json()["id"]

    r = client.get(f"/api/shared/files/{file_id}", headers=recipient_headers)
    assert r.status_code == 200

    r = client.delete(f"/api/workspaces/{workspace_id}/files/{file_id}/shares/{share_id}", headers=owner_headers)
    assert r.status_code == 204

    r = client.get(f"/api/shared/files/{file_id}", headers=recipient_headers)
    assert r.status_code == 404


def test_deleting_a_shared_file_removes_it_from_shared_with_me_without_erroring(client, owner_headers, recipient_headers, workspace_id):
    r = client.post(f"/api/workspaces/{workspace_id}/files", json={"name": "delete-me.sql", "content": "x"}, headers=owner_headers)
    file_id = r.json()["id"]
    client.post(f"/api/workspaces/{workspace_id}/files/{file_id}/shares", json={"email": "sharing-recipient@example.com", "role": "viewer"}, headers=owner_headers)

    r = client.get("/api/shared-with-me", headers=recipient_headers)
    assert any(item["resource_id"] == file_id for item in r.json())

    r = client.delete(f"/api/workspaces/{workspace_id}/files/{file_id}", headers=owner_headers)
    assert r.status_code == 204

    # The cascade-delete of the ResourceShare row (files/service.py's
    # delete_file) is what's under test -- and even if it were somehow
    # missed, list_shared_with_me's defensive orphan-filter must still
    # return 200 with the row simply absent, not 500.
    r = client.get("/api/shared-with-me", headers=recipient_headers)
    assert r.status_code == 200
    assert all(item["resource_id"] != file_id for item in r.json())
    r = client.get(f"/api/shared/files/{file_id}", headers=recipient_headers)
    assert r.status_code == 404


def test_dashboard_sharing_rejects_editor_role(client, owner_headers, workspace_id, connection_id):
    r = client.post(f"/api/workspaces/{workspace_id}/dashboards", json={"name": "Sharing Test Dashboard"}, headers=owner_headers)
    dashboard_id = r.json()["id"]
    r = client.post(f"/api/workspaces/{workspace_id}/dashboards/{dashboard_id}/shares", json={"email": "sharing-recipient@example.com", "role": "editor"}, headers=owner_headers)
    assert r.status_code == 400


def test_a_shared_dashboards_tile_actually_executes_and_returns_real_rows(client, owner_headers, recipient_headers, workspace_id, connection_id):
    r = client.post(f"/api/workspaces/{workspace_id}/dashboards", json={"name": "Shared Widgets Dashboard"}, headers=owner_headers)
    dashboard_id = r.json()["id"]
    r = client.post(
        f"/api/workspaces/{workspace_id}/dashboards/{dashboard_id}/items",
        json={"connection_id": connection_id, "title": "All widgets", "sql": "SELECT * FROM widgets", "chart_type": "table"},
        headers=owner_headers,
    )
    item_id = r.json()["id"]

    r = client.get(f"/api/shared/dashboards/{dashboard_id}", headers=recipient_headers)
    assert r.status_code == 404  # not shared yet

    client.post(f"/api/workspaces/{workspace_id}/dashboards/{dashboard_id}/shares", json={"email": "sharing-recipient@example.com", "role": "viewer"}, headers=owner_headers)

    r = client.get(f"/api/shared/dashboards/{dashboard_id}", headers=recipient_headers)
    assert r.status_code == 200, r.text
    assert len(r.json()["items"]) == 1
    assert r.json()["items"][0]["id"] == item_id

    r = client.post(f"/api/shared/dashboards/{dashboard_id}/items/{item_id}/run", headers=recipient_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["row_count"] == 2
    assert body["columns"] == ["id", "label"]

    # And the workspace-scoped dashboard route is still gated, same as files.
    r = client.get(f"/api/workspaces/{workspace_id}/dashboards/{dashboard_id}", headers=recipient_headers)
    assert r.status_code == 404


def test_running_an_item_from_a_different_dashboard_is_rejected_not_leaked(client, owner_headers, recipient_headers, workspace_id, connection_id):
    """The IDOR the design review specifically flagged as a blocking risk
    before this code was written: a share on dashboard A must not let a
    user run an item_id that actually belongs to dashboard B, even though
    the endpoint URL names dashboard A."""
    r = client.post(f"/api/workspaces/{workspace_id}/dashboards", json={"name": "IDOR Dashboard A"}, headers=owner_headers)
    dashboard_a_id = r.json()["id"]
    client.post(f"/api/workspaces/{workspace_id}/dashboards/{dashboard_a_id}/shares", json={"email": "sharing-recipient@example.com", "role": "viewer"}, headers=owner_headers)

    r = client.post(f"/api/workspaces/{workspace_id}/dashboards", json={"name": "IDOR Dashboard B (not shared)"}, headers=owner_headers)
    dashboard_b_id = r.json()["id"]
    r = client.post(
        f"/api/workspaces/{workspace_id}/dashboards/{dashboard_b_id}/items",
        json={"connection_id": connection_id, "title": "B's secret tile", "sql": "SELECT * FROM widgets", "chart_type": "table"},
        headers=owner_headers,
    )
    item_from_b_id = r.json()["id"]

    # dashboard_a_id in the URL (which IS shared), item_id from dashboard B
    # (which is NOT) -- must 404, not execute dashboard B's connection query.
    r = client.post(f"/api/shared/dashboards/{dashboard_a_id}/items/{item_from_b_id}/run", headers=recipient_headers)
    assert r.status_code == 404


def test_shared_dashboard_tile_run_re_validates_read_only_sql_at_execution_time(client, owner_headers, recipient_headers, workspace_id, connection_id):
    """Same "never trust stored SQL without re-checking at execution"
    posture Phase 4b established for scheduled queries -- simulated here
    by mutating a tile's stored SQL directly in the DB (bypassing the
    creation-time check), the same technique used to prove defense in
    depth rather than just first-line validation."""
    import asyncio
    import uuid as uuid_module

    from app.dashboards.models import DashboardItem
    from app.db.control_plane import ControlPlaneSessionLocal

    r = client.post(f"/api/workspaces/{workspace_id}/dashboards", json={"name": "Mutated SQL Dashboard"}, headers=owner_headers)
    dashboard_id = r.json()["id"]
    r = client.post(
        f"/api/workspaces/{workspace_id}/dashboards/{dashboard_id}/items",
        json={"connection_id": connection_id, "title": "Innocent at creation", "sql": "SELECT * FROM widgets", "chart_type": "table"},
        headers=owner_headers,
    )
    item_id = r.json()["id"]
    client.post(f"/api/workspaces/{workspace_id}/dashboards/{dashboard_id}/shares", json={"email": "sharing-recipient@example.com", "role": "viewer"}, headers=owner_headers)

    async def _mutate_sql():
        async with ControlPlaneSessionLocal() as session:
            item = await session.get(DashboardItem, uuid_module.UUID(item_id))
            item.sql = "DELETE FROM widgets"
            await session.commit()

    asyncio.run(_mutate_sql())

    r = client.post(f"/api/shared/dashboards/{dashboard_id}/items/{item_id}/run", headers=recipient_headers)
    assert r.status_code == 400
