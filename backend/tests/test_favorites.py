"""tests/test_favorites.py

Phase 5b (v2 rebuild): favorites. A purely personal bookmark on a file or
dashboard the user already has access to -- unlike sharing (Phase 5a) this
changes no one's visibility, so there's no "before/after" access story to
prove here. What matters instead: favoriting is per-user (one member's
favorite doesn't show up for another), idempotent (double-favorite /
double-unfavorite don't error or duplicate), and the polymorphic
resource_id cascade-deletes cleanly (mirrors app.sharing's same risk)."""
from __future__ import annotations

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
    return _register_and_login(client, "favorites-owner@example.com")


@pytest.fixture(scope="module")
def workspace_id(client, owner_headers):
    r = client.post("/api/workspaces", json={"name": "Favorites Test Workspace"}, headers=owner_headers)
    return r.json()["id"]


def test_favoriting_a_file_makes_it_appear_in_the_list(client, owner_headers, workspace_id):
    r = client.post(f"/api/workspaces/{workspace_id}/files", json={"name": "fav.sql", "content": "select 1"}, headers=owner_headers)
    file_id = r.json()["id"]

    r = client.get(f"/api/workspaces/{workspace_id}/favorites", headers=owner_headers)
    assert r.status_code == 200
    assert all(item["resource_id"] != file_id for item in r.json())

    r = client.put(f"/api/workspaces/{workspace_id}/files/{file_id}/favorite", headers=owner_headers)
    assert r.status_code == 200, r.text
    assert r.json()["resource_type"] == "file"
    assert r.json()["resource_id"] == file_id

    r = client.get(f"/api/workspaces/{workspace_id}/favorites", headers=owner_headers)
    assert any(item["resource_id"] == file_id and item["resource_name"] == "fav.sql" for item in r.json())


def test_favoriting_twice_does_not_duplicate(client, owner_headers, workspace_id):
    r = client.post(f"/api/workspaces/{workspace_id}/files", json={"name": "fav-twice.sql", "content": "x"}, headers=owner_headers)
    file_id = r.json()["id"]

    r1 = client.put(f"/api/workspaces/{workspace_id}/files/{file_id}/favorite", headers=owner_headers)
    r2 = client.put(f"/api/workspaces/{workspace_id}/files/{file_id}/favorite", headers=owner_headers)
    assert r1.json()["id"] == r2.json()["id"]  # same row, not a new one

    r = client.get(f"/api/workspaces/{workspace_id}/favorites", headers=owner_headers)
    assert len([item for item in r.json() if item["resource_id"] == file_id]) == 1


def test_unfavoriting_removes_it_and_is_idempotent(client, owner_headers, workspace_id):
    r = client.post(f"/api/workspaces/{workspace_id}/files", json={"name": "unfav.sql", "content": "x"}, headers=owner_headers)
    file_id = r.json()["id"]
    client.put(f"/api/workspaces/{workspace_id}/files/{file_id}/favorite", headers=owner_headers)

    r = client.delete(f"/api/workspaces/{workspace_id}/files/{file_id}/favorite", headers=owner_headers)
    assert r.status_code == 204
    r = client.get(f"/api/workspaces/{workspace_id}/favorites", headers=owner_headers)
    assert all(item["resource_id"] != file_id for item in r.json())

    # Unfavoriting something already not favorited is a no-op, not a 404.
    r = client.delete(f"/api/workspaces/{workspace_id}/files/{file_id}/favorite", headers=owner_headers)
    assert r.status_code == 204


def test_favorites_are_per_user_not_shared_across_the_workspace(client, owner_headers, workspace_id):
    import asyncio

    from app.db.control_plane import ControlPlaneSessionLocal
    from app.workspaces.models import WorkspaceMembership

    other_headers = _register_and_login(client, "favorites-other-member@example.com")
    me = client.get("/api/users/me", headers=other_headers).json()

    async def _add_membership():
        async with ControlPlaneSessionLocal() as session:
            session.add(WorkspaceMembership(workspace_id=workspace_id, user_id=me["id"], role="viewer"))
            await session.commit()

    asyncio.run(_add_membership())

    r = client.post(f"/api/workspaces/{workspace_id}/files", json={"name": "owner-only-fav.sql", "content": "x"}, headers=owner_headers)
    file_id = r.json()["id"]
    client.put(f"/api/workspaces/{workspace_id}/files/{file_id}/favorite", headers=owner_headers)

    r = client.get(f"/api/workspaces/{workspace_id}/favorites", headers=other_headers)
    assert all(item["resource_id"] != file_id for item in r.json())


def test_deleting_a_favorited_dashboard_removes_it_from_favorites_without_erroring(client, owner_headers, workspace_id):
    r = client.post(f"/api/workspaces/{workspace_id}/dashboards", json={"name": "Favorited Dashboard"}, headers=owner_headers)
    dashboard_id = r.json()["id"]
    r = client.put(f"/api/workspaces/{workspace_id}/dashboards/{dashboard_id}/favorite", headers=owner_headers)
    assert r.status_code == 200, r.text
    assert r.json()["resource_type"] == "dashboard"

    r = client.get(f"/api/workspaces/{workspace_id}/favorites", headers=owner_headers)
    assert any(item["resource_id"] == dashboard_id for item in r.json())

    r = client.delete(f"/api/workspaces/{workspace_id}/dashboards/{dashboard_id}", headers=owner_headers)
    assert r.status_code == 204

    # Same defensive posture as sharing's cascade test: even if the
    # cascade were somehow missed, list_favorites_for_user's orphan filter
    # must return 200 with the row simply absent, not 500.
    r = client.get(f"/api/workspaces/{workspace_id}/favorites", headers=owner_headers)
    assert r.status_code == 200
    assert all(item["resource_id"] != dashboard_id for item in r.json())
