from fastapi import FastAPI

from .api.routes import health
from .core.settings import get_settings


def create_application() -> FastAPI:
    """Instantiate the FastAPI application with configured routes."""
    settings = get_settings()
    app = FastAPI(title=settings.name, version=settings.version)

    api_prefix = "/api"
    app.include_router(health.router, prefix=api_prefix, tags=["health"])

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {"message": "Framegrab Tagger backend is running", "docs_url": "/docs"}

    return app


app = create_application()
