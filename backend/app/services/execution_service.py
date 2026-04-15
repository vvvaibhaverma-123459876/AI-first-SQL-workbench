"""Validated SQL execution service."""
import time
import pandas as pd
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.api.schemas import SQLExecutionResponse
from app.db.session import analytics_engine
from app.services.validation_service import SQLValidationService


class SQLExecutionService:
    def __init__(self) -> None:
        self.validator = SQLValidationService()

    def execute(self, sql: str) -> SQLExecutionResponse:
        validation = self.validator.validate(sql)
        if not validation.valid or not validation.normalized_sql:
            raise ValueError("; ".join(validation.errors))

        started = time.perf_counter()
        try:
            with analytics_engine.connect() as conn:
                result = conn.execute(text(validation.normalized_sql))
                rows = [dict(row._mapping) for row in result]
                columns = list(result.keys())
            execution_ms = int((time.perf_counter() - started) * 1000)
            return SQLExecutionResponse(
                columns=columns,
                rows=rows,
                row_count=len(rows),
                execution_ms=execution_ms,
                message="Query executed successfully.",
            )
        except SQLAlchemyError as exc:
            raise ValueError(str(exc)) from exc

    def export_csv_text(self, sql: str) -> str:
        executed = self.execute(sql)
        df = pd.DataFrame(executed.rows)
        return df.to_csv(index=False)
