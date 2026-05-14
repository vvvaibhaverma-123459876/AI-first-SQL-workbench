"""Metadata tables for saved queries, history, assistant memory, and result cache."""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class MetadataBase(DeclarativeBase):
    pass


class SavedQuery(MetadataBase):
    __tablename__ = "saved_queries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sql_text: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class QueryHistory(MetadataBase):
    __tablename__ = "query_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sql_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    execution_ms: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AssistantMemory(MetadataBase):
    """Stores successful local assistant runs so repeated/near-repeat prompts do not hit Ollama."""

    __tablename__ = "assistant_memory"
    __table_args__ = (UniqueConstraint("question_fingerprint", name="uq_assistant_memory_question_fingerprint"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    question_fingerprint: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    sql_text: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    selected_tables_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    positive_feedback: Mapped[int] = mapped_column(Integer, default=0)
    negative_feedback: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ResultCache(MetadataBase):
    """TTL-backed result cache for read-only SQL outputs."""

    __tablename__ = "result_cache"
    __table_args__ = (UniqueConstraint("sql_hash", name="uq_result_cache_sql_hash"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sql_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sql_text: Mapped[str] = mapped_column(Text, nullable=False)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    execution_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_used_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    use_count: Mapped[int] = mapped_column(Integer, default=0)
