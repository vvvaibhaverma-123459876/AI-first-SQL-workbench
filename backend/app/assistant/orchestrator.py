"""End-to-end local AI analyst orchestration."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.api.schemas import AssistantRunResponse, AssistantStep, SQLExecutionResponse
from app.core.config import get_settings
from app.services.ai_service import AIService
from app.services.execution_service import SQLExecutionService
from app.services.history_service import HistoryService
from app.services.learning_memory_service import LearningMemoryService
from app.services.validation_service import SQLValidationService


class AssistantOrchestrator:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.ai = AIService()
        self.validator = SQLValidationService()
        self.executor = SQLExecutionService()
        self.history = HistoryService()
        self.memory = LearningMemoryService()

    def run(self, db: Session, question: str, execute: bool = True, explain: bool = True, use_cache: bool = True) -> AssistantRunResponse:
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
            suggestions = self.ai.suggest_tables(question)
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
                sql = self.ai.generate_sql(question)
                steps.append(AssistantStep(name="sql_generation", detail="Generated SQL using the configured local AI provider."))

            # Validate and optionally repair.
            validation = self.validator.validate(sql)
            repair_attempts = 0
            while not validation.valid and repair_attempts < self.settings.max_repair_attempts:
                repair_attempts += 1
                warnings.extend(validation.errors)
                repaired = self.ai.repair_sql(sql, "; ".join(validation.errors))
                sql = repaired.repaired_sql
                steps.append(AssistantStep(name="sql_repair", status="warning", detail=f"Repair attempt {repair_attempts}: {repaired.rationale}"))
                validation = self.validator.validate(sql)

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
                    result = self.executor.execute(sql, metadata_db=db, use_cache=use_cache)
                    self.history.log(db, sql, "success", result.row_count, result.execution_ms)
                    steps.append(AssistantStep(
                        name="execution",
                        status="cached" if result.cached else "success",
                        detail=f"Returned {result.row_count} row(s) in {result.execution_ms} ms." if not result.cached else result.message,
                    ))
                except ValueError as exc:
                    self.history.log(db, sql, "error", 0, 0, str(exc))
                    # One final repair-and-run pass for runtime errors.
                    repaired = self.ai.repair_sql(sql, str(exc))
                    sql = repaired.repaired_sql
                    steps.append(AssistantStep(name="runtime_repair", status="warning", detail="Execution failed once; generated a repaired SQL candidate."))
                    result = None
                    errors.append(str(exc))
            else:
                steps.append(AssistantStep(name="execution", status="skipped", detail="Execution was skipped by request."))

            if explain:
                if result and result.rows:
                    explanation = self.ai.explain_result(question, sql, result)
                    steps.append(AssistantStep(name="result_explanation", detail="Generated result-level explanation locally."))
                elif not explanation:
                    explanation = self.ai.explain_sql(sql).explanation
                    steps.append(AssistantStep(name="sql_explanation", detail="Generated SQL explanation locally."))

            confidence = self._confidence(sql=sql, result=result, cached=cached, warning_count=len(warnings), error_count=len(errors))
            if not cached and sql:
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
