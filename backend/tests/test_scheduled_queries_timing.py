"""tests/test_scheduled_queries_timing.py

Pure cron-timing math (app/scheduled_queries/timing.py), tested with
contrived timestamps instead of real wall-clock waits -- this is the
correctness proof for "fires on schedule" that doesn't depend on a flaky
90-second cron wait (see tests/test_scheduled_queries.py for the
job/notification path, which uses a real local HTTP listener instead).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.scheduled_queries.timing import is_due, next_due

EVERY_MINUTE = "* * * * *"
EVERY_HOUR = "0 * * * *"


def test_next_due_computes_the_next_cron_occurrence_after_a_given_time():
    after = datetime(2026, 1, 1, 12, 30, 0)
    assert next_due(EVERY_MINUTE, after) == datetime(2026, 1, 1, 12, 31, 0)
    assert next_due(EVERY_HOUR, after) == datetime(2026, 1, 1, 13, 0, 0)


def test_is_due_is_false_before_the_next_occurrence_and_true_at_or_after_it():
    anchor = datetime(2026, 1, 1, 12, 30, 0)
    assert is_due(EVERY_MINUTE, anchor, anchor + timedelta(seconds=30)) is False
    assert is_due(EVERY_MINUTE, anchor, anchor + timedelta(minutes=1)) is True
    assert is_due(EVERY_MINUTE, anchor, anchor + timedelta(minutes=5)) is True


def test_is_due_uses_last_enqueued_at_as_the_anchor_not_last_run_at():
    """The actual double-fire-prevention mechanism: two ticks 30s apart
    against a row already enqueued a few seconds ago must not both see it
    as due, even if the job it triggered hasn't finished (and therefore
    hasn't updated last_run_at) yet."""
    last_enqueued_at = datetime(2026, 1, 1, 12, 30, 0)
    tick_1_now = last_enqueued_at + timedelta(seconds=10)
    tick_2_now = last_enqueued_at + timedelta(seconds=40)
    assert is_due(EVERY_MINUTE, last_enqueued_at, tick_1_now) is False
    assert is_due(EVERY_MINUTE, last_enqueued_at, tick_2_now) is False
    # Only once a full minute has actually passed since the last enqueue:
    assert is_due(EVERY_MINUTE, last_enqueued_at, last_enqueued_at + timedelta(minutes=1)) is True
