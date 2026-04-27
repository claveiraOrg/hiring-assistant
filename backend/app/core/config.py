from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import json
from typing import Any


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    environment: str = "development"
    secret_key: str
    backend_cors_origins: list[str] = Field(default=["http://localhost:3000"])

    # DB
    database_url: str

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Anthropic
    anthropic_api_key: str

    # OpenAI (embeddings)
    openai_api_key: str

    # Clerk
    clerk_secret_key: str

    # Cloudflare R2
    r2_account_id: str
    r2_access_key_id: str
    r2_secret_access_key: str
    r2_bucket_name: str = "hiring-assistant-cvs"
    r2_public_url: str

    # Observability
    sentry_dsn: str = ""
    langfuse_secret_key: str = ""
    langfuse_public_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # Network trust gate thresholds (tunable without code changes)
    trust_gate_score_threshold: int = 75
    trust_gate_confidence_threshold: float = 0.8
    trust_gate_diversity_threshold: float = 0.15

    # Workers
    worker_concurrency: int = 4
    llm_max_retries: int = 3

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def async_database_url(self) -> str:
        return self.database_url.replace("postgresql://", "postgresql+asyncpg://")


settings = Settings()  # type: ignore[call-arg]
