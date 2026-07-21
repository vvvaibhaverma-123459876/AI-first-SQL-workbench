"""RQ worker entrypoint -- run as its own process, separate from the API
server: `python -m app.worker`. docker-compose.yml runs this as the
`worker` service; a bare local dev setup needs it started manually
alongside `uvicorn app.main:app`.
"""
from __future__ import annotations

from rq import Worker

from app.ai_jobs.queue import ai_queue, redis_conn

if __name__ == "__main__":
    Worker([ai_queue], connection=redis_conn).work()
