from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_jobs.models import AiJob
from app.ai_jobs.queue import ai_queue
from app.ai_jobs.tasks import run_ai_task

CREATABLE_TASK_TYPES = {"generate", "explain", "repair", "suggest", "investigate"}

# RQ's own default (180s) is enough for a single generate/explain/repair/
# suggest call, but investigate chains two full orchestrator runs plus a
# synthesis call -- realistically 120-200s+ under this project's own
# hardware findings (task #22), and sometimes past 180s. Past job_timeout,
# RQ kills the work-horse outright (SIGKILL, no exception raised inside
# run_ai_task), so without this override the job's row would stay "running"
# forever with nothing to catch it and mark it failed.
JOB_TIMEOUT_SECONDS = {"investigate": 900}


class AiJobNotFoundError(Exception):
    pass


class InvalidTaskTypeError(Exception):
    pass


async def create_job(
    session: AsyncSession, *, workspace_id: uuid.UUID, created_by: uuid.UUID, task_type: str, input: dict
) -> AiJob:
    if task_type not in CREATABLE_TASK_TYPES:
        raise InvalidTaskTypeError(f"Unsupported task_type: {task_type!r} (must be one of {sorted(CREATABLE_TASK_TYPES)})")

    job = AiJob(workspace_id=workspace_id, task_type=task_type, status="queued", input=input, created_by=created_by)
    session.add(job)
    await session.commit()
    await session.refresh(job)
    ai_queue.enqueue(run_ai_task, str(job.id), job_timeout=JOB_TIMEOUT_SECONDS.get(task_type))
    return job


async def get_job(session: AsyncSession, *, workspace_id: uuid.UUID, job_id: uuid.UUID) -> AiJob:
    result = await session.execute(select(AiJob).where(AiJob.workspace_id == workspace_id, AiJob.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise AiJobNotFoundError(f"AI job {job_id} not found in workspace {workspace_id}")
    return job
