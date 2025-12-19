"""Tasks for ingesting metadata from TMDb and enriching the database."""

from __future__ import annotations

import logging
from celery import shared_task

from app.integrations.tmdb import TMDBIngestor

logger = logging.getLogger(__name__)


@shared_task(name="tmdb.ingest_movie")
def ingest_movie_from_tmdb(tmdb_id: int) -> dict[str, int]:
    """Fetch TMDb metadata and persist movies, cast, and artwork."""
    ingestor = TMDBIngestor()
    result = ingestor.ingest_movie(tmdb_id)
    logger.info("TMDb ingest completed for %s -> %s", tmdb_id, result.get("movie_id"))
    return result
