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
