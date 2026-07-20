import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def test_health_root_and_api_prefix(client):
    for path in ["/health", "/api/health"]:
        r = client.get(path)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["app_version"]
        assert body["ai_mode"] in {"ollama", "mock", "hf", "huggingface", "huggingface-local"}
        # The demo DB is seeded on boot (see app/main.py lifespan) — health should
        # be able to prove it's actually queryable, not just "the process is up".
        assert body["db_row_counts"], "expected at least one seeded table"
        assert all(count > 0 for count in body["db_row_counts"].values())


def test_validate_rejects_other_write_statements(client):
    for sql in ["UPDATE users SET email='x'", "DROP TABLE users", "INSERT INTO users VALUES (1)"]:
        r = client.post("/api/validate-sql", json={"sql": sql})
        assert r.status_code == 200
        assert r.json()["valid"] is False


def test_ai_status_is_local_only(client):
    r = client.get("/api/ai/status")
    assert r.status_code == 200
    assert r.json()["local_only"] is True


def test_schema(client):
    r = client.get("/api/schema")
    assert r.status_code == 200
    assert "tables" in r.json()


def test_validate_rejects_delete(client):
    r = client.post("/api/validate-sql", json={"sql": "DELETE FROM users"})
    assert r.status_code == 200
    assert r.json()["valid"] is False


def test_execute_uses_safe_select(client):
    r = client.post("/api/execute-sql", json={"sql": "SELECT * FROM users LIMIT 3", "use_cache": False})
    assert r.status_code == 200
    body = r.json()
    assert body["row_count"] <= 3
    assert "user_id" in body["columns"]


def test_assistant_memory_endpoint(client):
    r = client.get("/api/assistant/memory")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_mock_ai_mode_generates_deterministic_sql(monkeypatch):
    """AI_MODE=mock (what the hosted container defaults to — see the Dockerfile)
    must resolve to MockProvider and work end-to-end with zero network access.
    The provider is resolved once per process (app.api.routes holds a
    module-level AIService singleton), so this exercises a fresh AIService
    built after the env change rather than the already-imported singleton,
    which is the same reason it stays fast — MockProvider never touches the
    network."""
    from app.core.config import get_settings
    from app.llm.providers import MockProvider, get_provider
    from app.services.ai_service import AIService

    monkeypatch.setenv("AI_MODE", "mock")
    get_settings.cache_clear()
    get_provider.cache_clear()
    try:
        assert get_settings().effective_ai_mode == "mock"
        assert isinstance(get_provider(), MockProvider)

        sql = AIService().generate_sql("top users by transaction amount").strip().lower()
        assert sql.startswith("select") or sql.startswith("with")
    finally:
        get_settings.cache_clear()
        get_provider.cache_clear()


def test_generate_sql_degrades_gracefully_on_provider_failure(client, monkeypatch):
    """If the configured provider (e.g. ollama with no local runtime reachable)
    raises, AIService._generate() must fall back to the mock provider instead of
    a 500 — this is the safety net a hosted deploy relies on if AI_MODE is ever
    misconfigured. Patches the provider directly (rather than relying on a real
    connection-refused timeout) so this stays fast and deterministic."""
    from app.api.routes import ai_service

    def boom(_prompt: str) -> str:
        raise ConnectionError("simulated: no local Ollama runtime reachable")

    monkeypatch.setattr(ai_service.provider, "generate", boom)

    r = client.post("/api/generate-sql", json={"prompt": "count of users per country"})
    assert r.status_code == 200
    assert r.json()["sql"].strip()


README_SUGGESTED_DEMO_QUESTIONS = [
    "Top 20 users by total transaction amount",
    "Which referral channel has the best card activation rate?",
    "Monthly revenue trend for the last 6 months",
    "Users with open support tickets and their total spend",
    "Average days to first transaction by country",
]


def test_suggested_demo_questions_produce_distinct_valid_results(monkeypatch):
    """The 5 "Suggested demo queries" in the README are what a LinkedIn visitor
    is most likely to click first in mock mode. Each must produce valid,
    non-empty, and — critically — *distinct* SQL: MockProvider.generate()'s
    prompt includes the full schema text ahead of the actual question, so a
    naive keyword match against the whole prompt would spuriously match every
    table/column name and collapse all 5 onto the same canned query, which
    regression-tested here."""
    from app.services.execution_service import SQLExecutionService
    from app.services.validation_service import SQLValidationService
    from app.services.ai_service import AIService
    from app.core.config import get_settings
    from app.llm.providers import get_provider

    monkeypatch.setenv("AI_MODE", "mock")
    get_settings.cache_clear()
    get_provider.cache_clear()
    try:
        svc = AIService()
        validator = SQLValidationService()
        executor = SQLExecutionService()
        seen_sql = set()
        for question in README_SUGGESTED_DEMO_QUESTIONS:
            sql = svc.generate_sql(question)
            validation = validator.validate(sql)
            assert validation.valid, f"{question!r} -> invalid SQL: {validation.errors}"
            result = executor.execute(validation.normalized_sql, use_cache=False)
            assert result.row_count > 0, f"{question!r} -> empty result set"
            seen_sql.add(sql)
        assert len(seen_sql) == len(README_SUGGESTED_DEMO_QUESTIONS), "expected distinct SQL per demo question"
    finally:
        get_settings.cache_clear()
        get_provider.cache_clear()
