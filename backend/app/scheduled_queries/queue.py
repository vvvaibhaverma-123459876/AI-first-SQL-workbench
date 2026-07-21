"""Separate RQ queue from ai_jobs' -- same Redis connection, distinct queue
name so the two job kinds stay clearly separated (worker.py drains both).
"""
from __future__ import annotations

from rq import Queue

from app.ai_jobs.queue import redis_conn

scheduled_queries_queue = Queue("scheduled_queries", connection=redis_conn)
