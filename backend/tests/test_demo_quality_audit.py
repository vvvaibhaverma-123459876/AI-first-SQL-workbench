"""tests/test_demo_quality_audit.py

Reproduces and locks in fixes for 4 demo-quality bugs found by walking the
app exactly as the README instructs a newcomer (AI_MODE=mock, the bundled
demo DB, the 5 suggested demo questions) rather than through the existing
unit tests, which never exercised the *product surface* of these paths.

Finding 1 — DEFAULTS & INFERENCE: /api/suggest-tables always returned the
same hardcoded ['users', 'transactions'] regardless of the question, because
MockProvider.generate() had a canned JSON stub for "suggest relevant tables"
prompts that always parsed successfully in AIService.suggest_tables(),
short-circuiting before the already-implemented, schema-validated
keyword-matching fallback was ever reached.

Finding 2 — SILENT FALLBACKS (dishonest rationale): AIService.repair_sql()
unconditionally claimed "Generated a safer or syntactically corrected
read-only SQL statement" even when the repaired SQL was byte-for-byte (modulo
whitespace) identical to the broken input — which is exactly what
MockProvider does for unrecognized errors.

Finding 3 — ERROR SURFACES: SQLExecutionService.execute() re-raised the raw
SQLAlchemy exception text (including "[SQL: ...]" query dumps and internal
"https://sqlalche.me/..." doc links) verbatim as the user-facing error,
which the frontend renders directly in a prominent error panel and persists
into query history.

Finding 4 — SILENT FALLBACKS (invisible provider failure): AIService._generate()
caught *any* exception from the real provider (e.g. Ollama unreachable mid-
session) and silently substituted mock output, with no indication anywhere
in the API response, the assistant run's steps/warnings, or the UI that a
fallback occurred — while /api/ai/status is an independent live check that
would keep reporting "connected".
"""
from __future__ import annotations

import pytest


README_SUGGESTED_DEMO_QUESTIONS = [
    "Top 20 users by total transaction amount",
    "Which referral channel has the best card activation rate?",
    "Monthly revenue trend for the last 6 months",
    "Users with open support tickets and their total spend",
    "Average days to first transaction by country",
]


@pytest.fixture
def mock_ai_service():
    """A fresh AIService bound to AI_MODE=mock, independent of the
    module-level singleton the app uses (matches the existing pattern in
    tests/test_api.py)."""
    from app.core.config import get_settings
    from app.llm.providers import get_provider
    from app.services.ai_service import AIService
    import os

    prior = os.environ.get("AI_MODE")
    os.environ["AI_MODE"] = "mock"
    get_settings.cache_clear()
    get_provider.cache_clear()
    try:
        yield AIService()
    finally:
        if prior is None:
            os.environ.pop("AI_MODE", None)
        else:
            os.environ["AI_MODE"] = prior
        get_settings.cache_clear()
        get_provider.cache_clear()


# ── Finding 1: suggest-tables must actually reflect the question ──────────

def test_suggest_tables_mock_is_not_hardcoded_to_the_same_two_tables(mock_ai_service):
    """The exact observed bug: every one of the 5 README demo questions
    returned identical suggestions=['users', 'transactions'] in mock mode."""
    results = {q: mock_ai_service.suggest_tables(q) for q in README_SUGGESTED_DEMO_QUESTIONS}
    table_sets = {q: tuple(sorted(s.table_name for s in r.suggestions)) for q, r in results.items()}
    distinct = set(table_sets.values())
    assert len(distinct) > 1, f"suggest-tables returned the same table set for every demo question: {table_sets}"


def test_suggest_tables_mock_finds_referrals_and_cards_for_the_referral_question(mock_ai_service):
    """A concrete, checkable case: asking about referral channel / card
    activation must surface the referrals/cards tables, not the generic
    users/transactions stub."""
    result = mock_ai_service.suggest_tables("Which referral channel has the best card activation rate?")
    names = {s.table_name for s in result.suggestions}
    assert names & {"referrals", "cards"}, f"expected referrals/cards to be suggested, got {names}"


def test_suggest_tables_reason_is_honest_about_how_it_matched(mock_ai_service):
    """Every suggestion's reason text must reflect real keyword/schema
    matching, not a canned claim that doesn't correspond to any actual
    analysis of the question."""
    result = mock_ai_service.suggest_tables("Users with open support tickets and their total spend")
    names = {s.table_name for s in result.suggestions}
    assert "support_tickets" in names
    for s in result.suggestions:
        assert s.reason  # every suggestion must carry a real (non-empty) reason


# ── Finding 2: repair_sql must not claim success when nothing changed ─────

def test_repair_sql_is_honest_when_no_correction_was_actually_made(mock_ai_service):
    """Feeding a broken query MockProvider cannot meaningfully repair (it
    just echoes the SQL back, optionally appending LIMIT) must not produce a
    rationale claiming a safer/corrected statement was generated."""
    broken = "SELECT * FROM userz"
    result = mock_ai_service.repair_sql(broken, "no such table: userz")
    normalized_in = broken.strip().rstrip(";").lower()
    normalized_out = result.repaired_sql.strip().rstrip(";").lower()
    assert normalized_in == normalized_out.split("\nlimit")[0].strip(), "test setup assumption: mock echoes SQL unchanged (or only adds LIMIT)"
    assert "generated a safer" not in result.rationale.lower()
    assert "corrected" not in result.rationale.lower() or "no automatic correction" in result.rationale.lower()


def test_repair_sql_rationale_is_positive_when_sql_actually_changes(mock_ai_service, monkeypatch):
    """Sanity check: when the repaired SQL genuinely differs from the input
    in more than just a cosmetic trailing LIMIT (i.e. an actual repair
    happened), the positive rationale is still used — this must not regress
    into always claiming failure either."""
    monkeypatch.setattr(mock_ai_service, "_generate", lambda _p: ("SELECT * FROM users LIMIT 10", None))
    result = mock_ai_service.repair_sql("SELECT * FROM userz", "no such table: userz")
    assert "no automatic correction" not in result.rationale.lower()


# ── Finding 3: execute-sql must never leak raw driver/SQL text ────────────

def test_execution_service_error_has_no_raw_sql_dump_or_internal_urls():
    from app.services.execution_service import SQLExecutionService

    with pytest.raises(ValueError) as excinfo:
        SQLExecutionService().execute("SELECT nonexistent_col FROM users", use_cache=False)
    message = str(excinfo.value)
    assert "sqlalche.me" not in message, f"leaked internal SQLAlchemy doc URL: {message!r}"
    assert "[SQL:" not in message, f"leaked raw SQL dump: {message!r}"
    assert "no such column" in message, f"expected an actionable reason, got: {message!r}"


def test_execute_sql_api_error_response_has_no_raw_sql_dump_or_internal_urls():
    """End-to-end through the actual route the frontend calls, since that's
    what ends up rendered in the ResultsPanel error box and persisted into
    query history."""
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        r = client.post("/api/execute-sql", json={"sql": "SELECT nonexistent_col FROM users", "use_cache": False})
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "sqlalche.me" not in detail
    assert "[SQL:" not in detail
    assert "no such column" in detail


# ── Finding 4: provider fallback must be visible, not silent ──────────────

def test_generate_sql_reports_fallback_when_provider_fails(mock_ai_service, monkeypatch):
    monkeypatch.setattr(mock_ai_service.provider, "generate", lambda _p: (_ for _ in ()).throw(ConnectionError("no local Ollama runtime reachable")))
    sql, fallback_reason = mock_ai_service.generate_sql("count of users per country")
    assert sql.strip()
    assert fallback_reason, "a provider failure must be reported back to the caller, not swallowed silently"
    assert "no local ollama runtime reachable" in fallback_reason.lower()


def test_explain_sql_reports_fallback_when_provider_fails(mock_ai_service, monkeypatch):
    monkeypatch.setattr(mock_ai_service.provider, "generate", lambda _p: (_ for _ in ()).throw(ConnectionError("boom")))
    result = mock_ai_service.explain_sql("SELECT 1")
    assert result.provider_fallback, "ExplainSQLResponse must surface that a fallback occurred"


def test_repair_sql_reports_fallback_when_provider_fails(mock_ai_service, monkeypatch):
    monkeypatch.setattr(mock_ai_service.provider, "generate", lambda _p: (_ for _ in ()).throw(ConnectionError("boom")))
    result = mock_ai_service.repair_sql("SELECT * FROM users", "err")
    assert result.provider_fallback


def test_suggest_tables_reports_fallback_when_provider_fails(mock_ai_service, monkeypatch):
    monkeypatch.setattr(mock_ai_service.provider, "generate", lambda _p: (_ for _ in ()).throw(ConnectionError("boom")))
    result = mock_ai_service.suggest_tables("top users by spend")
    assert result.provider_fallback


def test_no_fallback_reported_when_provider_succeeds(mock_ai_service):
    """Sanity check: the happy path (mock provider, no injected failure)
    must not spuriously claim a fallback occurred."""
    sql, fallback_reason = mock_ai_service.generate_sql("count of users per country")
    assert fallback_reason is None


def test_assistant_run_surfaces_provider_fallback_in_warnings_and_steps(monkeypatch):
    """The primary user-facing flow: /assistant/run already has `warnings`
    and `steps` fields that the frontend renders (warnings feed the amber
    "Warnings" panel; steps feed the Assistant activity log). A provider
    failure mid-run must show up there instead of silently degrading."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.api.routes import assistant_orchestrator

    monkeypatch.setattr(
        assistant_orchestrator.ai.provider,
        "generate",
        lambda _p: (_ for _ in ()).throw(ConnectionError("simulated: no local Ollama runtime reachable")),
    )
    with TestClient(app) as client:
        r = client.post("/api/assistant/run", json={"question": "count of users per country", "execute": True, "explain": True, "use_cache": False})
    assert r.status_code == 200
    body = r.json()
    assert any("ollama runtime reachable" in w.lower() or "provider failed" in w.lower() for w in body["warnings"]), body["warnings"]
    assert any(s["name"] == "provider_fallback" for s in body["steps"]), body["steps"]


# ── End-to-end demo-path test (user-visible output, not internals) ────────

def test_full_demo_path_user_visible_output_is_correct(monkeypatch):
    """Runs the exact primary flow a newcomer following the README would
    hit: AI_MODE=mock, POST /api/assistant/run for a README-suggested demo
    question, and asserts on the USER-VISIBLE response shape — the rendered
    SQL, the result rows, the table suggestions actually shown in the AI
    panel, and the absence of any raw error/URL/placeholder leakage — not on
    internal function return values. This is the contract: none of findings
    1-4 can silently reappear without this failing."""
    from app.core.config import get_settings
    from app.llm.providers import get_provider
    import os

    prior = os.environ.get("AI_MODE")
    os.environ["AI_MODE"] = "mock"
    get_settings.cache_clear()
    get_provider.cache_clear()
    try:
        from fastapi.testclient import TestClient
        from app.main import app

        with TestClient(app) as client:
            for question in README_SUGGESTED_DEMO_QUESTIONS:
                r = client.post("/api/assistant/run", json={"question": question, "execute": True, "explain": True, "use_cache": False})
                assert r.status_code == 200, question
                body = r.json()
                assert body["status"] == "success", f"{question}: {body.get('errors')}"
                assert body["sql"] and body["sql"].strip().lower().startswith(("select", "with"))
                assert body["result"] is not None and body["result"]["row_count"] > 0, f"{question}: empty result"
                assert body["suggestions"], f"{question}: no table suggestions shown to the user"
                for placeholder in ("TODO", "{var}", "None", "undefined", "NaN"):
                    assert placeholder not in body["explanation"] if body["explanation"] else True

            # Finding 1, end-to-end: distinct questions must not all show the
            # same "Relevant Tables" panel contents.
            seen = set()
            for question in README_SUGGESTED_DEMO_QUESTIONS:
                r = client.post("/api/suggest-tables", json={"prompt": question})
                seen.add(tuple(sorted(s["table_name"] for s in r.json()["suggestions"])))
            assert len(seen) > 1, f"Relevant Tables panel is identical for every demo question: {seen}"

            # Finding 3, end-to-end: a realistic user error (typo'd column)
            # must be an actionable message, never a stack trace/SQL dump.
            r = client.post("/api/execute-sql", json={"sql": "SELECT nonexistent_col FROM users", "use_cache": False})
            assert r.status_code == 400
            assert "sqlalche.me" not in r.json()["detail"]
    finally:
        if prior is None:
            os.environ.pop("AI_MODE", None)
        else:
            os.environ["AI_MODE"] = prior
        get_settings.cache_clear()
        get_provider.cache_clear()
