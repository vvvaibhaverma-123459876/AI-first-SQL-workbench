"""Pydantic schemas for the connections API, plus the per-connector-type
config models that validate what a user submits before it's encrypted and
stored. Each *Config model is the single source of truth for what fields
that connector type needs -- drivers.py builds a SQLAlchemy URL from it."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field


class PostgresConfig(BaseModel):
    connector_type: Literal["postgres"] = "postgres"
    host: str
    port: int = 5432
    database: str
    username: str
    password: str


class MySQLConfig(BaseModel):
    connector_type: Literal["mysql"] = "mysql"
    host: str
    port: int = 3306
    database: str
    username: str
    password: str


class SQLiteConfig(BaseModel):
    connector_type: Literal["sqlite"] = "sqlite"
    # Path to a .db file on the server filesystem the backend process can
    # read. Uploading a file for per-workspace storage is a natural follow-up
    # but is out of scope here -- this phase is the connector layer, not the
    # file-management system (that's Phase 1's file tree, already shipped).
    path: str


class SnowflakeConfig(BaseModel):
    connector_type: Literal["snowflake"] = "snowflake"
    account: str
    user: str
    password: str
    warehouse: str
    database: str
    schema_name: str = Field(alias="schema")
    role: str | None = None

    model_config = {"populate_by_name": True}


class BigQueryConfig(BaseModel):
    connector_type: Literal["bigquery"] = "bigquery"
    project_id: str
    dataset: str | None = None
    # Contents of a GCP service-account JSON key, pasted as-is. Stored
    # encrypted like every other credential field here.
    service_account_json: str


class DatabricksConfig(BaseModel):
    connector_type: Literal["databricks"] = "databricks"
    server_hostname: str
    http_path: str
    access_token: str
    catalog: str | None = None
    schema_name: str | None = Field(default=None, alias="schema")

    model_config = {"populate_by_name": True}


ConnectionConfig = Annotated[
    Union[PostgresConfig, MySQLConfig, SQLiteConfig, SnowflakeConfig, BigQueryConfig, DatabricksConfig],
    Field(discriminator="connector_type"),
]

CONFIG_MODELS_BY_TYPE: dict[str, type[BaseModel]] = {
    "postgres": PostgresConfig,
    "mysql": MySQLConfig,
    "sqlite": SQLiteConfig,
    "snowflake": SnowflakeConfig,
    "bigquery": BigQueryConfig,
    "databricks": DatabricksConfig,
}


class DataConnectionCreate(BaseModel):
    name: str
    config: ConnectionConfig


class DataConnectionRead(BaseModel):
    id: uuid.UUID
    name: str
    connector_type: str
    created_at: datetime
    last_tested_at: datetime | None
    last_test_ok: bool | None

    model_config = {"from_attributes": True}


class TestConnectionResult(BaseModel):
    ok: bool
    message: str


class ColumnInfo(BaseModel):
    name: str
    type: str
    nullable: bool


class TableInfo(BaseModel):
    schema_name: str | None
    name: str
    columns: list[ColumnInfo]


class QueryRequest(BaseModel):
    sql: str


class QueryResponse(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    truncated: bool
    execution_ms: int
