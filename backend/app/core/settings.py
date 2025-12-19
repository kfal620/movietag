from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    name: str = Field(
        default="Framegrab Tagger API",
        validation_alias=AliasChoices("APP_NAME", "NAME"),
    )
    environment: str = Field(
        default="development",
        validation_alias=AliasChoices("APP_ENVIRONMENT", "ENVIRONMENT"),
    )
    version: str = Field(
        default="0.1.0",
        validation_alias=AliasChoices("APP_VERSION", "VERSION"),
    )
    database_url: str = Field(
        default="postgresql+psycopg://movietag:movietag@localhost:5432/movietag",
        validation_alias=AliasChoices("APP_DATABASE_URL", "DATABASE_URL"),
    )
    celery_broker_url: str = Field(
        default="redis://localhost:6379/0",
        validation_alias=AliasChoices("APP_CELERY_BROKER_URL", "CELERY_BROKER_URL"),
    )
    celery_result_backend: str = Field(
        default="redis://localhost:6379/1",
        validation_alias=AliasChoices(
            "APP_CELERY_RESULT_BACKEND", "CELERY_RESULT_BACKEND"
        ),
    )
    celery_default_queue: str = Field(
        default="movietag.default",
        validation_alias=AliasChoices(
            "APP_CELERY_DEFAULT_QUEUE", "CELERY_DEFAULT_QUEUE"
        ),
    )
    tmdb_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("APP_TMDB_API_KEY", "TMDB_API_KEY"),
    )
    tmdb_base_url: str = Field(
        default="https://api.themoviedb.org/3",
        validation_alias=AliasChoices("APP_TMDB_BASE_URL", "TMDB_BASE_URL"),
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance to avoid repeated environment parsing."""
    return Settings()
