"""tests/test_files.py

Phase 1 (v2 rebuild): the IDE core's file tree. Locks in the "done when" bar
-- a user creates, edits, and reopens files across a folder tree with zero
data loss, finds a file by name, and finds a phrase inside file contents
workspace-wide -- plus the autosave-revision safety net and role
enforcement on write operations.
"""
from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def auth_headers(client):
    email = "files-owner@example.com"
    client.post("/api/auth/register", json={"email": email, "password": "correcthorsebatterystaple", "display_name": "Files Owner"})
    r = client.post("/api/auth/jwt/login", data={"username": email, "password": "correcthorsebatterystaple"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def workspace_id(client, auth_headers):
    r = client.post("/api/workspaces", json={"name": "Files Test Workspace"}, headers=auth_headers)
    return r.json()["id"]


def test_create_and_reopen_a_file_round_trips_content_exactly(client, auth_headers, workspace_id):
    r = client.post(f"/api/workspaces/{workspace_id}/files", json={"name": "query.sql", "content": "SELECT 1;"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    file_id = r.json()["id"]
    assert r.json()["content"] == "SELECT 1;"

    r = client.get(f"/api/workspaces/{workspace_id}/files/{file_id}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["content"] == "SELECT 1;"


def test_folder_tree_nesting_and_listing(client, auth_headers, workspace_id):
    r = client.post(f"/api/workspaces/{workspace_id}/files", json={"name": "queries", "is_folder": True}, headers=auth_headers)
    folder_id = r.json()["id"]

    r = client.post(
        f"/api/workspaces/{workspace_id}/files",
        json={"name": "nested.sql", "parent_id": folder_id, "content": "SELECT 2;"},
        headers=auth_headers,
    )
    assert r.status_code == 200
    nested_id = r.json()["id"]

    r = client.get(f"/api/workspaces/{workspace_id}/files", headers=auth_headers)
    tree = {f["id"]: f for f in r.json()}
    assert tree[nested_id]["parent_id"] == folder_id
    assert tree[folder_id]["is_folder"] is True


def test_duplicate_name_in_same_folder_is_rejected_including_at_root(client, auth_headers, workspace_id):
    """The DB unique constraint alone does not catch this at root (NULL
    parent_id), so this is the regression test for the service-level check."""
    r = client.post(f"/api/workspaces/{workspace_id}/files", json={"name": "dup.sql", "content": "a"}, headers=auth_headers)
    assert r.status_code == 200
    r = client.post(f"/api/workspaces/{workspace_id}/files", json={"name": "dup.sql", "content": "b"}, headers=auth_headers)
    assert r.status_code == 409


def test_autosave_never_silently_loses_a_version(client, auth_headers, workspace_id):
    """Reproduces the exact risk autosave introduces: if two saves land far
    enough apart, the version in between must be recoverable, not just
    overwritten with no trace."""
    import time
    from app.files import service as files_service

    r = client.post(f"/api/workspaces/{workspace_id}/files", json={"name": "revisions.sql", "content": "v1"}, headers=auth_headers)
    file_id = r.json()["id"]

    original_threshold = files_service.MIN_SECONDS_BETWEEN_REVISIONS
    files_service.MIN_SECONDS_BETWEEN_REVISIONS = 0  # don't sleep in a test
    try:
        client.patch(f"/api/workspaces/{workspace_id}/files/{file_id}", json={"content": "v2"}, headers=auth_headers)
        client.patch(f"/api/workspaces/{workspace_id}/files/{file_id}", json={"content": "v3"}, headers=auth_headers)
    finally:
        files_service.MIN_SECONDS_BETWEEN_REVISIONS = original_threshold

    r = client.get(f"/api/workspaces/{workspace_id}/files/{file_id}/revisions", headers=auth_headers)
    contents = {rev["content"] for rev in r.json()}
    assert "v1" in contents, "the version before the first autosave must survive as a revision"
    assert "v2" in contents, "the version before the second autosave must survive as a revision"

    r = client.get(f"/api/workspaces/{workspace_id}/files/{file_id}", headers=auth_headers)
    assert r.json()["content"] == "v3", "the file itself always reflects the latest save"


def test_autosave_within_the_throttle_window_does_not_spam_revisions(client, auth_headers, workspace_id):
    r = client.post(f"/api/workspaces/{workspace_id}/files", json={"name": "throttled.sql", "content": "v1"}, headers=auth_headers)
    file_id = r.json()["id"]
    client.patch(f"/api/workspaces/{workspace_id}/files/{file_id}", json={"content": "v2"}, headers=auth_headers)
    client.patch(f"/api/workspaces/{workspace_id}/files/{file_id}", json={"content": "v3"}, headers=auth_headers)

    r = client.get(f"/api/workspaces/{workspace_id}/files/{file_id}/revisions", headers=auth_headers)
    assert len(r.json()) == 1, "two saves within the throttle window must only leave one recovery snapshot"


def test_delete_folder_cascades_to_children(client, auth_headers, workspace_id):
    r = client.post(f"/api/workspaces/{workspace_id}/files", json={"name": "to-delete", "is_folder": True}, headers=auth_headers)
    folder_id = r.json()["id"]
    r = client.post(f"/api/workspaces/{workspace_id}/files", json={"name": "child.sql", "parent_id": folder_id, "content": "x"}, headers=auth_headers)
    child_id = r.json()["id"]

    r = client.delete(f"/api/workspaces/{workspace_id}/files/{folder_id}", headers=auth_headers)
    assert r.status_code == 204

    assert client.get(f"/api/workspaces/{workspace_id}/files/{folder_id}", headers=auth_headers).status_code == 404
    assert client.get(f"/api/workspaces/{workspace_id}/files/{child_id}", headers=auth_headers).status_code == 404


def test_search_finds_a_phrase_inside_file_contents_workspace_wide(client, auth_headers, workspace_id):
    client.post(f"/api/workspaces/{workspace_id}/files", json={"name": "haystack.sql", "content": "SELECT needle FROM table"}, headers=auth_headers)
    r = client.get(f"/api/workspaces/{workspace_id}/files/search", params={"q": "needle"}, headers=auth_headers)
    assert r.status_code == 200
    names = [item["name"] for item in r.json()]
    assert "haystack.sql" in names
    assert "needle" in r.json()[[n["name"] for n in r.json()].index("haystack.sql")]["snippet"]


def test_a_viewer_cannot_write_but_can_read(client, workspace_id, auth_headers):
    """Direct role-enforcement test: register a second user, invite them as
    viewer, confirm read works and write is rejected with 403 (not a bare
    500 or a silent no-op)."""
    from app.db.control_plane import ControlPlaneSessionLocal
    from app.workspaces.models import WorkspaceMembership
    import asyncio

    email = "files-viewer@example.com"
    client.post("/api/auth/register", json={"email": email, "password": "correcthorsebatterystaple", "display_name": "Viewer"})
    r = client.post("/api/auth/jwt/login", data={"username": email, "password": "correcthorsebatterystaple"})
    viewer_token = r.json()["access_token"]
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}
    me = client.get("/api/users/me", headers=viewer_headers).json()

    async def _add_viewer_membership():
        async with ControlPlaneSessionLocal() as session:
            session.add(WorkspaceMembership(workspace_id=workspace_id, user_id=me["id"], role="viewer"))
            await session.commit()

    asyncio.run(_add_viewer_membership())

    r = client.get(f"/api/workspaces/{workspace_id}/files", headers=viewer_headers)
    assert r.status_code == 200

    r = client.post(f"/api/workspaces/{workspace_id}/files", json={"name": "viewer-should-not-create.sql", "content": "x"}, headers=viewer_headers)
    assert r.status_code == 403


def test_delete_nonempty_folder_with_revisions_on_real_postgres():
    """Regression test for a real bug: delete_file deleted parents before
    children and never deleted FileRevision rows. aiosqlite doesn't enforce
    foreign keys by default, so every other test in this file (including
    test_delete_folder_cascades_to_children) stayed green against that bug --
    real Postgres enforces files.parent_id and file_revisions.file_id
    immediately and would 500. Skipped unless TEST_POSTGRES_URL is set (CI
    sets it to the same Postgres service used for the alembic check)."""
    postgres_url = os.environ.get("TEST_POSTGRES_URL")
    if not postgres_url:
        pytest.skip("TEST_POSTGRES_URL not set -- this check needs real FK enforcement, which aiosqlite doesn't provide")

    import asyncio

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.auth.models import User
    from app.db.control_plane import ControlPlaneBase
    from app.files import service as files_service
    from app.workspaces.models import Workspace, WorkspaceMembership

    async def _run():
        from sqlalchemy import text

        engine = create_async_engine(postgres_url, future=True)
        async with engine.begin() as conn:
            # Phase 3d's schema_embeddings table (now part of
            # ControlPlaneBase.metadata) needs the pgvector extension --
            # per-database, not per-cluster, so this test's own scratch
            # create_all needs it too, same as test_schema_embeddings.py.
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(ControlPlaneBase.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        async with session_factory() as session:
            user_id = uuid.uuid4()
            session.add(User(id=user_id, email=f"{user_id}@example.com", hashed_password="x", display_name="FK Test", is_active=True, is_superuser=False, is_verified=False))
            workspace = Workspace(name="fk-regression", created_by=user_id)
            session.add(workspace)
            await session.flush()
            session.add(WorkspaceMembership(workspace_id=workspace.id, user_id=user_id, role="owner"))
            await session.commit()

            folder = await files_service.create_file(session, workspace_id=workspace.id, created_by=user_id, name="folder", is_folder=True, parent_id=None, content="")
            child = await files_service.create_file(session, workspace_id=workspace.id, created_by=user_id, name="child.sql", is_folder=False, parent_id=folder.id, content="v1")

            original_threshold = files_service.MIN_SECONDS_BETWEEN_REVISIONS
            files_service.MIN_SECONDS_BETWEEN_REVISIONS = 0
            try:
                await files_service.update_file(session, workspace_id=workspace.id, file_id=child.id, updated_by=user_id, content="v2")
            finally:
                files_service.MIN_SECONDS_BETWEEN_REVISIONS = original_threshold
            revisions = await files_service.list_revisions(session, workspace_id=workspace.id, file_id=child.id)
            assert revisions, "test setup: the child must have at least one revision before delete"

            # This is the actual regression check: must not raise an FK violation.
            await files_service.delete_file(session, workspace_id=workspace.id, file_id=folder.id, deleted_by=user_id)

            with pytest.raises(files_service.FileNotFoundError):
                await files_service.get_file(session, workspace_id=workspace.id, file_id=child.id)

        await engine.dispose()

    asyncio.run(_run())
