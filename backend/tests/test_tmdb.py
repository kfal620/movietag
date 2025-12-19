import httpx

from app.integrations.tmdb import TMDBClient


def test_tmdb_client_fetches_movie_details(monkeypatch):
    requested_paths = []

    def handler(request: httpx.Request) -> httpx.Response:  # type: ignore[override]
        requested_paths.append(str(request.url))
        assert request.headers.get("Authorization") == "Bearer test-key"
        return httpx.Response(200, json={"id": 123, "title": "Example"})

    transport = httpx.MockTransport(handler)

    monkeypatch.setenv("TMDB_API_KEY", "test-key")
    monkeypatch.setenv("TMDB_BASE_URL", "https://example.test")

    client = TMDBClient(httpx.Client(transport=transport, base_url="https://example.test"))
    result = client.movie_details(123)

    assert result["id"] == 123
    assert any(path.endswith("/movie/123") for path in requested_paths)
