from app.core.settings import get_settings
from app.models import Base, Frame, FrameTag, Movie, Tag


def test_settings_exposes_database_url():
    settings = get_settings()

    assert settings.database_url
    assert "postgresql" in settings.database_url


def test_models_are_registered_on_metadata():
    table_names = Base.metadata.tables.keys()

    assert "movies" in table_names
    assert "frames" in table_names
    assert "tags" in table_names
    assert "frame_tags" in table_names

