"""Feedback-aware local assistant memory.

This is intentionally not fake reinforcement learning. It is a practical local
learning layer: successful prompts, generated SQL, explanations, usage counts,
and thumbs-up/down feedback are stored locally and reused for fast future runs.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.metadata import AssistantMemory

STOPWORDS = {
    "a", "an", "the", "to", "of", "in", "on", "for", "by", "with", "and", "or", "is", "are",
    "was", "were", "show", "give", "get", "me", "please", "top", "list", "all", "from", "what",
    "which", "how", "many", "much", "count", "total",
}


@dataclass
class MemoryHit:
    item: AssistantMemory
    score: float


class LearningMemoryService:
    def tokenize(self, text: str) -> set[str]:
        words = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", (text or "").lower())
        return {word for word in words if word not in STOPWORDS and len(word) > 1}

    def fingerprint(self, text: str) -> str:
        return " ".join(sorted(self.tokenize(text)))[:500]

    def similarity(self, left: str, right: str) -> float:
        a = self.tokenize(left)
        b = self.tokenize(right)
        if not a or not b:
            return 0.0
        return len(a & b) / len(a | b)

    def find_best(self, db: Session, question: str, min_score: float = 0.74) -> MemoryHit | None:
        # Exact fingerprint lookup first.
        fp = self.fingerprint(question)
        exact = db.scalar(select(AssistantMemory).where(AssistantMemory.question_fingerprint == fp))
        if exact:
            score = min(1.0, 0.94 + self._feedback_bonus(exact))
            self._mark_used(db, exact)
            return MemoryHit(item=exact, score=score)

        # Fuzzy lookup over recent/local memories. This keeps dependencies light and fully local.
        candidates = list(db.scalars(select(AssistantMemory).order_by(desc(AssistantMemory.updated_at)).limit(250)).all())
        best: MemoryHit | None = None
        for item in candidates:
            score = self.similarity(question, item.question) + self._feedback_bonus(item)
            if best is None or score > best.score:
                best = MemoryHit(item=item, score=score)
        if best and best.score >= min_score:
            self._mark_used(db, best.item)
            return best
        return None

    def upsert(
        self,
        db: Session,
        question: str,
        sql_text: str,
        explanation: str | None = None,
        selected_tables: list[str] | None = None,
        confidence: float = 0.7,
    ) -> AssistantMemory:
        fp = self.fingerprint(question)
        existing = db.scalar(select(AssistantMemory).where(AssistantMemory.question_fingerprint == fp))
        if existing:
            existing.question = question
            existing.sql_text = sql_text
            existing.explanation = explanation
            existing.selected_tables_json = json.dumps(selected_tables or [])
            existing.confidence = max(existing.confidence or 0.0, confidence)
            existing.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(existing)
            return existing

        item = AssistantMemory(
            question=question,
            question_fingerprint=fp,
            sql_text=sql_text,
            explanation=explanation,
            selected_tables_json=json.dumps(selected_tables or []),
            confidence=confidence,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    def feedback(self, db: Session, memory_id: int, positive: bool) -> AssistantMemory | None:
        item = db.get(AssistantMemory, memory_id)
        if not item:
            return None
        if positive:
            item.positive_feedback += 1
            item.confidence = min(1.0, (item.confidence or 0.0) + 0.05)
        else:
            item.negative_feedback += 1
            item.confidence = max(0.0, (item.confidence or 0.0) - 0.08)
        item.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(item)
        return item

    def list_recent(self, db: Session, limit: int = 50) -> list[AssistantMemory]:
        return list(db.scalars(select(AssistantMemory).order_by(desc(AssistantMemory.updated_at)).limit(limit)).all())

    def _feedback_bonus(self, item: AssistantMemory) -> float:
        positive = item.positive_feedback or 0
        negative = item.negative_feedback or 0
        usage = min(item.use_count or 0, 10) * 0.005
        return min(0.12, positive * 0.025 + usage) - min(0.18, negative * 0.05)

    def _mark_used(self, db: Session, item: AssistantMemory) -> None:
        item.use_count += 1
        item.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(item)
