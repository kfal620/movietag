from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.auth import require_role
from app.core.settings import get_settings
from app.services.runtime_settings import persist_runtime_settings

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingsPayload(BaseModel):
    storage_endpoint_url: str | None = None
    storage_access_key: str | None = None
    storage_secret_key: str | None = None
    storage_frames_bucket: str | None = None
    tmdb_api_key: str | None = None
    omdb_api_key: str | None = None


class SettingsResponse(BaseModel):
    storage_endpoint_url: str | None
    storage_access_key: str | None
    storage_secret_key: str | None
    storage_frames_bucket: str | None
    tmdb_api_key: str | None
    omdb_api_key: str | None


def _serialize_settings() -> SettingsResponse:
    settings = get_settings()
    return SettingsResponse(
        storage_endpoint_url=settings.storage_endpoint_url,
        storage_access_key=settings.storage_access_key,
        storage_secret_key=settings.storage_secret_key,
        storage_frames_bucket=settings.storage_frames_bucket,
        tmdb_api_key=settings.tmdb_api_key,
        omdb_api_key=settings.omdb_api_key,
    )


@router.get("")
def get_runtime_settings(_: object = Depends(require_role("admin"))) -> SettingsResponse:
    return _serialize_settings()


@router.post("")
def update_runtime_settings(
    payload: SettingsPayload, _: object = Depends(require_role("admin"))
) -> SettingsResponse:
    payload_dict = payload.model_dump(exclude_unset=True)
    updates = {
        env_key: payload_dict.get(field_name)
        for field_name, env_key in {
            "storage_endpoint_url": "APP_STORAGE_ENDPOINT_URL",
            "storage_access_key": "APP_STORAGE_ACCESS_KEY",
            "storage_secret_key": "APP_STORAGE_SECRET_KEY",
            "storage_frames_bucket": "APP_STORAGE_FRAMES_BUCKET",
            "tmdb_api_key": "APP_TMDB_API_KEY",
            "omdb_api_key": "APP_OMDB_API_KEY",
        }.items()
        if field_name in payload_dict
    }
    persist_runtime_settings(updates)
    return _serialize_settings()
