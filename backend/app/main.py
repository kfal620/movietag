from fastapi import FastAPI

from .api.routes import embeddings, frames, health, movies, settings as settings_routes, tasks, vision
from .core.settings import get_settings


def create_application() -> FastAPI:
    """Instantiate the FastAPI application with configured routes."""
    settings = get_settings()
    app = FastAPI(title=settings.name, version=settings.version)

    api_prefix = "/api"
    app.include_router(health.router, prefix=api_prefix, tags=["health"])
    app.include_router(frames.router, prefix=api_prefix)
    app.include_router(movies.router, prefix=api_prefix)
    app.include_router(settings_routes.router, prefix=api_prefix)
    app.include_router(tasks.router, prefix=api_prefix)
    app.include_router(embeddings.router, prefix=api_prefix)
    app.include_router(vision.router_models, prefix=api_prefix)
    app.include_router(vision.router_vision, prefix=api_prefix)


    @app.on_event("startup")
    async def on_startup() -> None:
        """Trigger S3 synchronization on startup."""
        from app.tasks.frames import sync_s3_frames
        
        # Fire and forget
        sync_s3_frames.delay()


    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {"message": "Framegrab Tagger backend is running", "docs_url": "/docs"}

    return app


app = create_application()
