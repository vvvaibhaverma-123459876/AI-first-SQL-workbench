"""End-to-end local AI analyst orchestration."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.api.schemas import AssistantRunResponse, AssistantStep, ColumnSchema, SchemaResponse, SQLExecutionResponse, SQLValidationResponse, TableSchema
from app.connections import service as connections_service
from app.connections.models import DataConnection
from app.core.config import get_settings
from app.services.ai_service import SQL_DIALECT_LABEL, AIService
from app.services.execution_service import SQLExecutionService
from app.services.history_service import HistoryService
from app.services.learning_memory_service import LearningMemoryService
from app.services.validation_service import SQLValidationService


def schema_for_connection(connection: DataConnection) -> SchemaResponse:
    """Adapts connections.service's own schema shape (TableInfo/ColumnInfo --
    simpler than the legacy SchemaService's, with no PK/FK detection) into
    the AIService/prompt-building shape. Missing PK/FK annotations degrade
    gracefully -- schema_to_prompt_text() just omits them, it doesn't need
    them to be present."""
    tables = connections_service.get_schema_sync(connection)
    return SchemaResponse(
        tables=[
            TableSchema(name=table.name, columns=[ColumnSchema(name=col.name, data_type=col.type) for col in table.columns])
            for table in tables
        ]
    )


def _validate_for_connection(sql: str, connection: DataConnection) -> SQLValidationResponse:
    """Deliberately NOT SQLValidationService.validate(): that re-serializes
    through sqlglot's sqlite dialect (and injects a bare LIMIT), which would
    silently corrupt syntax for any other dialect (Postgres/MySQL/Snowflake/
    BigQuery/Databricks). connections.service.is_read_only_sql() is the same
    dialect-aware, non-rewriting check Phase 2's own query route already
    uses -- reused here rather than reinvented."""
    sql = (sql or "").strip()
    if not sql:
        return SQLValidationResponse(valid=False, errors=["SQL cannot be empty."])
    if connections_service.is_read_only_sql(sql, connector_type=connection.connector_type):
        return SQLValidationResponse(valid=True, normalized_sql=sql, warnings=[], errors=[])
    return SQLValidationResponse(valid=False, errors=["Only read-only SELECT/WITH queries are allowed for this connection."])


def _execute_on_connection(sql: str, connection: DataConnection) -> SQLExecutionResponse:
    qr = connections_service.run_query_sync(connection, sql)  # raises ValueError on failure, same contract as SQLExecutionService.execute
    message = "Query executed successfully." if not qr.truncated else f"Query executed successfully (truncated to {len(qr.rows)} row(s))."
    return SQLExecutionResponse(columns=qr.columns, rows=qr.rows, row_count=qr.row_count, execution_ms=qr.execution_ms, message=message, cached=False)


class AssistantOrchestrator:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.ai = AIService()
        self.validator = SQLValidationService()
        self.executor = SQLExecutionService()
        self.history = HistoryService()
        self.memory = LearningMemoryService()

    @staticmethod
    def _note_fallback(fallback_reason: str | None, warnings: list[str], steps: list[AssistantStep]) -> None:
        if not fallback_reason:
            return
        steps.append(AssistantStep(name="provider_fallback", status="warning", detail=fallback_reason))
        if fallback_reason not in warnings:
            warnings.append(fallback_reason)

    def run(
        self,
        db: Session,
        question: str,
        execute: bool = True,
        explain: bool = True,
        use_cache: bool = True,
        connection: DataConnection | None = None,
        schema: SchemaResponse | None = None,
    ) -> AssistantRunResponse:
        # A real connection's SQL/question memory isn't scoped by
        # connection_id (see LearningMemoryService/ResultCacheService --
        # both key on text alone), so reusing either across connections
        # could silently serve one connection's cached answer for another's
        # question against a different schema. Bypass both rather than risk
        # that; caching connection-scoped runs is a real future improvement,
        # deliberately not built here (documented gap, not a silent one).
        use_cache = use_cache and connection is None
        dialect = SQL_DIALECT_LABEL.get(connection.connector_type, "SQLite") if connection is not None else "SQLite"
        if connection is not None and schema is None:
            schema = schema_for_connection(connection)
        steps: list[AssistantStep] = []
        warnings: list[str] = []
        errors: list[str] = []
        sql: str | None = None
        result: SQLExecutionResponse | None = None
        explanation: str | None = None
        memory_id: int | None = None
        cached = False
        confidence = 0.55

        try:
            suggestions = self.ai.suggest_tables(question, schema=schema)
            self._note_fallback(suggestions.provider_fallback, warnings, steps)
            selected_tables = [item.table_name for item in suggestions.suggestions]
            steps.append(AssistantStep(name="schema_retrieval", detail=f"Selected {len(selected_tables)} relevant table(s): {', '.join(selected_tables) or 'heuristic fallback'}."))

            if use_cache and self.settings.assistant_cache_enabled:
                hit = self.memory.find_best(db, question, self.settings.assistant_cache_min_score)
                if hit:
                    sql = hit.item.sql_text
                    explanation = hit.item.explanation
                    memory_id = hit.item.id
                    cached = True
                    confidence = min(1.0, hit.score)
                    steps.append(AssistantStep(name="local_memory", status="cached", detail=f"Reused locally learned SQL memory with similarity score {hit.score:.2f}. Ollama was skipped."))

            if not sql:
                sql, fallback_reason = self.ai.generate_sql(question, schema=schema, dialect=dialect)
                self._note_fallback(fallback_reason, warnings, steps)
                steps.append(AssistantStep(name="sql_generation", detail="Generated SQL using the configured local AI provider."))

            # Validate and optionally repair.
            validation = _validate_for_connection(sql, connection) if connection is not None else self.validator.validate(sql)
            repair_attempts = 0
            while not validation.valid and repair_attempts < self.settings.max_repair_attempts:
                repair_attempts += 1
                warnings.extend(validation.errors)
                repaired = self.ai.repair_sql(sql, "; ".join(validation.errors), schema=schema, dialect=dialect)
                self._note_fallback(repaired.provider_fallback, warnings, steps)
                sql = repaired.repaired_sql
                steps.append(AssistantStep(name="sql_repair", status="warning", detail=f"Repair attempt {repair_attempts}: {repaired.rationale}"))
                validation = _validate_for_connection(sql, connection) if connection is not None else self.validator.validate(sql)

            if not validation.valid or not validation.normalized_sql:
                errors.extend(validation.errors)
                return AssistantRunResponse(
                    status="error",
                    question=question,
                    sql=sql,
                    suggestions=suggestions.suggestions,
                    join_suggestions=suggestions.join_suggestions,
                    warnings=warnings,
                    errors=errors,
                    steps=steps,
                    cached=cached,
                    memory_id=memory_id,
                    confidence=confidence,
                )

            sql = validation.normalized_sql
            steps.append(AssistantStep(name="sql_validation", detail="SQL passed read-only validation and safety checks."))
            warnings.extend(validation.warnings)

            if execute:
                try:
                    result = _execute_on_connection(sql, connection) if connection is not None else self.executor.execute(sql, metadata_db=db, use_cache=use_cache)
                    self.history.log(db, sql, "success", result.row_count, result.execution_ms)
                    steps.append(AssistantStep(
                        name="execution",
                        status="cached" if result.cached else "success",
                        detail=f"Returned {result.row_count} row(s) in {result.execution_ms} ms." if not result.cached else result.message,
                    ))
                except ValueError as exc:
                    self.history.log(db, sql, "error", 0, 0, str(exc))
                    # One final repair-and-run pass for runtime errors.
                    repaired = self.ai.repair_sql(sql, str(exc), schema=schema, dialect=dialect)
                    self._note_fallback(repaired.provider_fallback, warnings, steps)
                    sql = repaired.repaired_sql
                    steps.append(AssistantStep(name="runtime_repair", status="warning", detail="Execution failed once; generated a repaired SQL candidate."))
                    result = None
                    errors.append(str(exc))
            else:
                steps.append(AssistantStep(name="execution", status="skipped", detail="Execution was skipped by request."))

            if explain:
                if result and result.rows:
                    explanation, fallback_reason = self.ai.explain_result(question, sql, result)
                    self._note_fallback(fallback_reason, warnings, steps)
                    steps.append(AssistantStep(name="result_explanation", detail="Generated result-level explanation locally."))
                elif not explanation:
                    explained = self.ai.explain_sql(sql)
                    explanation = explained.explanation
                    self._note_fallback(explained.provider_fallback, warnings, steps)
                    steps.append(AssistantStep(name="sql_explanation", detail="Generated SQL explanation locally."))

            confidence = self._confidence(sql=sql, result=result, cached=cached, warning_count=len(warnings), error_count=len(errors))
            # connection is None check, not just use_cache: without it, a
            # connection-scoped SQL would still get written into this
            # question-text-keyed global memory, and a later unrelated demo
            # question with high fuzzy similarity could then be served that
            # connection's SQL as a "cached hit" -- writing, not just
            # reading, has to be scoped by connection.
            if not cached and sql and connection is None:
                memory = self.memory.upsert(
                    db,
                    question=question,
                    sql_text=sql,
                    explanation=explanation,
                    selected_tables=selected_tables,
                    confidence=confidence,
                )
                memory_id = memory.id
                steps.append(AssistantStep(name="local_learning", detail="Stored this successful assistant run in local memory for faster future reuse."))

            return AssistantRunResponse(
                status="success" if not errors else "error",
                question=question,
                sql=sql,
                result=result,
                explanation=explanation,
                suggestions=suggestions.suggestions,
                join_suggestions=suggestions.join_suggestions,
                next_questions=self._next_questions(question, selected_tables),
                warnings=warnings,
                errors=errors,
                steps=steps,
                cached=cached,
                memory_id=memory_id,
                confidence=confidence,
            )
        except Exception as exc:  # keep API responses useful instead of crashing UI
            errors.append(str(exc))
            steps.append(AssistantStep(name="assistant", status="error", detail=str(exc)))
            return AssistantRunResponse(status="error", question=question, sql=sql, explanation=explanation, warnings=warnings, errors=errors, steps=steps, cached=cached, memory_id=memory_id, confidence=confidence)

    def _confidence(self, sql: str, result: SQLExecutionResponse | None, cached: bool, warning_count: int, error_count: int) -> float:
        score = 0.62
        if sql and " join " in sql.lower():
            score += 0.05
        if result is not None:
            score += 0.12
        if result is not None and result.row_count > 0:
            score += 0.08
        if cached:
            score += 0.08
        score -= min(0.25, warning_count * 0.03 + error_count * 0.08)
        return max(0.0, min(1.0, score))

    def _next_questions(self, question: str, selected_tables: list[str]) -> list[str]:
        q = question.lower()
        if any(term in q for term in ["drop", "decline", "why", "issue", "failed", "failure"]):
            return [
                "Break this result down by week and acquisition channel.",
                "Check whether the drop is concentrated in new users or returning users.",
                "Compare the same metric by status, app version, or source if available.",
            ]
        if any(term in q for term in ["channel", "source", "referral", "campaign"]):
            return [
                "Show the same metric by signup month.",
                "Compare conversion rate instead of absolute volume.",
                "Find the top and bottom performing channels with sample size.",
            ]
        table_hint = selected_tables[0] if selected_tables else "the selected table"
        return [
            f"Show a monthly trend for {table_hint}.",
            "Break this by the most relevant category column.",
            "Explain the business takeaway from this result.",
        ]
