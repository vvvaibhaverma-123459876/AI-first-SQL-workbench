"""FastAPI routes for AI SQL Studio."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from app.api.schemas import (
    AskRequest,
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
from app.core.config import get_settings
from app.db.session import get_metadata_session
from app.services.ai_service import AIService
from app.services.execution_service import SQLExecutionService
from app.services.history_service import HistoryService
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


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", ai_provider=get_settings().ai_provider)


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
        response = execution_service.execute(payload.sql)
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
