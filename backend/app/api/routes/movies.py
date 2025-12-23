from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.core.auth import require_role
from app.core.celery import celery_app
from app.core.settings import get_settings
from app.db import get_db
from app.integrations.tmdb import TMDBClient, _parse_release_year
from app.models import Artwork, CastMember, Movie, MovieCast
from app.tasks.tmdb import ingest_movie_from_tmdb

router = APIRouter(prefix="/movies", tags=["movies"])
logger = logging.getLogger(__name__)


def _serialize_movie(movie: Movie) -> dict[str, Any]:
    return {
        "id": movie.id,
        "tmdb_id": movie.tmdb_id,
        "title": movie.title,
        "description": movie.description,
        "release_year": movie.release_year,
        "created_at": movie.created_at,
        "updated_at": movie.updated_at,
        "cast": [
            {
                "id": mapping.cast_member.id,
                "name": mapping.cast_member.name,
                "character": mapping.character,
                "cast_order": mapping.cast_order,
            }
            for mapping in movie.cast_members
        ],
        "artwork": [
            {
                "id": artwork.id,
                "kind": artwork.kind,
                "file_path": artwork.file_path,
                "aspect_ratio": artwork.aspect_ratio,
                "width": artwork.width,
                "height": artwork.height,
                "language": artwork.language,
            }
            for artwork in movie.artwork
        ],
    }


@router.get("")
def list_movies(
    limit: int = 20,
    offset: int = 0,
    q: str | None = Query(default=None, description="Search by title"),
    year: int | None = Query(default=None, description="Release year"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    query = db.query(Movie).options(
        joinedload(Movie.cast_members).joinedload(MovieCast.cast_member),
        joinedload(Movie.artwork),
    )
    if q:
        query = query.filter(Movie.title.ilike(f"%{q}%"))
    if year:
        query = query.filter(Movie.release_year == year)
    total = query.count()
    movies = query.order_by(Movie.updated_at.desc()).offset(offset).limit(limit).all()
    return {
        "items": [_serialize_movie(movie) for movie in movies],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/search")
def search_tmdb_movies(
    q: str = Query(..., description="Movie title to search for"),
    year: int | None = Query(default=None, description="Optional release year filter"),
    limit: int = Query(default=5, ge=1, le=20),
    _: object = Depends(require_role("moderator", "admin")),
) -> dict[str, Any]:
    query = q.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")

    settings = get_settings()
    if not settings.tmdb_api_key:
        raise HTTPException(status_code=503, detail="TMDb is not configured")

    client = TMDBClient()
    try:
        response = client.search_movies(query, year=year)
    except Exception as exc:
        logger.exception("TMDb search failed for %s", query)
        raise HTTPException(status_code=502, detail=f"TMDb search failed: {exc}") from exc

    results: list[dict[str, Any]] = []
    for entry in response.get("results", []):
        tmdb_id = entry.get("id")
        title = entry.get("title") or entry.get("original_title")
        if tmdb_id is None or not title:
            continue
        results.append(
            {
                "tmdb_id": tmdb_id,
                "title": title,
                "release_year": _parse_release_year(entry.get("release_date")),
                "overview": entry.get("overview"),
                "poster_path": entry.get("poster_path"),
            }
        )
        if len(results) >= limit:
            break

    return {"items": results}


@router.get("/{movie_id}")
def get_movie(movie_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    movie = (
        db.query(Movie)
        .options(
            joinedload(Movie.cast_members).joinedload(MovieCast.cast_member),
            joinedload(Movie.artwork),
        )
        .filter(Movie.id == movie_id)
        .one_or_none()
    )
    if movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    return _serialize_movie(movie)


class TMDBIngestRequest(BaseModel):
    tmdb_id: int


@router.post("/ingest")
def ingest_tmdb_movie(
    payload: TMDBIngestRequest, _: object = Depends(require_role("moderator", "admin"))
) -> dict[str, str]:
    async_result = ingest_movie_from_tmdb.delay(payload.tmdb_id)
    return {"task_id": async_result.id, "status": "queued"}


@router.get("/tasks/{task_id}")
def tmdb_task_status(task_id: str) -> dict[str, Any]:
    result = celery_app.AsyncResult(task_id)
    response: dict[str, Any] = {"task_id": task_id, "state": result.state}
    if result.successful():
        response["result"] = result.result
    elif result.failed():
        response["error"] = str(result.result)
    return response
