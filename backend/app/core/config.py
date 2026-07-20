"""Application configuration."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = BACKEND_ROOT / "data"
DEFAULT_ANALYTICS_DB_URL = f"sqlite:///{(DATA_DIR / 'demo_analytics.db').as_posix()}"
DEFAULT_METADATA_DB_URL = f"sqlite:///{(DATA_DIR / 'app_metadata.db').as_posix()}"


class Settings(BaseSettings):
    app_name: str = Field(default="AI SQL Studio API", alias="APP_NAME")
    # Keep in sync with the "version" field in the root package.json.
    app_version: str = Field(default="1.1.0-local-ai", alias="APP_VERSION")
    debug: bool = Field(default=True, alias="DEBUG")
    api_prefix: str = Field(default="/api", alias="API_PREFIX")

    analytics_db_url: str = Field(default=DEFAULT_ANALYTICS_DB_URL, alias="ANALYTICS_DB_URL")
    metadata_db_url: str = Field(default=DEFAULT_METADATA_DB_URL, alias="METADATA_DB_URL")

    ai_provider: str = Field(default="ollama", alias="AI_PROVIDER")
    # AI_MODE is the newer, deploy-facing name (ollama|mock) and takes
    # precedence when set; AI_PROVIDER (which also accepts hf/huggingface) is
    # kept for backward compatibility with existing local .env files and
    # docker-compose.yml. The production Dockerfile sets AI_MODE=mock.
    ai_mode: str | None = Field(default=None, alias="AI_MODE")
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="qwen2.5-coder:7b", alias="OLLAMA_MODEL")
    ollama_explain_model: str | None = Field(default=None, alias="OLLAMA_EXPLAIN_MODEL")
    hf_model: str = Field(default="google/flan-t5-base", alias="HF_MODEL")

    default_row_limit: int = Field(default=200, alias="DEFAULT_ROW_LIMIT")
    default_sql_limit: int = Field(default=200, alias="DEFAULT_SQL_LIMIT")
    assistant_cache_enabled: bool = Field(default=True, alias="ASSISTANT_CACHE_ENABLED")
    assistant_cache_min_score: float = Field(default=0.74, alias="ASSISTANT_CACHE_MIN_SCORE")
    result_cache_ttl_seconds: int = Field(default=900, alias="RESULT_CACHE_TTL_SECONDS")
    sql_execution_timeout_seconds: int = Field(default=30, alias="SQL_EXECUTION_TIMEOUT_SECONDS")
    max_repair_attempts: int = Field(default=2, alias="MAX_REPAIR_ATTEMPTS")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    @field_validator("api_prefix")
    @classmethod
    def normalize_api_prefix(cls, value: str) -> str:
        if not value:
            return ""
        return value if value.startswith("/") else f"/{value}"

    @property
    def effective_ai_mode(self) -> str:
        """The mode that actually decides which LLM provider gets used."""
        return (self.ai_mode or self.ai_provider).lower()


@lru_cache
def get_settings() -> Settings:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return Settings()
