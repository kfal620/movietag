from app.core.settings import get_settings
from app.models import (
    Artwork,
    Base,
    CastMember,
    Frame,
    FrameTag,
    Movie,
    MovieCast,
    SceneAttribute,
    Tag,
    ActorDetection,
)


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
    assert "cast_members" in table_names
    assert "movie_cast" in table_names
    assert "artwork" in table_names
    assert "scene_attributes" in table_names
    assert "actor_detections" in table_names


def test_timestamp_columns_are_not_nullable_and_use_server_defaults():
    metadata = Base.metadata
    movies = metadata.tables["movies"].columns
    frames = metadata.tables["frames"].columns
    tags = metadata.tables["tags"].columns
    frame_tags = metadata.tables["frame_tags"].columns
    scene_attributes = metadata.tables["scene_attributes"].columns
    actor_detections = metadata.tables["actor_detections"].columns
    cast_members = metadata.tables["cast_members"].columns
    movie_cast = metadata.tables["movie_cast"].columns
    artwork = metadata.tables["artwork"].columns

    for column in (
        movies["created_at"],
        movies["updated_at"],
        frames["created_at"],
        frames["updated_at"],
        tags["created_at"],
        tags["updated_at"],
        frame_tags["created_at"],
        frame_tags["updated_at"],
        cast_members["created_at"],
        cast_members["updated_at"],
        movie_cast["created_at"],
        movie_cast["updated_at"],
        artwork["created_at"],
        artwork["updated_at"],
        scene_attributes["created_at"],
        scene_attributes["updated_at"],
        actor_detections["created_at"],
        actor_detections["updated_at"],
    ):
        assert column.nullable is False
        assert column.server_default is not None


def test_frame_foreign_keys_and_indexes():
    frames = Base.metadata.tables["frames"]

    assert frames.c.movie_id.nullable is False
    # SQLAlchemy marks both explicit and implicit indexes here
    assert frames.c.movie_id.index is True
    assert any(index.name == "ix_frames_movie_id" for index in frames.indexes)


def test_tmdb_entities_have_indexes_and_constraints():
    movies = Base.metadata.tables["movies"]
    cast_members = Base.metadata.tables["cast_members"]
    movie_cast = Base.metadata.tables["movie_cast"]
    artwork = Base.metadata.tables["artwork"]
    actor_detections = Base.metadata.tables["actor_detections"]

    assert movies.c.tmdb_id.index is True
    assert any(index.name == "uq_movies_tmdb_id" for index in movies.constraints)

    assert cast_members.c.tmdb_id.nullable is False
    assert any(index.name == "uq_cast_members_tmdb_id" for index in cast_members.constraints)

    assert any(index.name == "uq_movie_cast_pair" for index in movie_cast.constraints)
    assert movie_cast.c.movie_id.index is True
    assert movie_cast.c.cast_member_id.index is True

    assert artwork.c.movie_id.index is True
    assert any(index.name == "uq_artwork_per_movie" for index in artwork.constraints)

    assert any(index.name == "uq_actor_detection_frame_cast" for index in actor_detections.constraints)
