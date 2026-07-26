"""tests/test_observability.py

Phase 6a (v2 rebuild): structured logging + the AI fallback-rate metric.

The metric's whole point is that it's aggregated across BOTH the API
process and the worker process (see app/observability/metrics.py's own
docstring) -- a single AIService._generate() call in-process here is
enough to prove the counters move at all, since both processes go through
the exact same Redis-backed counter functions; there is no
process-specific code path left to separately exercise.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_metrics_endpoint_returns_well_shaped_response_even_if_redis_is_unreachable(client):
    # Deliberately does NOT skip on missing Redis, unlike the test below --
    # this is exactly the "metrics side-channel must degrade visibly, never
    # 500" property from app/observability/metrics.py's record_ai_call/
    # get_ai_fallback_metrics, and it needs to hold whether or not Redis
    # happens to be reachable in whatever environment runs this test.
    r = client.get("/api/metrics")
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body["ai_calls_total"], int)
    assert isinstance(body["ai_calls_fallback"], int)
    assert isinstance(body["ai_fallback_rate"], float)
    assert body["ai_calls_fallback"] <= body["ai_calls_total"]


def test_an_ai_call_increments_the_metrics_endpoints_counters(client):
    """Skipped if Redis is unreachable, same pattern as
    test_scheduled_queries.py's real-Redis tick test -- this is the one
    property that genuinely needs a real Redis to prove (the counter
    actually moves), as opposed to the always-run test above (the endpoint
    never breaks)."""
    from redis import Redis
    from redis.exceptions import ConnectionError as RedisConnectionError

    from app.core.config import get_settings

    try:
        Redis.from_url(get_settings().redis_url).ping()
    except RedisConnectionError:
        pytest.skip("Redis not reachable at REDIS_URL -- set it to a running Redis to run this test")

    before = client.get("/api/metrics").json()

    r = client.post("/api/generate-sql", json={"prompt": "count all rows in users"})
    assert r.status_code == 200, r.text

    after = client.get("/api/metrics").json()
    assert after["ai_calls_total"] == before["ai_calls_total"] + 1
