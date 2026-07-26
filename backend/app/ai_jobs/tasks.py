"""The RQ job function -- runs inside the worker process (app/worker.py),
never inside the API process. Sync all the way through: a sync DB session
(app/db/control_plane_sync.py) and AIService's existing sync provider calls.

input/result shape per task_type:
  generate: input={"prompt": str}          -> result={"sql": str, "provider_fallback": str|None}
  explain:  input={"sql": str}              -> result=ExplainSQLResponse as dict
  repair:   input={"sql": str, "error_message": str} -> result=RepairSQLResponse as dict
  suggest:  input={"prompt": str}           -> result=SuggestTablesResponse as dict
"""
from __future__ import annotations

import uuid
from datetime import datetime

from app.ai_jobs.models import AiJob
from app.db.control_plane_sync import get_sync_session
from app.services.ai_service import AIService


def _execute(service: AIService, task_type: str, input: dict) -> dict:
    if task_type == "generate":
        sql, fallback_reason = service.generate_sql(input["prompt"])
        return {"sql": sql, "provider_fallback": fallback_reason}
    if task_type == "explain":
        return service.explain_sql(input["sql"]).model_dump()
    if task_type == "repair":
        return service.repair_sql(input["sql"], input.get("error_message", "")).model_dump()
    if task_type == "suggest":
        return service.suggest_tables(input["prompt"]).model_dump()
    raise ValueError(f"Unsupported task_type: {task_type!r}")


def run_ai_task(job_id: str) -> None:
    session = get_sync_session()
    try:
        job = session.get(AiJob, uuid.UUID(job_id))
        if job is None:
            return  # Job row vanished (e.g. workspace deleted mid-flight) -- nothing to update.

        job.status = "running"
        job.started_at = datetime.utcnow()
        session.commit()

        try:
            job.result = _execute(AIService(), job.task_type, job.input)
            job.status = "done"
        except Exception as exc:
            job.error = str(exc)
            job.status = "failed"
        job.finished_at = datetime.utcnow()
        session.commit()
    finally:
        session.close()
