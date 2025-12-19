import pytest

from app.core import settings as settings_module
from app.core.settings import get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Ensure cached settings do not leak between tests."""
    settings_module.get_settings.cache_clear()
    yield
    settings_module.get_settings.cache_clear()


def test_settings_can_read_standard_database_url(monkeypatch):
    expected_url = "postgresql+psycopg://user:pass@localhost:5432/override"
    monkeypatch.setenv("DATABASE_URL", expected_url)

    settings = get_settings()

    assert settings.database_url == expected_url


def test_settings_can_read_celery_and_tmdb_overrides(monkeypatch):
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://redis.test/0")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://redis.test/1")
    monkeypatch.setenv("CELERY_DEFAULT_QUEUE", "custom.queue")
    monkeypatch.setenv("TMDB_API_KEY", "apikey")
    monkeypatch.setenv("TMDB_BASE_URL", "https://tmdb.test")

    settings = get_settings()

    assert settings.celery_broker_url.endswith("/0")
    assert settings.celery_result_backend.endswith("/1")
    assert settings.celery_default_queue == "custom.queue"
    assert settings.tmdb_api_key == "apikey"
    assert settings.tmdb_base_url == "https://tmdb.test"
