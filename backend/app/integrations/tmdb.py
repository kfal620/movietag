"""Minimal TMDb API client used for metadata enrichment."""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import contextmanager
import logging
from typing import Any, Protocol

import httpx
from sqlalchemy.orm import Session

from app.core.settings import Settings, get_settings
from app.db import SessionLocal
from app.models import Artwork, CastMember, Movie, MovieCast

logger = logging.getLogger(__name__)


class TMDBClient:
    """HTTP client for interacting with TMDb."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        settings = get_settings()
        self._api_key = settings.tmdb_api_key

        if client is None:
            self._client = httpx.Client(
                base_url=settings.tmdb_base_url,
                timeout=10.0,
            )
        else:
            self._client = client

    def movie_details(
        self,
        tmdb_id: int,
        *,
        append_to_response: list[str] | None = None,
    ) -> dict[str, Any]:
        """Fetch metadata for a movie by its TMDb identifier."""
        params = {"api_key": self._api_key} if self._api_key else {}
        if append_to_response:
            params["append_to_response"] = ",".join(append_to_response)
        response = self._client.get(f"/movie/{tmdb_id}", params=params)
        response.raise_for_status()
        return response.json()

    def search_movies(self, query: str, *, year: int | None = None) -> dict[str, Any]:
        """Search TMDb for movies by title (and optional release year)."""
        params: dict[str, Any] = {"api_key": self._api_key, "query": query} if self._api_key else {"query": query}
        if year is not None:
            params["year"] = year
        response = self._client.get("/search/movie", params=params)
        response.raise_for_status()
        return response.json()


class MovieMetadataProvider(Protocol):
    """Interface for pluggable movie metadata providers."""

    name: str

    def fetch_movie(
        self, tmdb_id: int, *, append_to_response: list[str] | None = None
    ) -> dict[str, Any]:
        ...


class TMDBProvider:
    """Provider that delegates to TMDb APIs."""

    name = "tmdb"

    def __init__(self, client: TMDBClient | None = None) -> None:
        self._client = client or TMDBClient()

    def fetch_movie(
        self, tmdb_id: int, *, append_to_response: list[str] | None = None
    ) -> dict[str, Any]:
        return self._client.movie_details(tmdb_id, append_to_response=append_to_response)


class OMDBProvider:
    """Provider that proxies requests to the OMDb API."""

    name = "omdb"

    def __init__(
        self,
        api_key: str,
        base_url: str,
        client: httpx.Client | None = None,
    ) -> None:
        headers = {"Accept": "application/json"}
        self._client = client or httpx.Client(base_url=base_url, headers=headers, timeout=10.0)
        self._api_key = api_key

    def fetch_movie(
        self, tmdb_id: int, *, append_to_response: list[str] | None = None  # noqa: ARG002 - interface parity
    ) -> dict[str, Any]:
        response = self._client.get("", params={"apikey": self._api_key, "i": f"tt{tmdb_id}"})
        response.raise_for_status()
        payload = response.json()

        if str(payload.get("Response")).lower() == "false":
            raise ValueError(payload.get("Error") or "OMDb query failed")

        actors = [
            actor.strip() for actor in (payload.get("Actors") or "").split(",") if actor.strip()
        ]
        release_year = (payload.get("Year") or "").split("–")[0].strip()

        return {
            "id": tmdb_id,
            "title": payload.get("Title"),
            "original_title": payload.get("Title"),
            "overview": payload.get("Plot"),
            "release_date": f"{release_year}-01-01" if release_year else None,
            "credits": {
                "cast": [
                    {
                        "id": abs(hash((tmdb_id, actor, index))) % 2_147_483_647,
                        "name": actor,
                        "character": None,
                        "order": index,
                    }
                    for index, actor in enumerate(actors)
                ]
            },
            # OMDb does not expose still artwork URLs in the free tier; keep structure consistent
            "images": {"posters": [], "backdrops": []},
        }


def _select_provider(
    settings: Settings | None = None,
    *,
    provider_hint: str | None = None,
    client: TMDBClient | httpx.Client | None = None,
) -> MovieMetadataProvider:
    resolved_settings = settings or get_settings()
    hint = (provider_hint or "").lower()
    tmdb_client = client if isinstance(client, TMDBClient) else TMDBClient(client)
    omdb_client: httpx.Client | None
    if isinstance(client, httpx.Client):
        omdb_client = client
    elif isinstance(client, TMDBClient):
        omdb_client = client._client
    else:
        omdb_client = None

    if hint == "omdb" and resolved_settings.omdb_api_key:
        return OMDBProvider(
            resolved_settings.omdb_api_key,
            resolved_settings.omdb_base_url,
            client=omdb_client,
        )

    if resolved_settings.tmdb_api_key or hint == "tmdb":
        return TMDBProvider(tmdb_client)

    if resolved_settings.omdb_api_key:
        return OMDBProvider(
            resolved_settings.omdb_api_key,
            resolved_settings.omdb_base_url,
            client=omdb_client,
        )

    return TMDBProvider(tmdb_client)


SessionFactory = Callable[[], Session]


def _cleanup_session(session_factory: SessionFactory, session: Session) -> None:
    if hasattr(session_factory, "remove"):
        session_factory.remove()  # type: ignore[call-arg]
    else:
        session.close()


@contextmanager
def _session_scope(
    session_factory: SessionFactory | None = None,
) -> Generator[Session, None, None]:
    factory = session_factory or SessionLocal
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        _cleanup_session(factory, session)


def _parse_release_year(release_date: str | None) -> int | None:
    if not release_date:
        return None
    try:
        return int(release_date.split("-")[0])
    except (ValueError, IndexError):
        return None


def _calculate_aspect_ratio(width: int | None, height: int | None, provided: float | None) -> float | None:
    if width and height and height != 0:
        return round(width / height, 3)
    return provided


class TMDBIngestor:
    """Fetch movie metadata from TMDb and persist it locally."""

    def __init__(
        self,
        client: TMDBClient | None = None,
        provider: MovieMetadataProvider | None = None,
        provider_hint: str | None = None,
        session_factory: SessionFactory | None = None,
    ) -> None:
        self._provider = provider or _select_provider(provider_hint=provider_hint, client=client)
        self._session_factory = session_factory or SessionLocal

    def ingest_movie(self, tmdb_id: int) -> dict[str, Any]:
        payload = self._provider.fetch_movie(tmdb_id, append_to_response=["credits", "images"])

        with _session_scope(self._session_factory) as session:
            movie = self._upsert_movie(session, payload)
            cast_count = self._persist_cast(session, movie, payload.get("credits", {}))
            artwork_count = self._persist_artwork(
                session, movie, payload.get("images", {})
            )

            logger.info(
                "Metadata import (%s) for %s: movie_id=%s cast=%s artwork=%s",
                self._provider.name,
                tmdb_id,
                movie.id,
                cast_count,
                artwork_count,
            )

            return {
                "movie_id": movie.id,
                "tmdb_id": movie.tmdb_id,
                "provider": self._provider.name,
                "cast_count": cast_count,
                "artwork_count": artwork_count,
            }

    def _upsert_movie(self, session: Session, payload: dict[str, Any]) -> Movie:
        tmdb_id = payload.get("id")
        if tmdb_id is None:
            raise ValueError("TMDb payload missing movie id")

        title = payload.get("title") or payload.get("original_title") or "Untitled"
        description = payload.get("overview")
        release_year = _parse_release_year(payload.get("release_date"))

        movie = session.query(Movie).filter_by(tmdb_id=tmdb_id).one_or_none()
        if movie is None:
            movie = Movie(tmdb_id=tmdb_id)

        movie.title = title
        movie.description = description
        movie.release_year = release_year
        movie.metadata_json = payload

        session.add(movie)
        session.flush()

        return movie

    def _persist_cast(
        self, session: Session, movie: Movie, credits: dict[str, Any]
    ) -> int:
        cast_entries = credits.get("cast") or []
        stored = 0

        for entry in cast_entries:
            tmdb_cast_id = entry.get("id")
            name = entry.get("name")
            if tmdb_cast_id is None or not name:
                continue

            cast_member = (
                session.query(CastMember).filter_by(tmdb_id=tmdb_cast_id).one_or_none()
            )
            if cast_member is None:
                cast_member = CastMember(tmdb_id=tmdb_cast_id)

            cast_member.name = name
            cast_member.profile_path = entry.get("profile_path")

            session.add(cast_member)
            session.flush()

            mapping = (
                session.query(MovieCast)
                .filter_by(movie_id=movie.id, cast_member_id=cast_member.id)
                .one_or_none()
            )
            if mapping is None:
                mapping = MovieCast(movie_id=movie.id, cast_member_id=cast_member.id)

            mapping.character = entry.get("character")
            mapping.cast_order = entry.get("order")

            session.add(mapping)
            stored += 1

        return stored

    def _persist_artwork(
        self, session: Session, movie: Movie, images: dict[str, Any]
    ) -> int:
        stored = 0

        for kind, key in (("poster", "posters"), ("backdrop", "backdrops")):
            for artwork in images.get(key, []) or []:
                file_path = artwork.get("file_path")
                if not file_path:
                    continue

                width = artwork.get("width")
                height = artwork.get("height")

                record = (
                    session.query(Artwork)
                    .filter_by(movie_id=movie.id, file_path=file_path, kind=kind)
                    .one_or_none()
                )
                if record is None:
                    record = Artwork(movie_id=movie.id, file_path=file_path, kind=kind)

                record.width = width
                record.height = height
                record.aspect_ratio = _calculate_aspect_ratio(
                    width, height, artwork.get("aspect_ratio")
                )
                record.language = artwork.get("iso_639_1")

                session.add(record)
                stored += 1

        return stored
