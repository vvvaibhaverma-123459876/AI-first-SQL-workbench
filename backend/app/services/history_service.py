"""Persistence for recent query execution history."""
from sqlalchemy import desc, select
from sqlalchemy.orm import Session
from app.models.metadata import QueryHistory


class HistoryService:
    def log(self, db: Session, sql_text: str, status: str, row_count: int = 0, execution_ms: int = 0, error_message: str | None = None) -> QueryHistory:
        entry = QueryHistory(
            sql_text=sql_text,
            status=status,
            row_count=row_count,
            execution_ms=execution_ms,
            error_message=error_message,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    def list(self, db: Session, limit: int = 50) -> list[QueryHistory]:
        stmt = select(QueryHistory).order_by(desc(QueryHistory.created_at)).limit(limit)
        return list(db.scalars(stmt).all())
