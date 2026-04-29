from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/hirematch"
    anthropic_api_key: str = ""
    api_key: str = "dev-api-key"  # X-API-Key header value
    anthropic_model: str = "claude-sonnet-4-6"


settings = Settings()
