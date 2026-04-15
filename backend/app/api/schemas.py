"""Request and response schemas for the API."""
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    ai_provider: str


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


class SQLExecutionResponse(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    execution_ms: int
    message: str


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
