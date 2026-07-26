from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai_jobs.models import AiJob
from app.ai_jobs.queue import ai_queue
from app.ai_jobs.tasks import run_ai_task

# "investigate" is a valid AiJob.task_type at the DB level (see models.py)
# but has no job function yet -- that's the multi-step investigate agent,
# built on top of this queue in a later phase. Only accept task types this
# phase actually implements a worker function for.
CREATABLE_TASK_TYPES = {"generate", "explain", "repair", "suggest"}


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
    ai_queue.enqueue(run_ai_task, str(job.id))
    return job


async def get_job(session: AsyncSession, *, workspace_id: uuid.UUID, job_id: uuid.UUID) -> AiJob:
    result = await session.execute(select(AiJob).where(AiJob.workspace_id == workspace_id, AiJob.id == job_id))
    job = result.scalar_one_or_none()
    if job is None:
        raise AiJobNotFoundError(f"AI job {job_id} not found in workspace {workspace_id}")
    return job
