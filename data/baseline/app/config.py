"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "sample-app"
    debug: bool = False
    database_url: str = "sqlite+aiosqlite:///./app.db"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    model_config = {"env_prefix": "APP_"}


settings = Settings()
