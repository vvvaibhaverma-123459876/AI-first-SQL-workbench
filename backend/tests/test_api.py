from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_root_and_api_prefix():
    for path in ["/health", "/api/health"]:
        r = client.get(path)
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


def test_ai_status_is_local_only():
    r = client.get("/api/ai/status")
    assert r.status_code == 200
    assert r.json()["local_only"] is True


def test_schema():
    r = client.get("/api/schema")
    assert r.status_code == 200
    assert "tables" in r.json()


def test_validate_rejects_delete():
    r = client.post("/api/validate-sql", json={"sql": "DELETE FROM users"})
    assert r.status_code == 200
    assert r.json()["valid"] is False


def test_execute_uses_safe_select():
    r = client.post("/api/execute-sql", json={"sql": "SELECT * FROM users LIMIT 3", "use_cache": False})
    assert r.status_code == 200
    body = r.json()
    assert body["row_count"] <= 3
    assert "user_id" in body["columns"]


def test_assistant_memory_endpoint():
    r = client.get("/api/assistant/memory")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
