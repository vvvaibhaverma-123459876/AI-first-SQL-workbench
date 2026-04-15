"""CRUD operations for saved queries."""
from sqlalchemy import desc, select
from sqlalchemy.orm import Session
from app.models.metadata import SavedQuery


class SavedQueryService:
    def create(self, db: Session, name: str, sql_text: str, description: str | None = None) -> SavedQuery:
        obj = SavedQuery(name=name, sql_text=sql_text, description=description)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def list(self, db: Session) -> list[SavedQuery]:
        stmt = select(SavedQuery).order_by(desc(SavedQuery.created_at))
        return list(db.scalars(stmt).all())

    def get(self, db: Session, query_id: int) -> SavedQuery | None:
        return db.get(SavedQuery, query_id)

    def delete(self, db: Session, query_id: int) -> bool:
        obj = db.get(SavedQuery, query_id)
        if not obj:
            return False
        db.delete(obj)
        db.commit()
        return True
