"""Celery tasks for the movietag backend."""

from .frames import embed_frame, import_frame, tag_frame

__all__ = ["import_frame", "embed_frame", "tag_frame"]
