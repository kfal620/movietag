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


def test_timestamp_columns_are_not_nullable_and_use_server_defaults():
    metadata = Base.metadata
    movies = metadata.tables["movies"].columns
    frames = metadata.tables["frames"].columns
    tags = metadata.tables["tags"].columns
    frame_tags = metadata.tables["frame_tags"].columns

    for column in (
        movies["created_at"],
        movies["updated_at"],
        frames["created_at"],
        frames["updated_at"],
        tags["created_at"],
        tags["updated_at"],
        frame_tags["created_at"],
        frame_tags["updated_at"],
    ):
        assert column.nullable is False
        assert column.server_default is not None


def test_frame_foreign_keys_and_indexes():
    frames = Base.metadata.tables["frames"]

    assert frames.c.movie_id.nullable is False
    # SQLAlchemy marks both explicit and implicit indexes here
    assert frames.c.movie_id.index is True
    assert any(index.name == "ix_frames_movie_id" for index in frames.indexes)
