"""FastAPI routes for AI SQL Studio."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.api.schemas import (
    AIStatusResponse,
    AskRequest,
    AssistantFeedbackRequest,
    AssistantFeedbackResponse,
    AssistantMemoryItem,
    AssistantRunRequest,
    AssistantRunResponse,
    ExplainSQLResponse,
    GenerateSQLRequest,
    HealthResponse,
    RepairSQLRequest,
    RepairSQLResponse,
    SQLExecutionRequest,
    SQLExecutionResponse,
    SQLTextRequest,
    SQLValidationResponse,
    SavedQueryCreate,
    SavedQueryResponse,
    SchemaResponse,
    SuggestTablesRequest,
    SuggestTablesResponse,
    TablePreviewResponse,
)
from app.assistant.orchestrator import AssistantOrchestrator
from app.core.config import get_settings
from app.db.session import analytics_engine, get_metadata_session
from app.services.ai_service import AIService
from app.services.execution_service import SQLExecutionService
from app.services.history_service import HistoryService
from app.services.learning_memory_service import LearningMemoryService
from app.services.saved_query_service import SavedQueryService
from app.services.schema_service import SchemaService
from app.services.validation_service import SQLValidationService

router = APIRouter()
schema_service = SchemaService()
validation_service = SQLValidationService()
execution_service = SQLExecutionService()
ai_service = AIService()
history_service = HistoryService()
saved_query_service = SavedQueryService()
assistant_orchestrator = AssistantOrchestrator()
memory_service = LearningMemoryService()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    inspector = inspect(analytics_engine)
    row_counts: dict[str, int] = {}
    with analytics_engine.connect() as conn:
        for table_name in inspector.get_table_names():
            row_counts[table_name] = conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"')).scalar_one()
    return HealthResponse(
        status="ok",
        app_version=settings.app_version,
        ai_provider=settings.ai_provider,
        ai_mode=settings.effective_ai_mode,
        api_prefix=settings.api_prefix,
        database="ok",
        db_row_counts=row_counts,
    )


@router.get("/ai/status", response_model=AIStatusResponse)
def ai_status() -> AIStatusResponse:
    return AIStatusResponse(**ai_service.status())


@router.get("/schema", response_model=SchemaResponse)
def get_schema() -> SchemaResponse:
    return schema_service.get_schema()


@router.get("/tables/{table_name}/preview", response_model=TablePreviewResponse)
def preview_table(table_name: str) -> TablePreviewResponse:
    try:
        return schema_service.preview_table(table_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/generate-sql")
def generate_sql(payload: GenerateSQLRequest):
    return {"sql": ai_service.generate_sql(payload.prompt)}


@router.post("/validate-sql", response_model=SQLValidationResponse)
def validate_sql(payload: SQLTextRequest) -> SQLValidationResponse:
    return validation_service.validate(payload.sql)


@router.post("/execute-sql", response_model=SQLExecutionResponse)
def execute_sql(payload: SQLExecutionRequest, db: Session = Depends(get_metadata_session)) -> SQLExecutionResponse:
    try:
        response = execution_service.execute(payload.sql, metadata_db=db, use_cache=payload.use_cache)
        history_service.log(db, payload.sql, "success", response.row_count, response.execution_ms)
        return response
    except ValueError as exc:
        history_service.log(db, payload.sql, "error", 0, 0, str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/execute-sql/export", response_class=PlainTextResponse)
def export_sql(payload: SQLExecutionRequest) -> str:
    try:
        return execution_service.export_csv_text(payload.sql)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/explain-sql", response_model=ExplainSQLResponse)
def explain_sql(payload: SQLTextRequest) -> ExplainSQLResponse:
    return ai_service.explain_sql(payload.sql)


@router.post("/repair-sql", response_model=RepairSQLResponse)
def repair_sql(payload: RepairSQLRequest) -> RepairSQLResponse:
    return ai_service.repair_sql(payload.sql, payload.error_message)


@router.post("/suggest-tables", response_model=SuggestTablesResponse)
def suggest_tables(payload: SuggestTablesRequest) -> SuggestTablesResponse:
    return ai_service.suggest_tables(payload.prompt)


@router.post("/ask")
def ask(payload: AskRequest):
    try:
        return ai_service.ask(payload.mode, payload.prompt, payload.sql, payload.error_message)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/assistant/run", response_model=AssistantRunResponse)
def assistant_run(payload: AssistantRunRequest, db: Session = Depends(get_metadata_session)) -> AssistantRunResponse:
    return assistant_orchestrator.run(db, payload.question, execute=payload.execute, explain=payload.explain, use_cache=payload.use_cache)


@router.post("/assistant/feedback", response_model=AssistantFeedbackResponse)
def assistant_feedback(payload: AssistantFeedbackRequest, db: Session = Depends(get_metadata_session)) -> AssistantFeedbackResponse:
    item = memory_service.feedback(db, payload.memory_id, payload.positive)
    if not item:
        raise HTTPException(status_code=404, detail="Assistant memory item not found")
    return AssistantFeedbackResponse(stored=True, memory_id=item.id, positive_feedback=item.positive_feedback, negative_feedback=item.negative_feedback)


@router.get("/assistant/memory", response_model=list[AssistantMemoryItem])
def assistant_memory(db: Session = Depends(get_metadata_session)) -> list[AssistantMemoryItem]:
    return [
        AssistantMemoryItem(
            id=item.id,
            question=item.question,
            sql_text=item.sql_text,
            confidence=item.confidence,
            use_count=item.use_count,
            positive_feedback=item.positive_feedback,
            negative_feedback=item.negative_feedback,
            updated_at=item.updated_at,
        )
        for item in memory_service.list_recent(db)
    ]


@router.get("/history")
def history(db: Session = Depends(get_metadata_session)):
    return history_service.list(db)


@router.post("/saved-queries", response_model=SavedQueryResponse)
def create_saved_query(payload: SavedQueryCreate, db: Session = Depends(get_metadata_session)) -> SavedQueryResponse:
    return saved_query_service.create(db, payload.name, payload.sql_text, payload.description)


@router.get("/saved-queries", response_model=list[SavedQueryResponse])
def list_saved_queries(db: Session = Depends(get_metadata_session)) -> list[SavedQueryResponse]:
    return saved_query_service.list(db)


@router.get("/saved-queries/{query_id}", response_model=SavedQueryResponse)
def get_saved_query(query_id: int, db: Session = Depends(get_metadata_session)) -> SavedQueryResponse:
    obj = saved_query_service.get(db, query_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Saved query not found")
    return obj


@router.delete("/saved-queries/{query_id}")
def delete_saved_query(query_id: int, db: Session = Depends(get_metadata_session)):
    deleted = saved_query_service.delete(db, query_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Saved query not found")
    return {"deleted": True}
