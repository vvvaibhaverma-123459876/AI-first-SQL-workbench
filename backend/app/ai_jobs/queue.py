"""Redis connection + the RQ queue every AI call runs through.

All AI calls (generate/explain/repair/suggest, and the investigate agent
built on top of this in a later phase) run off the request path: every one
of these is a real LLM call to Ollama, taking anywhere from ~10s to 100s+
(measured empirically, task #22) -- doing that inline in an async FastAPI
route would tie up the request for the whole duration. A route enqueues a
job and returns immediately; the frontend polls GET .../ai/jobs/{id}.
"""
from __future__ import annotations

from redis import Redis
from rq import Queue

from app.core.config import get_settings

redis_conn = Redis.from_url(get_settings().redis_url)
ai_queue = Queue("ai_tasks", connection=redis_conn)
