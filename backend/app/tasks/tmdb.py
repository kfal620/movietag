"""Tasks for ingesting metadata from TMDb and enriching the database."""

from __future__ import annotations

import logging
from celery import shared_task

from app.integrations.tmdb import TMDBIngestor

logger = logging.getLogger(__name__)


@shared_task(name="tmdb.ingest_movie")
def ingest_movie_from_tmdb(tmdb_id: int, provider_hint: str | None = None) -> dict[str, int | str]:
    """Fetch metadata from TMDb/OMDb and persist movies, cast, and artwork."""
    ingestor = TMDBIngestor(provider_hint=provider_hint)
    result = ingestor.ingest_movie(tmdb_id)
    logger.info(
        "Metadata ingest completed for %s via %s -> %s",
        tmdb_id,
        result.get("provider"),
        result.get("movie_id"),
    )
    return result
