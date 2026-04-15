"""Application configuration."""
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="AI SQL Studio API", alias="APP_NAME")
    debug: bool = Field(default=True, alias="DEBUG")
    analytics_db_url: str = Field(default="sqlite:///./data/demo_analytics.db", alias="ANALYTICS_DB_URL")
    metadata_db_url: str = Field(default="sqlite:///./data/app_metadata.db", alias="METADATA_DB_URL")
    ai_provider: str = Field(default="mock", alias="AI_PROVIDER")
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama3.1", alias="OLLAMA_MODEL")
    hf_model: str = Field(default="google/flan-t5-base", alias="HF_MODEL")
    default_row_limit: int = Field(default=200, alias="DEFAULT_ROW_LIMIT")
    default_sql_limit: int = Field(default=200, alias="DEFAULT_SQL_LIMIT")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
