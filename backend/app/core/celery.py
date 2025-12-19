"""Celery application configuration."""

from __future__ import annotations

from celery import Celery

from .settings import get_settings


def create_celery_app() -> Celery:
    """Create and configure a Celery app from application settings."""
    settings = get_settings()
    celery_app = Celery(
        "movietag",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
        include=["app.tasks.frames"],
    )

    celery_app.conf.task_default_queue = settings.celery_default_queue
    celery_app.conf.task_queues = None  # rely on the default queue for now
    celery_app.conf.result_persistent = False

    # ensure tasks are registered when running in-process
    from app.tasks import frames as _  # noqa: F401

    celery_app.autodiscover_tasks(["app.tasks"])
    return celery_app


celery_app = create_celery_app()
