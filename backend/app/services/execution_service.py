"""Validated SQL execution service with local result caching."""
from __future__ import annotations

import time

import pandas as pd
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.schemas import SQLExecutionResponse
from app.db.session import analytics_engine
from app.services.result_cache_service import ResultCacheService
from app.services.validation_service import SQLValidationService


class SQLExecutionService:
    def __init__(self) -> None:
        self.validator = SQLValidationService()
        self.cache = ResultCacheService()

    def execute(self, sql: str, metadata_db: Session | None = None, use_cache: bool = True) -> SQLExecutionResponse:
        validation = self.validator.validate(sql)
        if not validation.valid or not validation.normalized_sql:
            raise ValueError("; ".join(validation.errors))

        normalized_sql = validation.normalized_sql
        if use_cache and metadata_db is not None:
            cached = self.cache.get(metadata_db, normalized_sql)
            if cached:
                return cached

        started = time.perf_counter()
        try:
            with analytics_engine.connect() as conn:
                result = conn.execute(text(normalized_sql))
                rows = [dict(row._mapping) for row in result]
                columns = list(result.keys())
            execution_ms = int((time.perf_counter() - started) * 1000)
            response = SQLExecutionResponse(
                columns=columns,
                rows=rows,
                row_count=len(rows),
                execution_ms=execution_ms,
                message="Query executed successfully.",
                cached=False,
            )
            if use_cache and metadata_db is not None:
                self.cache.put(metadata_db, normalized_sql, response)
            return response
        except SQLAlchemyError as exc:
            raise ValueError(str(exc)) from exc

    def export_csv_text(self, sql: str) -> str:
        executed = self.execute(sql, metadata_db=None, use_cache=False)
        df = pd.DataFrame(executed.rows)
        return df.to_csv(index=False)
