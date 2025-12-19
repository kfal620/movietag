"""Frame ingestion and tagging tasks."""

from __future__ import annotations

import logging
from typing import Any

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="frames.import")
def import_frame(file_path: str) -> dict[str, Any]:
    """Import a still frame from disk or object storage."""
    logger.info("Importing frame from %s", file_path)
    return {"status": "queued", "file_path": file_path}


@shared_task(name="frames.embed")
def embed_frame(frame_id: int) -> dict[str, Any]:
    """Generate an embedding vector for a frame."""
    logger.info("Generating embedding for frame %s", frame_id)
    return {"status": "queued", "frame_id": frame_id}


@shared_task(name="frames.tag")
def tag_frame(frame_id: int) -> dict[str, Any]:
    """Assign predicted tags to a frame based on embeddings."""
    logger.info("Tagging frame %s", frame_id)
    return {"status": "queued", "frame_id": frame_id}
