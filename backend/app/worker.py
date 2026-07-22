"""RQ worker entrypoint -- run as its own process, separate from the API
server: `python -m app.worker`. docker-compose.yml runs this as the
`worker` service; a bare local dev setup needs it started manually
alongside `uvicorn app.main:app`.
"""
from __future__ import annotations

from rq import Worker

# Every control-plane model must be imported before this process touches the
# database, or SQLAlchemy's mapper never learns those tables exist. A job
# function only imports the models it directly names (AiJob) -- but AiJob
# has foreign keys to workspaces.id and users.id, and flushing a session
# needs the FULL set of mapped tables to topologically sort them, not just
# the one being written. Without these imports, the very first commit inside
# run_ai_task (job.status = "running") crashes with
# NoReferencedTableError -- verified empirically by actually running this
# worker end-to-end (see alembic/env.py for the same requirement, and its
# note on why app.auth.models must be imported first).
from app.auth.models import User  # noqa: E402,F401

from app.ai_jobs.models import AiJob  # noqa: E402,F401
from app.connections.embedding_models import SchemaEmbedding  # noqa: E402,F401
from app.connections.models import DataConnection  # noqa: E402,F401
from app.dashboards.models import Dashboard, DashboardItem  # noqa: E402,F401
from app.favorites.models import Favorite  # noqa: E402,F401
from app.files.models import File, FileRevision  # noqa: E402,F401
from app.scheduled_queries.models import ScheduledQuery  # noqa: E402,F401
from app.sharing.models import ResourceShare  # noqa: E402,F401
from app.workspaces.models import AuditLogEntry, Workspace, WorkspaceMembership  # noqa: E402,F401

from app.ai_jobs.queue import ai_queue, redis_conn  # noqa: E402
from app.scheduled_queries.queue import scheduled_queries_queue  # noqa: E402

if __name__ == "__main__":
    # "ai_tasks" listed first so CI's log-grep for "Listening on ai_tasks"
    # (see ci-and-deploy.yml's "Start AI worker for e2e smoke test" step)
    # still matches as a substring regardless of what RQ appends after it.
    Worker([ai_queue, scheduled_queries_queue], connection=redis_conn).work()
