"""Initialize metadata database."""
from app.db.session import metadata_engine
from app.models.metadata import MetadataBase


def init_metadata_db() -> None:
    MetadataBase.metadata.create_all(bind=metadata_engine)
