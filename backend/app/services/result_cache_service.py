"""Persistent local result cache for repeated read-only SQL queries."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import SQLExecutionResponse
from app.core.config import get_settings
from app.models.metadata import ResultCache


class ResultCacheService:
    def __init__(self) -> None:
        self.settings = get_settings()

    @staticmethod
    def hash_sql(sql: str) -> str:
        normalized = " ".join((sql or "").strip().split()).lower()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def get(self, db: Session, sql: str) -> SQLExecutionResponse | None:
        if self.settings.result_cache_ttl_seconds <= 0:
            return None
        sql_hash = self.hash_sql(sql)
        item = db.scalar(select(ResultCache).where(ResultCache.sql_hash == sql_hash))
        if not item:
            return None
        if datetime.utcnow() - item.created_at > timedelta(seconds=self.settings.result_cache_ttl_seconds):
            db.delete(item)
            db.commit()
            return None
        item.use_count += 1
        item.last_used_at = datetime.utcnow()
        db.commit()
        payload: dict[str, Any] = json.loads(item.result_json)
        return SQLExecutionResponse(
            columns=payload.get("columns", []),
            rows=payload.get("rows", []),
            row_count=payload.get("row_count", 0),
            execution_ms=0,
            message=f"Served from local result cache. Original execution: {item.execution_ms} ms.",
            cached=True,
        )

    def put(self, db: Session, sql: str, response: SQLExecutionResponse) -> None:
        if self.settings.result_cache_ttl_seconds <= 0:
            return
        sql_hash = self.hash_sql(sql)
        payload = response.model_dump()
        item = db.scalar(select(ResultCache).where(ResultCache.sql_hash == sql_hash))
        if item:
            item.sql_text = sql
            item.result_json = json.dumps(payload, default=str)
            item.row_count = response.row_count
            item.execution_ms = response.execution_ms
            item.created_at = datetime.utcnow()
            item.last_used_at = datetime.utcnow()
        else:
            db.add(ResultCache(
                sql_hash=sql_hash,
                sql_text=sql,
                result_json=json.dumps(payload, default=str),
                row_count=response.row_count,
                execution_ms=response.execution_ms,
            ))
        db.commit()
