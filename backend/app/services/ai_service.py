"""Schema-aware local AI services for generation, explanation, repair, and suggestions."""
from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

from app.api.schemas import ExplainSQLResponse, RepairSQLResponse, SchemaResponse, SQLExecutionResponse, SuggestTablesResponse, TableSuggestion
from app.core.config import get_settings
from app.llm.providers import MockProvider, get_provider
from app.observability.metrics import record_ai_call
from app.services.schema_service import SchemaService
from app.utils.schema_text import schema_to_prompt_text

if TYPE_CHECKING:
    # Deferred to TYPE_CHECKING only, never imported at runtime here: this
    # module is reachable from test files that don't always import
    # app.main (and therefore app.auth.models) first, and DataConnection's
    # own GUID import trips fastapi-users-db-sqlalchemy 7.0.0's import-
    # order bug if it lands before app.auth.models does (see alembic/env.py
    # for the full explanation -- this is the same bug class, bite #5's
    # near-miss, avoided rather than fixed here).
    from app.connections.models import DataConnection

logger = logging.getLogger(__name__)

# Every generate_sql/repair_sql caller used to implicitly target the bundled
# demo database, which is SQLite -- so the prompt hardcoded "SQLite" and
# nobody noticed. Once a caller can pass a real connection's schema (Phase
# 3c, connection-aware AI), the dialect must travel with it: generating
# correct table names in the wrong dialect (e.g. SQLite's strftime() against
# a Postgres connection) still fails at execution. Keys match
# app.connections.drivers.SQLGLOT_DIALECT_BY_TYPE / DataConnection.connector_type.
SQL_DIALECT_LABEL = {
    "postgres": "PostgreSQL",
    "mysql": "MySQL",
    "sqlite": "SQLite",
    "snowflake": "Snowflake SQL",
    "bigquery": "BigQuery Standard SQL",
    "databricks": "Databricks SQL (Spark SQL)",
}


class AIService:
    def __init__(self) -> None:
        self.provider = get_provider()
        self.fallback = MockProvider()
        self.schema_service = SchemaService()

    def status(self) -> dict:
        return self.provider.status()

    def _generate(self, prompt_text: str, *, task: str) -> tuple[str, str | None]:
        """Returns (text, fallback_reason). fallback_reason is None on the
        happy path and a human-readable explanation whenever the real
        provider failed and mock output was substituted instead — callers
        must surface this to the user rather than silently swallowing it.

        task is one of generate|explain|repair|suggest|investigate --
        resolved to a concrete model via Settings.model_for_task(), so every
        caller (the legacy v1 endpoints included) gets task-appropriate
        model routing without needing to know or pass a model themselves."""
        model = get_settings().model_for_task(task)
        try:
            result = self.provider.generate(prompt_text, model=model), None
        except Exception as exc:
            reason = f"{self.provider.provider_name} provider failed ({exc}); used local mock fallback instead."
            logger.warning("AI provider fallback: %s", reason)
            result = self.fallback.generate(f"{prompt_text}\n\nProvider failure fallback reason: {exc}"), reason
        record_ai_call(result[1])
        return result

    def _schema_text(self, schema: SchemaResponse | None = None) -> str:
        return schema_to_prompt_text(schema or self.schema_service.get_schema())

    def generate_sql(self, prompt: str, schema: SchemaResponse | None = None, dialect: str = "SQLite") -> tuple[str, str | None]:
        prompt_text = f"""
You are an expert {dialect} analyst working inside a local-only SQL workbench.
Use only the schema below. Never invent tables or columns.
Return SQL only, no markdown, no commentary.
Rules:
- Use read-only SELECT/WITH SQL only.
- Prefer explicit joins.
- Include a LIMIT unless the user asks for an aggregate-only single-row answer.
- Use {dialect}-compatible syntax.

Schema:
{self._schema_text(schema)}

Business question: {prompt}
"""
        raw, fallback_reason = self._generate(prompt_text, task="generate")
        return self._strip_code_fences(raw), fallback_reason

    def explain_sql(self, sql: str) -> ExplainSQLResponse:
        prompt_text = f"""
Explain this SQLite query in plain English for an analyst.
Focus on tables used, joins, filters, grouping, sorting, and returned fields.
Be concise.

SQL:
```sql
{sql}
```
"""
        explanation, fallback_reason = self._generate(prompt_text, task="explain")
        return ExplainSQLResponse(explanation=explanation, provider_fallback=fallback_reason)

    def explain_result(self, question: str, sql: str, result: SQLExecutionResponse) -> tuple[str, str | None]:
        sample_rows = result.rows[:10]
        prompt_text = f"""
Explain the query result for an analyst.
Do not invent facts beyond the rows shown.
Mention row count, obvious top/bottom values, caveats, and one next analysis.

Original question: {question}
SQL:
```sql
{sql}
```
Columns: {result.columns}
Row count: {result.row_count}
Sample rows JSON:
{json.dumps(sample_rows, default=str)}
"""
        text, fallback_reason = self._generate(prompt_text, task="explain")
        return text.strip(), fallback_reason

    def repair_sql(self, sql: str, error_message: str = "", schema: SchemaResponse | None = None, dialect: str = "SQLite") -> RepairSQLResponse:
        prompt_text = f"""
Repair the following {dialect} query.
Return SQL only.
Use only the schema below and keep the query read-only.

Schema:
{self._schema_text(schema)}

Error: {error_message}
SQL:
```sql
{sql}
```
"""
        raw, fallback_reason = self._generate(prompt_text, task="repair")
        repaired = self._strip_code_fences(raw)
        if self._normalize_sql(repaired) == self._normalize_sql(sql):
            rationale = "No automatic correction could be generated; the original SQL was returned unchanged. Please review the query manually."
        else:
            rationale = "Generated a safer or syntactically corrected read-only SQL statement."
        return RepairSQLResponse(repaired_sql=repaired, rationale=rationale, provider_fallback=fallback_reason)

    def suggest_tables(self, prompt: str, schema: SchemaResponse | None = None, connection: DataConnection | None = None) -> SuggestTablesResponse:
        if connection is not None:
            via_embeddings = self._suggest_tables_via_embeddings(prompt, connection, schema)
            if via_embeddings is not None:
                return via_embeddings
        schema = schema or self.schema_service.get_schema()
        prompt_text = f"""
Suggest relevant tables for this analyst request.
Respond as JSON with keys suggestions and join_suggestions.
Each suggestion should contain table_name, reason, and suggested_columns.
Use only tables and columns from the schema.

Schema:
{schema_to_prompt_text(schema)}
Request: {prompt}
"""
        raw, fallback_reason = self._generate(prompt_text, task="suggest")
        try:
            payload = json.loads(self._extract_json(raw))
            suggestions = [TableSuggestion(**item) for item in payload.get("suggestions", [])]
            joins = payload.get("join_suggestions", [])
            # Validate against actual schema so model output cannot invent names.
            table_map = {table.name: {column.name for column in table.columns} for table in schema.tables}
            filtered: list[TableSuggestion] = []
            for suggestion in suggestions:
                if suggestion.table_name in table_map:
                    suggestion.suggested_columns = [col for col in suggestion.suggested_columns if col in table_map[suggestion.table_name]][:8]
                    filtered.append(suggestion)
            if filtered:
                return SuggestTablesResponse(suggestions=filtered[:6], join_suggestions=joins[:6], provider_fallback=fallback_reason)
        except Exception:
            pass

        keywords = {word.strip("?,.").lower() for word in prompt.split() if len(word) > 3}
        fallback = []
        for table in schema.tables:
            col_names = [c.name for c in table.columns]
            if any(k in table.name.lower() or any(k in c.lower() for c in col_names) for k in keywords):
                fallback.append(TableSuggestion(table_name=table.name, reason="Matched prompt keywords.", suggested_columns=col_names[:5]))
        if not fallback:
            fallback = [TableSuggestion(table_name=table.name, reason="Included as general schema context.", suggested_columns=[c.name for c in table.columns[:5]]) for table in schema.tables[:3]]
        joins = self._heuristic_join_suggestions(schema)
        return SuggestTablesResponse(suggestions=fallback[:5], join_suggestions=joins[:5], provider_fallback=fallback_reason)

    def _suggest_tables_via_embeddings(self, prompt: str, connection: DataConnection, schema: SchemaResponse | None) -> SuggestTablesResponse | None:
        """Deterministic, cheaper alternative to the LLM-based suggestion
        call above: ranks this connection's real tables by cosine
        similarity to the question instead of asking the model to guess.
        Returns None (not a fallback response) whenever embeddings aren't
        usable here -- mock AI mode, an unreachable embedding model, or a
        connection with no schema -- so the caller falls through to the
        existing LLM+keyword path and surfaces that as normal.

        Imports are local, not top-of-module: this module is reachable
        from test files that don't always import app.main (and therefore
        app.auth.models) first, and embedding_models.SchemaEmbedding's own
        GUID import trips fastapi-users-db-sqlalchemy's import-order bug if
        it lands first. Deferred past every test's client-fixture import of
        app.main sidesteps that entirely -- see the TYPE_CHECKING note atop
        this file for the same bug class."""
        if schema is None:
            return None
        from app.connections.embedding_service import ensure_embeddings, find_relevant_tables
        from app.db.control_plane_sync import get_sync_session

        session = get_sync_session()
        try:
            provider_name = self.provider.provider_name
            ready = ensure_embeddings(session, workspace_id=connection.workspace_id, connection_id=connection.id, schema=schema, provider_name=provider_name)
            if not ready:
                return None
            hits = find_relevant_tables(session, connection_id=connection.id, question=prompt, provider_name=provider_name, top_k=5)
            if not hits:
                return None
            suggestions = [
                TableSuggestion(
                    table_name=hit.table_name,
                    reason=f"Semantically relevant to this question (embedding-ranked, {self.provider.provider_name}/{get_settings().schema_embedding_model}).",
                    suggested_columns=list(hit.column_names)[:8],
                )
                for hit in hits
            ]
            return SuggestTablesResponse(suggestions=suggestions, join_suggestions=self._heuristic_join_suggestions(schema)[:5], provider_fallback=None)
        finally:
            session.close()

    def synthesize_investigation(self, question: str, findings: list[dict]) -> tuple[str, str | None]:
        """Ties together the results of a multi-step investigation (the
        original question plus at least one automatic follow-up) into a
        short written report. This is the step that makes "investigate" a
        distinct task from calling assistant/run twice: the model reads
        both results together and writes up what they mean side by side,
        not just what each one says in isolation."""
        sections = []
        for i, finding in enumerate(findings, start=1):
            sections.append(
                f"Step {i} question: {finding['question']}\n"
                f"SQL used:\n{finding['sql']}\n"
                f"Rows returned: {finding['row_count']}\n"
                f"Sample rows: {json.dumps(finding.get('sample', []), default=str)}"
            )
        prompt_text = f"""
INVESTIGATION REPORT

You are a data analyst. Write a concise investigation summary (3-6 sentences,
markdown) describing what the findings below show for this question, tying
the steps together rather than describing them one at a time. End with one
concrete suggested next step.

Original question: {question}

{chr(10).join(sections)}
"""
        text, fallback_reason = self._generate(prompt_text, task="investigate")
        return text.strip(), fallback_reason

    def ask(self, mode: str, prompt: str | None = None, sql: str | None = None, error_message: str | None = None):
        if mode == "generate":
            sql_text, fallback_reason = self.generate_sql(prompt or "")
            return {"sql": sql_text, "provider_fallback": fallback_reason}
        if mode == "explain":
            return self.explain_sql(sql or "").model_dump()
        if mode == "repair":
            return self.repair_sql(sql or "", error_message or "").model_dump()
        if mode == "suggest":
            return self.suggest_tables(prompt or "").model_dump()
        raise ValueError(f"Unsupported mode: {mode}")

    @staticmethod
    def _normalize_sql(text: str) -> str:
        """Whitespace/case/trailing-semicolon-insensitive comparison, and
        also ignores a trailing LIMIT clause: appending a LIMIT does not fix
        the kind of error repair_sql is invoked for (missing table/column,
        syntax error), so it must not by itself count as a "real" repair."""
        normalized = re.sub(r"\s+", " ", (text or "").strip()).rstrip(";").strip().lower()
        return re.sub(r"\s+limit\s+\d+\s*$", "", normalized).strip()

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        text = (text or "").strip()
        match = re.search(r"```(?:sql)?\s*(.*?)```", text, re.S | re.I)
        if match:
            return match.group(1).strip()
        text = re.sub(r"^```sql\s*", "", text, flags=re.I)
        text = re.sub(r"^```", "", text)
        text = re.sub(r"```$", "", text)
        return text.strip()

    @staticmethod
    def _extract_json(text: str) -> str:
        match = re.search(r"\{.*\}", text or "", re.S)
        return match.group(0) if match else text

    @staticmethod
    def _heuristic_join_suggestions(schema) -> list[str]:
        joins: list[str] = []
        for table in schema.tables:
            for col in table.columns:
                if col.is_foreign_key and col.references:
                    joins.append(f"{table.name}.{col.name} = {col.references}")
        return joins
