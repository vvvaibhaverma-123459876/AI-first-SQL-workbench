"""The RQ job function -- runs inside the worker process (app/worker.py),
never inside the API process. Sync all the way through: a sync DB session
(app/db/control_plane_sync.py) and AIService's existing sync provider calls.

input/result shape per task_type:
  generate:    input={"prompt": str}                      -> result={"sql": str, "provider_fallback": str|None}
  explain:     input={"sql": str}                          -> result=ExplainSQLResponse as dict
  repair:      input={"sql": str, "error_message": str}    -> result=RepairSQLResponse as dict
  suggest:     input={"prompt": str}                       -> result=SuggestTablesResponse as dict
  investigate: input={"question": str}                     -> result={"file_id": str, "summary": str, "provider_fallback": str|None}
"""
from __future__ import annotations

import uuid
from datetime import datetime

from app.ai_jobs.models import AiJob
from app.api.schemas import AssistantRunResponse
from app.assistant.orchestrator import AssistantOrchestrator
from app.db.control_plane_sync import get_sync_session
from app.db.session import MetadataSessionLocal
from app.files.models import File
from app.services.ai_service import AIService
from app.workspaces.models import AuditLogEntry


def _finding(response: AssistantRunResponse) -> dict:
    return {
        "question": response.question,
        "sql": response.sql or "",
        "row_count": response.result.row_count if response.result else 0,
        "sample": response.result.rows[:5] if response.result else [],
    }


def _render_step(title: str, response: AssistantRunResponse) -> list[str]:
    lines = [f"## {title}", "", f"**Question:** {response.question}", "", "```sql", response.sql or "(no SQL generated)", "```"]
    if response.result:
        lines += ["", f"Returned {response.result.row_count} row(s) in {response.result.execution_ms} ms."]
    if response.explanation:
        lines += ["", response.explanation]
    if response.errors:
        lines += ["", f"**Errors:** {'; '.join(response.errors)}"]
    return lines


def _run_investigation(job: AiJob) -> dict:
    """Chains a primary question with one automatic follow-up (drawn from
    the orchestrator's own next_questions heuristic), then asks the model to
    write a short report tying both together -- the piece that makes this a
    genuine multi-step investigation rather than two independent
    assistant/run calls. The report is written as a new file in the
    workspace's own file tree (reusing the File/FileRevision models from
    Phase 1) rather than a separate report entity, consistent with this
    project's file-centric IDE identity -- it's just a markdown file someone
    can open, edit, and version like anything else in the tree."""
    question = job.input["question"]
    orchestrator = AssistantOrchestrator()
    metadata_db = MetadataSessionLocal()
    try:
        primary = orchestrator.run(metadata_db, question, execute=True, explain=True, use_cache=False)
        findings = [_finding(primary)]
        report_sections = _render_step("Step 1", primary)

        followup: AssistantRunResponse | None = None
        if primary.status == "success" and primary.next_questions:
            followup = orchestrator.run(metadata_db, primary.next_questions[0], execute=True, explain=True, use_cache=False)
            findings.append(_finding(followup))
            report_sections += ["", *_render_step("Step 2 (automatic follow-up)", followup)]
    finally:
        metadata_db.close()

    synthesis, fallback_reason = orchestrator.ai.synthesize_investigation(question, findings)
    report_md = "\n".join([f"# Investigation: {question}", "", "## Summary", synthesis, "", *report_sections])

    control_session = get_sync_session()
    try:
        file = File(
            workspace_id=job.workspace_id,
            parent_id=None,
            name=f"Investigation - {question[:60].strip()} - {str(job.id)[:8]}.md",
            is_folder=False,
            content=report_md,
            created_by=job.created_by,
        )
        control_session.add(file)
        control_session.add(AuditLogEntry(workspace_id=job.workspace_id, user_id=job.created_by, action="file.created", detail=file.name))
        control_session.commit()
        control_session.refresh(file)
        file_id = str(file.id)
    finally:
        control_session.close()

    return {"file_id": file_id, "summary": _truncate(synthesis, 400), "provider_fallback": fallback_reason}


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    # Cut at the last word boundary within the limit, not mid-word/mid-token
    # -- a hard slice can land inside a markdown marker (e.g. "**next step:*")
    # and show a dangling artifact to whoever's reading the job summary.
    cut = text[:limit].rsplit(" ", 1)[0] or text[:limit]
    return f"{cut}…"


def _execute(service: AIService, job: AiJob) -> dict:
    task_type, input = job.task_type, job.input
    if task_type == "generate":
        sql, fallback_reason = service.generate_sql(input["prompt"])
        return {"sql": sql, "provider_fallback": fallback_reason}
    if task_type == "explain":
        return service.explain_sql(input["sql"]).model_dump()
    if task_type == "repair":
        return service.repair_sql(input["sql"], input.get("error_message", "")).model_dump()
    if task_type == "suggest":
        return service.suggest_tables(input["prompt"]).model_dump()
    if task_type == "investigate":
        return _run_investigation(job)
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
            job.result = _execute(AIService(), job)
            job.status = "done"
        except Exception as exc:
            job.error = str(exc)
            job.status = "failed"
        job.finished_at = datetime.utcnow()
        session.commit()
    finally:
        session.close()
