from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_")

    name: str = "Framegrab Tagger API"
    environment: str = "development"
    version: str = "0.1.0"
    database_url: str = (
        "postgresql+psycopg://movietag:movietag@localhost:5432/movietag"
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance to avoid repeated environment parsing."""
    return Settings()
