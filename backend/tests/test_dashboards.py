"""tests/test_dashboards.py

Phase 4a (v2 rebuild): named, workspace-scoped dashboards of pinned queries
with a chart type each. Every item requires a real connection in the same
workspace (no legacy-demo fallback, same posture as Phase 3c's Investigate
panel), and -- since dashboard tiles re-execute unattended on every reload
with no live human role check in the loop -- only provably read-only SQL is
ever accepted for a tile, checked at creation/update time via the same
sqlglot-based is_read_only_sql() Phase 2's own query route already uses.
"""
from __future__ import annotations

import asyncio
import sqlite3
import tempfile

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def auth_headers(client):
    email = "dashboards-owner@example.com"
    client.post("/api/auth/register", json={"email": email, "password": "correcthorsebatterystaple", "display_name": "Dashboards Owner"})
    r = client.post("/api/auth/jwt/login", data={"username": email, "password": "correcthorsebatterystaple"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def workspace_id(client, auth_headers):
    r = client.post("/api/workspaces", json={"name": "Dashboards Test Workspace"}, headers=auth_headers)
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
        json={"name": "dashboards-sqlite", "config": {"connector_type": "sqlite", "path": tmp.name}},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_create_list_and_get_a_dashboard_with_items(client, auth_headers, workspace_id, connection_id):
    r = client.post(f"/api/workspaces/{workspace_id}/dashboards", json={"name": "Widgets Overview"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    dashboard_id = r.json()["id"]

    r = client.get(f"/api/workspaces/{workspace_id}/dashboards", headers=auth_headers)
    assert r.status_code == 200
    assert any(d["id"] == dashboard_id for d in r.json())

    for i, label in enumerate(["Widget count", "Widgets by label", "Widget list"]):
        r = client.post(
            f"/api/workspaces/{workspace_id}/dashboards/{dashboard_id}/items",
            json={"connection_id": connection_id, "title": label, "sql": "SELECT * FROM widgets", "chart_type": "table", "width": 1},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text

    r = client.get(f"/api/workspaces/{workspace_id}/dashboards/{dashboard_id}", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Widgets Overview"
    assert len(body["items"]) == 3
    # New items append at the end -- sort_order should already be in
    # creation order without any explicit reordering.
    assert [item["sort_order"] for item in body["items"]] == sorted(item["sort_order"] for item in body["items"])


def test_duplicate_dashboard_name_in_the_same_workspace_is_rejected(client, auth_headers, workspace_id):
    client.post(f"/api/workspaces/{workspace_id}/dashboards", json={"name": "Dup Dashboard"}, headers=auth_headers)
    r = client.post(f"/api/workspaces/{workspace_id}/dashboards", json={"name": "Dup Dashboard"}, headers=auth_headers)
    assert r.status_code == 409


def test_a_non_read_only_sql_tile_is_rejected_at_creation_not_left_pinned(client, auth_headers, workspace_id, connection_id):
    """The core security check this phase's advisor review flagged as
    blocking: a dashboard tile runs unattended on every reload, so it must
    never accept SQL that isn't provably read-only, regardless of the
    creator's own role."""
    r = client.post(f"/api/workspaces/{workspace_id}/dashboards", json={"name": "Write Attempt Dashboard"}, headers=auth_headers)
    dashboard_id = r.json()["id"]

    r = client.post(
        f"/api/workspaces/{workspace_id}/dashboards/{dashboard_id}/items",
        json={"connection_id": connection_id, "title": "Bad tile", "sql": "DELETE FROM widgets", "chart_type": "table"},
        headers=auth_headers,
    )
    assert r.status_code == 400, r.text

    r = client.get(f"/api/workspaces/{workspace_id}/dashboards/{dashboard_id}", headers=auth_headers)
    assert r.json()["items"] == []


def test_an_invalid_chart_type_is_rejected(client, auth_headers, workspace_id, connection_id):
    r = client.post(f"/api/workspaces/{workspace_id}/dashboards", json={"name": "Bad Chart Type Dashboard"}, headers=auth_headers)
    dashboard_id = r.json()["id"]
    r = client.post(
        f"/api/workspaces/{workspace_id}/dashboards/{dashboard_id}/items",
        json={"connection_id": connection_id, "title": "t", "sql": "SELECT 1", "chart_type": "not-a-real-type"},
        headers=auth_headers,
    )
    assert r.status_code == 400


def test_a_connection_from_another_workspace_cannot_be_pinned(client, auth_headers, workspace_id, connection_id):
    r = client.post("/api/workspaces", json={"name": "Other Workspace"}, headers=auth_headers)
    other_workspace_id = r.json()["id"]
    r = client.post(f"/api/workspaces/{other_workspace_id}/dashboards", json={"name": "Cross-Workspace Dashboard"}, headers=auth_headers)
    dashboard_id = r.json()["id"]

    r = client.post(
        f"/api/workspaces/{other_workspace_id}/dashboards/{dashboard_id}/items",
        json={"connection_id": connection_id, "title": "t", "sql": "SELECT 1", "chart_type": "table"},
        headers=auth_headers,
    )
    assert r.status_code == 400


def test_update_item_reorders_and_resizes_and_still_blocks_a_write(client, auth_headers, workspace_id, connection_id):
    r = client.post(f"/api/workspaces/{workspace_id}/dashboards", json={"name": "Update Dashboard"}, headers=auth_headers)
    dashboard_id = r.json()["id"]
    r = client.post(
        f"/api/workspaces/{workspace_id}/dashboards/{dashboard_id}/items",
        json={"connection_id": connection_id, "title": "Original", "sql": "SELECT * FROM widgets", "chart_type": "table"},
        headers=auth_headers,
    )
    item_id = r.json()["id"]

    r = client.patch(
        f"/api/workspaces/{workspace_id}/dashboards/{dashboard_id}/items/{item_id}",
        json={"width": 2, "sort_order": 5, "chart_type": "bar", "x_field": "label", "y_fields": ["id"]},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["width"] == 2
    assert body["sort_order"] == 5
    assert body["chart_type"] == "bar"
    assert body["x_field"] == "label"

    r = client.patch(
        f"/api/workspaces/{workspace_id}/dashboards/{dashboard_id}/items/{item_id}",
        json={"sql": "DROP TABLE widgets"},
        headers=auth_headers,
    )
    assert r.status_code == 400
    # Rejected update must not have partially applied.
    r = client.get(f"/api/workspaces/{workspace_id}/dashboards/{dashboard_id}", headers=auth_headers)
    assert r.json()["items"][0]["sql"] == "SELECT * FROM widgets"


def test_delete_item_then_delete_dashboard(client, auth_headers, workspace_id, connection_id):
    r = client.post(f"/api/workspaces/{workspace_id}/dashboards", json={"name": "Delete Me Dashboard"}, headers=auth_headers)
    dashboard_id = r.json()["id"]
    r = client.post(
        f"/api/workspaces/{workspace_id}/dashboards/{dashboard_id}/items",
        json={"connection_id": connection_id, "title": "t", "sql": "SELECT 1", "chart_type": "table"},
        headers=auth_headers,
    )
    item_id = r.json()["id"]

    r = client.delete(f"/api/workspaces/{workspace_id}/dashboards/{dashboard_id}/items/{item_id}", headers=auth_headers)
    assert r.status_code == 204
    r = client.get(f"/api/workspaces/{workspace_id}/dashboards/{dashboard_id}", headers=auth_headers)
    assert r.json()["items"] == []

    r = client.delete(f"/api/workspaces/{workspace_id}/dashboards/{dashboard_id}", headers=auth_headers)
    assert r.status_code == 204
    r = client.get(f"/api/workspaces/{workspace_id}/dashboards/{dashboard_id}", headers=auth_headers)
    assert r.status_code == 404


def test_a_viewer_can_read_a_dashboard_but_cannot_create_or_pin_items(client, auth_headers, workspace_id, connection_id):
    from app.db.control_plane import ControlPlaneSessionLocal
    from app.workspaces.models import WorkspaceMembership

    email = "dashboards-viewer@example.com"
    client.post("/api/auth/register", json={"email": email, "password": "correcthorsebatterystaple", "display_name": "Dashboards Viewer"})
    r = client.post("/api/auth/jwt/login", data={"username": email, "password": "correcthorsebatterystaple"})
    viewer_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    me = client.get("/api/users/me", headers=viewer_headers).json()

    async def _add_viewer_membership():
        async with ControlPlaneSessionLocal() as session:
            session.add(WorkspaceMembership(workspace_id=workspace_id, user_id=me["id"], role="viewer"))
            await session.commit()

    asyncio.run(_add_viewer_membership())

    r = client.post(f"/api/workspaces/{workspace_id}/dashboards", json={"name": "Owner Dashboard For Viewer Test"}, headers=auth_headers)
    dashboard_id = r.json()["id"]

    r = client.get(f"/api/workspaces/{workspace_id}/dashboards/{dashboard_id}", headers=viewer_headers)
    assert r.status_code == 200

    r = client.post(f"/api/workspaces/{workspace_id}/dashboards", json={"name": "Viewer Should Not Create"}, headers=viewer_headers)
    assert r.status_code == 403

    r = client.post(
        f"/api/workspaces/{workspace_id}/dashboards/{dashboard_id}/items",
        json={"connection_id": connection_id, "title": "t", "sql": "SELECT 1", "chart_type": "table"},
        headers=viewer_headers,
    )
    assert r.status_code == 403
