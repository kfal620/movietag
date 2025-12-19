from fastapi import APIRouter

from ...core.settings import get_settings

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Simple readiness endpoint used for uptime checks."""
    settings = get_settings()
    return {
        "status": "ok",
        "environment": settings.environment,
        "version": settings.version,
    }
