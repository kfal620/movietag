from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

from app.core import settings as settings_module
from app.models import Base


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _make_alembic_config(database_url: str) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Ensure cached settings are reset between migrations tests."""
    settings_module.get_settings.cache_clear()
    yield
    settings_module.get_settings.cache_clear()


def test_migrations_are_up_to_date(tmp_path, monkeypatch):
    """Validate Alembic migrations produce the same schema as the models."""
    db_url = f"sqlite:///{tmp_path / 'alembic.db'}"
    monkeypatch.setenv("APP_DATABASE_URL", db_url)

    config = _make_alembic_config(db_url)
    command.upgrade(config, "head")

    engine = create_engine(db_url)
    with engine.connect() as connection:
        context = MigrationContext.configure(
            connection,
            opts={
                "target_metadata": Base.metadata,
                "compare_type": True,
                "compare_server_default": True,
                "include_object": lambda obj, name, type_, reflected, compare_to: name != "alembic_version",
            },
        )
        diffs = compare_metadata(context, Base.metadata)

    assert diffs == []
