"""Request and response schemas for the API."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    app_version: str
    ai_provider: str
    ai_mode: str
    api_prefix: str = "/api"
    database: str = "ok"
    db_row_counts: dict[str, int] = Field(default_factory=dict)


class AIStatusResponse(BaseModel):
    provider: str
    status: Literal["connected", "not_configured", "error", "mock"]
    active_model: str | None = None
    base_url: str | None = None
    available_models: list[str] = []
    message: str
    local_only: bool = True


class ColumnSchema(BaseModel):
    name: str
    data_type: str
    is_primary_key: bool = False
    is_foreign_key: bool = False
    references: str | None = None


class TableSchema(BaseModel):
    name: str
    columns: list[ColumnSchema]


class SchemaResponse(BaseModel):
    tables: list[TableSchema]


class TablePreviewResponse(BaseModel):
    table_name: str
    columns: list[str]
    rows: list[dict[str, Any]]


class SQLTextRequest(BaseModel):
    sql: str


class PromptRequest(BaseModel):
    prompt: str
    schema_context: str | None = None


class GenerateSQLRequest(BaseModel):
    prompt: str


class SQLValidationResponse(BaseModel):
    valid: bool
    normalized_sql: str | None = None
    warnings: list[str] = []
    errors: list[str] = []


class SQLExecutionRequest(BaseModel):
    sql: str
    use_cache: bool = True


class SQLExecutionResponse(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    execution_ms: int
    message: str
    cached: bool = False


class ExplainSQLResponse(BaseModel):
    explanation: str


class RepairSQLRequest(BaseModel):
    sql: str
    error_message: str = ""


class RepairSQLResponse(BaseModel):
    repaired_sql: str
    rationale: str


class SuggestTablesRequest(BaseModel):
    prompt: str


class TableSuggestion(BaseModel):
    table_name: str
    reason: str
    suggested_columns: list[str] = []


class SuggestTablesResponse(BaseModel):
    suggestions: list[TableSuggestion]
    join_suggestions: list[str] = []


class AskRequest(BaseModel):
    mode: Literal["generate", "explain", "repair", "suggest"]
    prompt: str | None = None
    sql: str | None = None
    error_message: str | None = None


class AssistantRunRequest(BaseModel):
    question: str = Field(min_length=1)
    execute: bool = True
    explain: bool = True
    use_cache: bool = True


class AssistantStep(BaseModel):
    name: str
    status: Literal["success", "warning", "error", "cached", "skipped"] = "success"
    detail: str


class AssistantRunResponse(BaseModel):
    status: Literal["success", "error"]
    question: str
    sql: str | None = None
    result: SQLExecutionResponse | None = None
    explanation: str | None = None
    suggestions: list[TableSuggestion] = []
    join_suggestions: list[str] = []
    next_questions: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []
    steps: list[AssistantStep] = []
    cached: bool = False
    memory_id: int | None = None
    confidence: float = 0.0


class AssistantFeedbackRequest(BaseModel):
    memory_id: int
    positive: bool


class AssistantFeedbackResponse(BaseModel):
    stored: bool
    memory_id: int
    positive_feedback: int
    negative_feedback: int


class AssistantMemoryItem(BaseModel):
    id: int
    question: str
    sql_text: str
    confidence: float
    use_count: int
    positive_feedback: int
    negative_feedback: int
    updated_at: datetime


class HistoryItem(BaseModel):
    id: int
    sql_text: str
    status: str
    row_count: int
    execution_ms: int
    error_message: str | None = None
    created_at: datetime


class SavedQueryCreate(BaseModel):
    name: str = Field(min_length=1)
    sql_text: str = Field(min_length=1)
    description: str | None = None


class SavedQueryResponse(BaseModel):
    id: int
    name: str
    sql_text: str
    description: str | None = None
    created_at: datetime
