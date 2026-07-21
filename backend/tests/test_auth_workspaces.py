"""tests/test_auth_workspaces.py

Phase 0 (v2 rebuild): multi-tenant foundations. Locks in the "done when" bar
from the build plan — a user can register, log in, create a workspace, and
see it persisted — plus the role-enforcement contract every later phase's
resource sharing depends on.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _register_and_login(client: TestClient, email: str, password: str = "correcthorsebatterystaple", display_name: str = "Test User") -> str:
    r = client.post("/api/auth/register", json={"email": email, "password": password, "display_name": display_name})
    assert r.status_code == 201, r.text
    r = client.post("/api/auth/jwt/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_register_then_login_issues_a_working_token(client):
    token = _register_and_login(client, "alice@example.com")
    r = client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == "alice@example.com"
    assert r.json()["display_name"] == "Test User"


def test_workspace_routes_require_authentication(client):
    r = client.get("/api/workspaces")
    assert r.status_code == 401
    r = client.post("/api/workspaces", json={"name": "x"})
    assert r.status_code == 401


def test_create_and_list_workspace_persists_and_grants_owner_role(client):
    token = _register_and_login(client, "bob@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    r = client.post("/api/workspaces", json={"name": "Bob's Workspace"}, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "Bob's Workspace"
    assert body["role"] == "owner"
    workspace_id = body["id"]

    r = client.get("/api/workspaces", headers=headers)
    assert r.status_code == 200
    names = [w["name"] for w in r.json()]
    assert "Bob's Workspace" in names

    r = client.get(f"/api/workspaces/{workspace_id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["id"] == workspace_id


def test_a_second_user_cannot_see_someone_elses_workspace(client):
    """The whole point of workspaces: they're isolated per user until
    something is explicitly shared (a later phase's job)."""
    owner_token = _register_and_login(client, "carol@example.com")
    r = client.post("/api/workspaces", json={"name": "Carol's Private Workspace"}, headers={"Authorization": f"Bearer {owner_token}"})
    workspace_id = r.json()["id"]

    other_token = _register_and_login(client, "dave@example.com")
    r = client.get(f"/api/workspaces/{workspace_id}", headers={"Authorization": f"Bearer {other_token}"})
    assert r.status_code == 404, "a non-member must not be able to see the workspace even exists"

    r = client.get("/api/workspaces", headers={"Authorization": f"Bearer {other_token}"})
    assert r.status_code == 200
    assert r.json() == [], "dave has no workspaces of his own yet"


def test_require_role_service_enforces_role_ranking():
    """Direct test of the role-ranking logic later phases (sharing,
    permissioned dashboards) will depend on — viewer < editor < owner."""
    from app.workspaces.service import ROLE_RANK

    assert ROLE_RANK["viewer"] < ROLE_RANK["editor"] < ROLE_RANK["owner"]


def test_existing_product_routes_are_unaffected_by_the_new_auth_layer(client):
    """The v1 SQL workbench routes must keep working unauthenticated during
    the transition — Phase 2 is what scopes them to a workspace/connection,
    not Phase 0."""
    r = client.get("/api/health")
    assert r.status_code == 200
    r = client.get("/api/schema")
    assert r.status_code == 200
