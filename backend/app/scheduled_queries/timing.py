"""Pure cron-timing math, deliberately separated from app/scheduler.py's
process loop so it can be unit tested with contrived timestamps instead of
real wall-clock waits.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from croniter import croniter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.scheduled_queries.models import ScheduledQuery


def next_due(cron_expression: str, after: datetime) -> datetime:
    return croniter(cron_expression, after).get_next(datetime)


def is_due(cron_expression: str, anchor: datetime, now: datetime) -> bool:
    return next_due(cron_expression, anchor) <= now


def tick(session: Session) -> list[uuid.UUID]:
    """Enqueues every due, active schedule and stamps last_enqueued_at in
    the SAME step as the enqueue decision -- not the job -- so a later
    tick (this runs on an interval, see app/scheduler.py) can't re-see a
    row whose job simply hasn't finished yet and enqueue it a second time.
    Local import of the queue/job function: this module is imported by
    both the scheduler process and the RQ worker's model-registration
    chain, and importing the queue (which opens a Redis connection at
    import time) isn't needed by every caller.
    """
    from app.scheduled_queries.queue import scheduled_queries_queue
    from app.scheduled_queries.tasks import run_scheduled_query

    now = datetime.utcnow()
    enqueued: list[uuid.UUID] = []
    rows = session.execute(select(ScheduledQuery).where(ScheduledQuery.is_active == True)).scalars().all()  # noqa: E712
    for row in rows:
        anchor = row.last_enqueued_at or row.created_at
        if is_due(row.cron_expression, anchor, now):
            row.last_enqueued_at = now
            session.commit()
            scheduled_queries_queue.enqueue(run_scheduled_query, str(row.id))
            enqueued.append(row.id)
    return enqueued
