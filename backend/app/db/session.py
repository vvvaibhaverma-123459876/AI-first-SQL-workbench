"""Database engine and session factories."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import get_settings

settings = get_settings()

analytics_engine = create_engine(settings.analytics_db_url, future=True)
metadata_engine = create_engine(settings.metadata_db_url, future=True)

AnalyticsSessionLocal = sessionmaker(bind=analytics_engine, autoflush=False, autocommit=False, future=True)
MetadataSessionLocal = sessionmaker(bind=metadata_engine, autoflush=False, autocommit=False, future=True)


def get_metadata_session():
    db = MetadataSessionLocal()
    try:
        yield db
    finally:
        db.close()
