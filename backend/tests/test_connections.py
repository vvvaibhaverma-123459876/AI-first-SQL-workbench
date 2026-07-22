"""tests/test_connections.py

Phase 2 (v2 rebuild): the data connector layer. Postgres, MySQL, and SQLite
are exercised against real running databases here, not mocks -- the same
"reproduce against real infrastructure" discipline that caught the Phase 1
FK-cascade bug. Snowflake, BigQuery, and Databricks are implemented against
their standard SQLAlchemy dialects but cannot be live-verified in this
environment (no cloud account exists here); what IS tested for those three
is the one thing every user of them will actually experience if the optional
driver package isn't installed: a clean, typed error, not a crash.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def auth_headers(client):
    email = "connections-owner@example.com"
    client.post("/api/auth/register", json={"email": email, "password": "correcthorsebatterystaple", "display_name": "Connections Owner"})
    r = client.post("/api/auth/jwt/login", data={"username": email, "password": "correcthorsebatterystaple"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def workspace_id(client, auth_headers):
    r = client.post("/api/workspaces", json={"name": "Connections Test Workspace"}, headers=auth_headers)
    return r.json()["id"]


def test_create_connection_never_returns_the_password(client, auth_headers, workspace_id):
    r = client.post(
        f"/api/workspaces/{workspace_id}/connections",
        json={"name": "leak-check", "config": {"connector_type": "postgres", "host": "example.com", "database": "d", "username": "u", "password": "super-secret-value"}},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    assert "super-secret-value" not in r.text
    assert "password" not in r.json()
    assert "encrypted_config" not in r.json()

    r = client.get(f"/api/workspaces/{workspace_id}/connections", headers=auth_headers)
    assert "super-secret-value" not in r.text


def test_credentials_are_encrypted_at_rest_inspecting_the_raw_db_column(client, auth_headers, workspace_id):
    """Phase 6's own done-when: "connection credentials are encrypted at
    rest (verified by inspecting the DB directly)". The test above proves
    the API's own read path never leaks a secret -- that's necessary but
    not sufficient, since a bug that stored the config as plaintext would
    still pass it as long as every response happened to strip the field
    before serializing. This test instead reads the RAW `encrypted_config`
    column straight out of the control-plane DB, bypassing
    connections.service.get_connection() (and therefore crypto.decrypt_config)
    entirely, for two differently-shaped connectors -- a plain password AND
    a bearer-token-style secret -- so this isn't just "the postgres
    password specifically" but the whole encrypted-blob approach
    (crypto.encrypt_config encrypts the entire config dict as one JSON
    payload, not per-field)."""
    import json
    import uuid

    from app.connections.models import DataConnection
    from app.db.control_plane_sync import get_sync_session

    secrets = {
        "postgres": ("db-inspect-postgres", "extremely-secret-db-password", {"connector_type": "postgres", "host": "h", "database": "d", "username": "u", "password": "extremely-secret-db-password"}),
        "databricks": ("db-inspect-databricks", "dapi_extremely_secret_token_value", {"connector_type": "databricks", "server_hostname": "h", "http_path": "/p", "access_token": "dapi_extremely_secret_token_value"}),
    }
    connection_ids = {}
    for key, (name, _secret, config) in secrets.items():
        r = client.post(f"/api/workspaces/{workspace_id}/connections", json={"name": name, "config": config}, headers=auth_headers)
        assert r.status_code == 200, r.text
        connection_ids[key] = r.json()["id"]

    session = get_sync_session()
    try:
        for key, (_name, secret, _config) in secrets.items():
            row = session.get(DataConnection, uuid.UUID(connection_ids[key]))
            assert row is not None
            # The raw stored blob: not the plaintext secret, not even valid
            # JSON (Fernet's own token format), so this can't pass by
            # accident of e.g. a dict repr containing the value differently.
            assert secret not in row.encrypted_config
            with pytest.raises(json.JSONDecodeError):
                json.loads(row.encrypted_config)
    finally:
        session.close()


def test_duplicate_connection_name_in_workspace_is_rejected(client, auth_headers, workspace_id):
    payload = {"name": "dup-conn", "config": {"connector_type": "sqlite", "path": "/tmp/whatever.db"}}
    r = client.post(f"/api/workspaces/{workspace_id}/connections", json=payload, headers=auth_headers)
    assert r.status_code == 200
    r = client.post(f"/api/workspaces/{workspace_id}/connections", json=payload, headers=auth_headers)
    assert r.status_code == 409


def test_sqlite_connection_full_round_trip(client, auth_headers, workspace_id):
    """No skip needed -- SQLite needs no server, so this always runs and is
    the fastest full proof that create -> test -> schema -> query all work
    end to end through the real API."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    conn = sqlite3.connect(tmp.name)
    conn.execute("CREATE TABLE widgets (id INTEGER PRIMARY KEY, label TEXT NOT NULL)")
    conn.execute("INSERT INTO widgets (label) VALUES ('a'), ('b')")
    conn.commit()
    conn.close()

    r = client.post(
        f"/api/workspaces/{workspace_id}/connections",
        json={"name": "sqlite-roundtrip", "config": {"connector_type": "sqlite", "path": tmp.name}},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    connection_id = r.json()["id"]

    r = client.post(f"/api/workspaces/{workspace_id}/connections/{connection_id}/test", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["ok"] is True

    r = client.get(f"/api/workspaces/{workspace_id}/connections/{connection_id}/schema", headers=auth_headers)
    assert r.status_code == 200
    tables = {t["name"]: t for t in r.json()}
    assert "widgets" in tables
    assert {c["name"] for c in tables["widgets"]["columns"]} == {"id", "label"}

    r = client.post(f"/api/workspaces/{workspace_id}/connections/{connection_id}/query", json={"sql": "SELECT * FROM widgets ORDER BY id"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["row_count"] == 2
    assert body["rows"][0]["label"] == "a"
    assert body["truncated"] is False


def test_viewer_can_select_but_not_write_through_a_connection(client, auth_headers, workspace_id):
    """Role enforcement is statement-shape-based here, not resource-based like
    files: a viewer may run a SELECT against a connection (read) but not an
    INSERT/UPDATE/DDL (write) -- classified via sqlglot, fail-closed if it
    can't parse the statement."""
    from app.db.control_plane import ControlPlaneSessionLocal
    from app.workspaces.models import WorkspaceMembership
    import asyncio

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    conn = sqlite3.connect(tmp.name)
    conn.execute("CREATE TABLE t (id INTEGER)")
    conn.commit()
    conn.close()

    r = client.post(
        f"/api/workspaces/{workspace_id}/connections",
        json={"name": "role-check-sqlite", "config": {"connector_type": "sqlite", "path": tmp.name}},
        headers=auth_headers,
    )
    connection_id = r.json()["id"]

    email = "connections-viewer@example.com"
    client.post("/api/auth/register", json={"email": email, "password": "correcthorsebatterystaple", "display_name": "Viewer"})
    r = client.post("/api/auth/jwt/login", data={"username": email, "password": "correcthorsebatterystaple"})
    viewer_headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    me = client.get("/api/users/me", headers=viewer_headers).json()

    async def _add_viewer_membership():
        async with ControlPlaneSessionLocal() as session:
            session.add(WorkspaceMembership(workspace_id=workspace_id, user_id=me["id"], role="viewer"))
            await session.commit()

    asyncio.run(_add_viewer_membership())

    r = client.post(f"/api/workspaces/{workspace_id}/connections/{connection_id}/query", json={"sql": "SELECT * FROM t"}, headers=viewer_headers)
    assert r.status_code == 200, r.text

    r = client.post(f"/api/workspaces/{workspace_id}/connections/{connection_id}/query", json={"sql": "INSERT INTO t VALUES (1)"}, headers=viewer_headers)
    assert r.status_code == 403


def test_editor_write_through_a_connection_actually_persists(client, auth_headers, workspace_id):
    """Regression test for a real bug: run_query_sync used engine.connect()
    with no commit, so an editor's INSERT looked like it succeeded (the API
    even returned 200) but was silently rolled back the instant the
    connection closed -- and for statements with no result set at all,
    iterating the result raised ResourceClosedError, which the route turned
    into a confusing 400 for a write that should have been allowed. Checks
    persistence through a second, independent sqlite3 connection to the same
    file, not just the API's own response, since the bug could otherwise
    hide behind an in-transaction read that looks correct but never lands
    on disk."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    conn = sqlite3.connect(tmp.name)
    conn.execute("CREATE TABLE writable (id INTEGER PRIMARY KEY, label TEXT)")
    conn.commit()
    conn.close()

    r = client.post(
        f"/api/workspaces/{workspace_id}/connections",
        json={"name": "write-persists-check", "config": {"connector_type": "sqlite", "path": tmp.name}},
        headers=auth_headers,
    )
    connection_id = r.json()["id"]

    r = client.post(
        f"/api/workspaces/{workspace_id}/connections/{connection_id}/query",
        json={"sql": "INSERT INTO writable (label) VALUES ('persisted')"},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["row_count"] == 1  # one row affected, reported via result.rowcount
    assert r.json()["columns"] == []

    check_conn = sqlite3.connect(tmp.name)
    rows = check_conn.execute("SELECT label FROM writable").fetchall()
    check_conn.close()
    assert rows == [("persisted",)]


@pytest.mark.parametrize(
    "connector_type,fake_config",
    [
        ("snowflake", {"connector_type": "snowflake", "account": "acct", "user": "u", "password": "p", "warehouse": "w", "database": "d", "schema": "s"}),
        ("bigquery", {"connector_type": "bigquery", "project_id": "proj", "service_account_json": "{}"}),
        ("databricks", {"connector_type": "databricks", "server_hostname": "h", "http_path": "/p", "access_token": "t"}),
    ],
)
def test_cloud_connectors_without_the_optional_driver_installed_fail_clean_not_crash(client, auth_headers, workspace_id, connector_type, fake_config):
    """Snowflake/BigQuery/Databricks drivers are optional extras (see
    requirements.txt) and are not installed in this project's dev/CI
    environment -- this is the one thing every user of these three
    connector types experiences without the extra installed, and it must be
    a clean typed error, not a 500."""
    r = client.post(
        f"/api/workspaces/{workspace_id}/connections",
        json={"name": f"{connector_type}-clean-error-check", "config": fake_config},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    connection_id = r.json()["id"]

    r = client.post(f"/api/workspaces/{workspace_id}/connections/{connection_id}/test", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "not installed" in body["message"]


def _postgres_sync_config(env_var: str) -> dict | None:
    raw = os.environ.get(env_var)
    if not raw:
        return None
    url = make_url(raw)
    return {"connector_type": "postgres", "host": url.host, "port": url.port or 5432, "database": url.database, "username": url.username, "password": url.password}


def test_postgres_connection_against_a_real_postgres_server(client, auth_headers, workspace_id):
    """Skipped unless TEST_POSTGRES_URL is set -- same CI Postgres service
    container the rest of this project's backend tests already use, just
    with the sync psycopg2 driver this connector actually uses (blocking
    driver, run through a threadpool -- see service.py's module docstring)."""
    config = _postgres_sync_config("TEST_POSTGRES_URL")
    if config is None:
        pytest.skip("TEST_POSTGRES_URL not set")

    import psycopg2

    seed_conn = psycopg2.connect(host=config["host"], port=config["port"], dbname=config["database"], user=config["username"], password=config["password"])
    seed_conn.autocommit = True
    with seed_conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS connector_smoke_test")
        cur.execute("CREATE TABLE connector_smoke_test (id INT PRIMARY KEY, label TEXT NOT NULL)")
        cur.execute("INSERT INTO connector_smoke_test VALUES (1, 'from-real-postgres')")
    seed_conn.close()

    r = client.post(f"/api/workspaces/{workspace_id}/connections", json={"name": "real-postgres", "config": config}, headers=auth_headers)
    assert r.status_code == 200, r.text
    connection_id = r.json()["id"]

    r = client.post(f"/api/workspaces/{workspace_id}/connections/{connection_id}/test", headers=auth_headers)
    assert r.json()["ok"] is True, r.json()

    r = client.post(
        f"/api/workspaces/{workspace_id}/connections/{connection_id}/query",
        json={"sql": "SELECT * FROM connector_smoke_test"},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["rows"] == [{"id": 1, "label": "from-real-postgres"}]


def test_mysql_connection_against_a_real_mysql_server(client, auth_headers, workspace_id):
    """Skipped unless TEST_MYSQL_URL is set. CI runs a real MySQL service
    container for this; locally it needs `docker run ... mysql:8` pointed at
    by TEST_MYSQL_URL, e.g. mysql+pymysql://root:root@localhost:3307/sqlstudio."""
    raw = os.environ.get("TEST_MYSQL_URL")
    if not raw:
        pytest.skip("TEST_MYSQL_URL not set")
    url = make_url(raw)
    config = {"connector_type": "mysql", "host": url.host, "port": url.port or 3306, "database": url.database, "username": url.username, "password": url.password}

    import pymysql

    seed_conn = pymysql.connect(host=config["host"], port=config["port"], database=config["database"], user=config["username"], password=config["password"])
    with seed_conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS connector_smoke_test")
        cur.execute("CREATE TABLE connector_smoke_test (id INT PRIMARY KEY, label VARCHAR(100) NOT NULL)")
        cur.execute("INSERT INTO connector_smoke_test VALUES (1, 'from-real-mysql')")
    seed_conn.commit()
    seed_conn.close()

    r = client.post(f"/api/workspaces/{workspace_id}/connections", json={"name": "real-mysql", "config": config}, headers=auth_headers)
    assert r.status_code == 200, r.text
    connection_id = r.json()["id"]

    r = client.post(f"/api/workspaces/{workspace_id}/connections/{connection_id}/test", headers=auth_headers)
    assert r.json()["ok"] is True, r.json()

    r = client.post(
        f"/api/workspaces/{workspace_id}/connections/{connection_id}/query",
        json={"sql": "SELECT * FROM connector_smoke_test"},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["rows"] == [{"id": 1, "label": "from-real-mysql"}]


def test_query_row_limit_caps_at_default_row_limit_and_reports_truncation(client, auth_headers, workspace_id):
    """Bounds memory regardless of whether the user's own SQL has a LIMIT --
    a `SELECT *` against a huge external table must not be able to pull
    unbounded rows into this server's memory."""
    from app.core.config import get_settings

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    conn = sqlite3.connect(tmp.name)
    conn.execute("CREATE TABLE big (n INTEGER)")
    row_limit = get_settings().default_row_limit
    conn.executemany("INSERT INTO big VALUES (?)", [(i,) for i in range(row_limit + 50)])
    conn.commit()
    conn.close()

    r = client.post(
        f"/api/workspaces/{workspace_id}/connections",
        json={"name": "row-limit-check", "config": {"connector_type": "sqlite", "path": tmp.name}},
        headers=auth_headers,
    )
    connection_id = r.json()["id"]

    r = client.post(f"/api/workspaces/{workspace_id}/connections/{connection_id}/query", json={"sql": "SELECT * FROM big"}, headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["row_count"] == row_limit
    assert body["truncated"] is True
