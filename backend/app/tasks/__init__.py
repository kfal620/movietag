"""Celery tasks for the movietag backend."""

from .frames import (
    detect_actor_faces,
    detect_scene_attributes,
    embed_frame,
    enrich_frame_metadata,
    import_frame,
    ingest_and_tag_frame,
    tag_frame,
)
from .tmdb import ingest_movie_from_tmdb
from .vision import analyze_frames

__all__ = [
    "import_frame",
    "embed_frame",
    "tag_frame",
    "enrich_frame_metadata",
    "detect_scene_attributes",
    "detect_actor_faces",
    "ingest_and_tag_frame",
    "ingest_movie_from_tmdb",
    "analyze_frames",
]
