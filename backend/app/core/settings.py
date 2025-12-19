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


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance to avoid repeated environment parsing."""
    return Settings()
