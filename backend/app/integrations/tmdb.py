"""Minimal TMDb API client used for metadata enrichment."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.settings import get_settings


class TMDBClient:
    """HTTP client for interacting with TMDb."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        settings = get_settings()
        auth_header = (
            {"Authorization": f"Bearer {settings.tmdb_api_key}"}
            if settings.tmdb_api_key
            else {}
        )

        if client is None:
            self._client = httpx.Client(
                base_url=settings.tmdb_base_url,
                headers=auth_header or None,
                timeout=10.0,
            )
        else:
            if auth_header and "Authorization" not in client.headers:
                client.headers.update(auth_header)
            self._client = client

    def movie_details(self, tmdb_id: int) -> dict[str, Any]:
        """Fetch metadata for a movie by its TMDb identifier."""
        response = self._client.get(f"/movie/{tmdb_id}")
        response.raise_for_status()
        return response.json()
