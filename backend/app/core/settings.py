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
    storage_endpoint_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("APP_STORAGE_ENDPOINT_URL", "STORAGE_ENDPOINT_URL"),
    )
    storage_access_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("APP_STORAGE_ACCESS_KEY", "STORAGE_ACCESS_KEY"),
    )
    storage_secret_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("APP_STORAGE_SECRET_KEY", "STORAGE_SECRET_KEY"),
    )
    storage_frames_bucket: str | None = Field(
        default="frames",
        validation_alias=AliasChoices("APP_STORAGE_FRAMES_BUCKET", "STORAGE_FRAMES_BUCKET"),
    )
    clip_model_name: str = Field(
        default="ViT-B-32",
        validation_alias=AliasChoices("APP_CLIP_MODEL_NAME", "CLIP_MODEL_NAME"),
    )
    clip_pretrained: str = Field(
        default="openai",
        validation_alias=AliasChoices("APP_CLIP_PRETRAINED", "CLIP_PRETRAINED"),
    )
    face_min_confidence: float = Field(
        default=0.9,
        validation_alias=AliasChoices("APP_FACE_MIN_CONFIDENCE", "FACE_MIN_CONFIDENCE"),
    )
    embedding_service_url: str | None = Field(
        default=None,
        description="Optional HTTP endpoint for an embedding service (CLIP/ViT).",
        validation_alias=AliasChoices(
            "APP_EMBEDDING_SERVICE_URL", "EMBEDDING_SERVICE_URL"
        ),
    )
    embedding_model_version: str | None = Field(
        default=None,
        description="Model revision or ONNX path for embeddings.",
        validation_alias=AliasChoices(
            "APP_EMBEDDING_MODEL_VERSION", "EMBEDDING_MODEL_VERSION"
        ),
    )
    vision_model_path: str | None = Field(
        default=None,
        description="Optional local ONNX/weights path for scene/vision models.",
        validation_alias=AliasChoices("APP_VISION_MODEL_PATH", "VISION_MODEL_PATH"),
    )
    admin_token: str = Field(
        default="admin-token",
        validation_alias=AliasChoices("APP_ADMIN_TOKEN", "ADMIN_TOKEN"),
    )
    moderator_token: str = Field(
        default="moderator-token",
        validation_alias=AliasChoices("APP_MODERATOR_TOKEN", "MODERATOR_TOKEN"),
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance to avoid repeated environment parsing."""
    return Settings()
