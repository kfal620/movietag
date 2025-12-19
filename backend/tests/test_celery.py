from app.core import celery as celery_module
from app.core.celery import create_celery_app
from app.core.settings import get_settings


def test_celery_uses_settings_for_configuration(monkeypatch):
    broker = "redis://example.com:6379/9"
    backend = "redis://example.com:6379/10"
    queue = "custom.queue"

    monkeypatch.setenv("CELERY_BROKER_URL", broker)
    monkeypatch.setenv("CELERY_RESULT_BACKEND", backend)
    monkeypatch.setenv("CELERY_DEFAULT_QUEUE", queue)
    celery_module.get_settings.cache_clear()

    app = create_celery_app()

    assert app.conf.broker_url == broker
    assert app.conf.result_backend == backend
    assert app.conf.task_default_queue == queue


def test_celery_app_exposes_discovered_tasks():
    # ensure cached settings don't interfere
    celery_module.get_settings.cache_clear()
    app = create_celery_app()

    assert "frames.import" in app.tasks
    assert "frames.embed" in app.tasks
    assert "frames.tag" in app.tasks
