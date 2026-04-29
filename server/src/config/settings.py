from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://hermes:hermes_dev@localhost:5432/hermes_hiring"
    db_echo: bool = False

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Object Storage (S3-compatible)
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "hermes"
    s3_secret_key: str = "hermes_dev"
    s3_bucket: str = "hermes-hiring"

    # LLM Provider
    llm_provider: str = "openai"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o"

    # Hermes Orchestrator
    hermes_port: int = 8080
    hermes_log_level: str = "INFO"

    # Agent Service Ports
    profile_agent_port: int = 8101
    job_agent_port: int = 8102
    matching_agent_port: int = 8103
    gdpr_agent_port: int = 8104
    feedback_agent_port: int = 8105

    # Observability
    otel_service_name: str = "hermes-hiring"
    otel_exporter_otlp_endpoint: str = "http://localhost:4318"
    prometheus_port: int = 9090


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
