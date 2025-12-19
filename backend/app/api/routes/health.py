from fastapi import APIRouter
from sqlalchemy import text

from ...core.settings import get_settings
from ...db import SessionLocal
from ...core.celery import celery_app
from ...services.storage import _build_s3_client  # type: ignore

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str | dict[str, str | bool]]:
    """Deep readiness endpoint with dependencies."""
    settings = get_settings()
    checks: dict[str, str | bool] = {}

    # Database
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        checks["database"] = False

    # Redis / broker
    try:
        with celery_app.connection() as conn:
            conn.ensure_connection(max_retries=1)
        checks["broker"] = True
    except Exception:
        checks["broker"] = False

    # Storage
    try:
        bucket = settings.storage_frames_bucket
        if settings.storage_access_key and settings.storage_secret_key and bucket:
            client = _build_s3_client()
            client.head_bucket(Bucket=bucket)
        checks["storage"] = True
    except Exception:
        checks["storage"] = False

    status = "ok"
    return {
        "status": status,
        "environment": settings.environment,
        "version": settings.version,
        "checks": checks,
    }
