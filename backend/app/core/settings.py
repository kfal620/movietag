from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE_PATH = BASE_DIR / ".env"


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=ENV_FILE_PATH, extra="ignore")

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
    tmdb_api_key: Optional[str] = Field(
        default="b9c1f62dcbb3d3a66f3631a1b95386c4",  # Hardcoded TMDB API key
        validation_alias=AliasChoices("APP_TMDB_API_KEY", "TMDB_API_KEY"),
    )
    tmdb_base_url: str = Field(
        default="https://api.themoviedb.org/3",
        validation_alias=AliasChoices("APP_TMDB_BASE_URL", "TMDB_BASE_URL"),
    )
    omdb_api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("APP_OMDB_API_KEY", "OMDB_API_KEY"),
    )
    omdb_base_url: str = Field(
        default="https://www.omdbapi.com",
        validation_alias=AliasChoices("APP_OMDB_BASE_URL", "OMDB_BASE_URL"),
    )
    storage_endpoint_url: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("APP_STORAGE_ENDPOINT_URL", "STORAGE_ENDPOINT_URL"),
    )
    storage_public_endpoint_url: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices(
            "APP_STORAGE_PUBLIC_ENDPOINT_URL", "STORAGE_PUBLIC_ENDPOINT_URL"
        ),
    )
    storage_access_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("APP_STORAGE_ACCESS_KEY", "STORAGE_ACCESS_KEY"),
    )
    storage_secret_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("APP_STORAGE_SECRET_KEY", "STORAGE_SECRET_KEY"),
    )
    storage_frames_bucket: Optional[str] = Field(
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
    enhanced_clip_model_name: str = Field(
        default="ViT-L-14",
        validation_alias=AliasChoices("APP_ENHANCED_CLIP_MODEL_NAME", "ENHANCED_CLIP_MODEL_NAME"),
    )
    enhanced_clip_pretrained: str = Field(
        default="laion2b_s32b_b82k",
        validation_alias=AliasChoices("APP_ENHANCED_CLIP_PRETRAINED", "ENHANCED_CLIP_PRETRAINED"),
    )
    enhanced_clip_batch_size: int = Field(
        default=4,
        validation_alias=AliasChoices("APP_ENHANCED_CLIP_BATCH_SIZE", "ENHANCED_CLIP_BATCH_SIZE"),
    )
    face_min_confidence: float = Field(
        default=0.9,
        validation_alias=AliasChoices("APP_FACE_MIN_CONFIDENCE", "FACE_MIN_CONFIDENCE"),
    )
    embedding_service_url: Optional[str] = Field(
        default=None,
        description="Optional HTTP endpoint for an embedding service (CLIP/ViT).",
        validation_alias=AliasChoices(
            "APP_EMBEDDING_SERVICE_URL", "EMBEDDING_SERVICE_URL"
        ),
    )
    embedding_model_version: Optional[str] = Field(
        default=None,
        description="Model revision or ONNX path for embeddings.",
        validation_alias=AliasChoices(
            "APP_EMBEDDING_MODEL_VERSION", "EMBEDDING_MODEL_VERSION"
        ),
    )
    vision_model_path: Optional[str] = Field(
        default=None,
        description="Optional local ONNX/weights path for scene/vision models.",
        validation_alias=AliasChoices("APP_VISION_MODEL_PATH", "VISION_MODEL_PATH"),
    )
    vision_service_url: Optional[str] = Field(
        default=None,
        description="HTTP endpoint for production scene understanding models.",
        validation_alias=AliasChoices("APP_VISION_SERVICE_URL", "VISION_SERVICE_URL"),
    )
    face_recognition_match_threshold: float = Field(
        default=0.55,
        description="Cosine similarity threshold for face recognition.",
        validation_alias=AliasChoices(
            "APP_FACE_RECOGNITION_MATCH_THRESHOLD", "FACE_RECOGNITION_MATCH_THRESHOLD"
        ),
    )
    face_unknown_match_threshold: float = Field(
        default=0.58,
        description="Cosine similarity threshold for clustering unknown faces.",
        validation_alias=AliasChoices(
            "APP_FACE_UNKNOWN_MATCH_THRESHOLD", "FACE_UNKNOWN_MATCH_THRESHOLD"
        ),
    )
    face_analytics_service_url: Optional[str] = Field(
        default=None,
        description="HTTP endpoint for production-grade face analytics (emotion/pose/embedding).",
        validation_alias=AliasChoices(
            "APP_FACE_ANALYTICS_SERVICE_URL", "FACE_ANALYTICS_SERVICE_URL"
        ),
    )
    admin_token: str = Field(
        default="admin-token",
        validation_alias=AliasChoices("APP_ADMIN_TOKEN", "ADMIN_TOKEN"),
    )
    moderator_token: str = Field(
        default="moderator-token",
        validation_alias=AliasChoices("APP_MODERATOR_TOKEN", "MODERATOR_TOKEN"),
    )


def get_settings() -> Settings:
    """Return application settings loaded from the environment or .env file."""
    return Settings()
