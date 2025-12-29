"""Celery application configuration."""

from __future__ import annotations

from celery import Celery
from app.core.settings import get_settings

# Create the Celery app object FIRST, at module import time.
# This guarantees it exists before any task modules import it.
celery_app = Celery("movietag")

# Configure it from settings
settings = get_settings()
celery_app.conf.broker_url = settings.celery_broker_url
celery_app.conf.result_backend = settings.celery_result_backend

celery_app.conf.task_default_queue = settings.celery_default_queue
celery_app.conf.task_queues = None  # rely on the default queue for now
celery_app.conf.result_persistent = False

celery_app.conf.beat_schedule = {
    "sync-s3-frames-every-minute": {
        "task": "frames.sync_s3",
        "schedule": 60.0,
    },
}

# Discover tasks AFTER celery_app exists and is configured.
# This will import app.tasks.* modules, but they can safely import celery_app now.
celery_app.autodiscover_tasks(["app.tasks"])
