"""Phase 6a: the AI fallback-rate metric, aggregated for real.

Every AI call (whether it arrives via the v2 job queue, running in the
worker process, or one of the legacy synchronous /api/... endpoints,
running in the API process) ultimately routes through exactly one choke
point: AIService._generate() (see app/services/ai_service.py). That's the
single call site instrumented here -- covering every AI-producing route
in the system without needing to touch each one individually, and without
missing any.

Counters live in Redis, not process memory: a per-response
`provider_fallback` field has existed since Phase 3, but that's
visibility, not a metric -- an in-memory counter would only ever see the
calls made in whichever single process (API or worker) happened to
increment it, and the two processes never share memory. Redis is already
a hard dependency (RQ), so it's the natural shared counter store, and its
own default persistence means the counts survive a process restart --
deliberately not reset on boot, since "how has this deployment behaved
over its lifetime" is more useful than a counter that discards history
every redeploy.
"""
from __future__ import annotations

import logging

from redis import Redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_redis = Redis.from_url(get_settings().redis_url, socket_connect_timeout=1, socket_timeout=1)

_TOTAL_KEY = "metrics:ai_calls:total"
_FALLBACK_KEY = "metrics:ai_calls:fallback"


def record_ai_call(fallback_reason: str | None) -> None:
    # A metrics side-channel must never be able to break the actual AI call
    # it's instrumenting -- e.g. a unit test or dev box with no Redis
    # running would otherwise turn every single generate/explain/repair
    # call into a hard failure. Swallow and log instead.
    try:
        _redis.incr(_TOTAL_KEY)
        if fallback_reason:
            _redis.incr(_FALLBACK_KEY)
    except Exception:
        logger.warning("record_ai_call: could not reach Redis, metric not recorded", exc_info=True)


def get_ai_fallback_metrics() -> dict:
    try:
        total = int(_redis.get(_TOTAL_KEY) or 0)
        fallback = int(_redis.get(_FALLBACK_KEY) or 0)
    except Exception:
        logger.warning("get_ai_fallback_metrics: could not reach Redis", exc_info=True)
        return {"ai_calls_total": 0, "ai_calls_fallback": 0, "ai_fallback_rate": 0.0, "error": "metrics store unreachable"}
    return {
        "ai_calls_total": total,
        "ai_calls_fallback": fallback,
        "ai_fallback_rate": (fallback / total) if total else 0.0,
    }
