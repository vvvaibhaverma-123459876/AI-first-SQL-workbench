"""tests/test_demo_quality_audit.py

Reproduces and locks in fixes for demo-quality bugs found by walking the app
exactly as the README instructs a newcomer (AI_MODE=mock, the bundled demo
DB, the 5 suggested demo questions) rather than through the existing unit
tests, which never exercised the *product surface* of these paths.

Finding 3 — ERROR SURFACES: SQLExecutionService.execute() re-raised the raw
SQLAlchemy exception text (including "[SQL: ...]" query dumps and internal
"https://sqlalche.me/..." doc links) verbatim as the user-facing error,
which the frontend renders directly in a prominent error panel and persists
into query history.
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
