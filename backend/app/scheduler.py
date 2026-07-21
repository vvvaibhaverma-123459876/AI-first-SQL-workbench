"""Standalone process: `python -m app.scheduler`. Runs docker-compose's
`scheduler` service, separate from app/worker.py's RQ Worker.

Deliberately its own process, not a background thread inside worker.py:
RQ's default Worker forks a work-horse subprocess per job, and a
persistent thread doing DB queries + Redis enqueues (as a tick loop would)
holds library locks (SQLAlchemy, logging, requests) that a fork() taken
mid-tick could copy into the child in a locked, never-released state --
the same fork-safety bug class as the already-documented macOS
NSCharacterSet abort (see worker.py / sql-studio-v2-rebuild memory), except
this variant isn't macOS-specific and could hang a job on Linux/CI too.
This process never forks anything -- it only enqueues -- so that risk
doesn't apply here.
"""
from __future__ import annotations

import time

# app.auth.models MUST import before anything that touches
# fastapi_users_db_sqlalchemy.generics -- see alembic/env.py for the full
# explanation of this recurring bug class.
from app.auth.models import User  # noqa: E402,F401

from app.ai_jobs.models import AiJob  # noqa: E402,F401
from app.connections.embedding_models import SchemaEmbedding  # noqa: E402,F401
from app.connections.models import DataConnection  # noqa: E402,F401
from app.dashboards.models import Dashboard, DashboardItem  # noqa: E402,F401
from app.files.models import File, FileRevision  # noqa: E402,F401
from app.scheduled_queries.models import ScheduledQuery  # noqa: E402,F401
from app.scheduled_queries.timing import tick  # noqa: E402
from app.workspaces.models import AuditLogEntry, Workspace, WorkspaceMembership  # noqa: E402,F401

from app.db.control_plane_sync import get_sync_session  # noqa: E402

TICK_INTERVAL_SECONDS = 30


def main() -> None:
    print(f"*** Scheduler tick loop starting, interval={TICK_INTERVAL_SECONDS}s", flush=True)
    while True:
        session = get_sync_session()
        try:
            enqueued = tick(session)
            if enqueued:
                print(f"Scheduler tick enqueued {len(enqueued)} due job(s): {enqueued}", flush=True)
        except Exception as exc:  # a bad tick must not kill the loop -- it retries next interval
            print(f"Scheduler tick failed: {exc}", flush=True)
        finally:
            session.close()
        time.sleep(TICK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
