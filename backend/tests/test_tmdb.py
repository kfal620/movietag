import httpx

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.integrations.tmdb import TMDBClient, TMDBIngestor
from app.models import Artwork, Base, CastMember, Movie, MovieCast


def test_tmdb_client_fetches_movie_details(monkeypatch):
    requested_paths = []

    def handler(request: httpx.Request) -> httpx.Response:  # type: ignore[override]
        requested_paths.append(str(request.url))
        assert request.headers.get("Authorization") == "Bearer test-key"
        return httpx.Response(200, json={"id": 123, "title": "Example"})

    transport = httpx.MockTransport(handler)

    monkeypatch.setenv("TMDB_API_KEY", "test-key")
    monkeypatch.setenv("TMDB_BASE_URL", "https://example.test")

    client = TMDBClient(
        httpx.Client(transport=transport, base_url="https://example.test")
    )
    result = client.movie_details(123)

    assert result["id"] == 123
    assert any(path.endswith("/movie/123") for path in requested_paths)


def test_tmdb_ingestor_persists_movie_cast_and_artwork(monkeypatch):
    movie_payload = {
        "id": 550,
        "title": "Fight Club",
        "overview": "An insomniac office worker...",
        "release_date": "1999-10-12",
        "credits": {
            "cast": [
                {
                    "id": 1,
                    "name": "First Actor",
                    "character": "Narrator",
                    "order": 0,
                    "profile_path": "/narrator.jpg",
                },
                {
                    "id": 2,
                    "name": "Second Actor",
                    "character": "Tyler",
                    "order": 1,
                    "profile_path": None,
                },
            ]
        },
        "images": {
            "posters": [
                {
                    "file_path": "/poster.jpg",
                    "width": 1000,
                    "height": 1500,
                    "iso_639_1": "en",
                    "aspect_ratio": 0.666,
                }
            ],
            "backdrops": [
                {
                    "file_path": "/backdrop.jpg",
                    "width": 1920,
                    "height": 1080,
                    "iso_639_1": None,
                    "aspect_ratio": 1.777,
                }
            ],
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:  # type: ignore[override]
        assert "append_to_response=credits%2Cimages" in str(request.url)
        return httpx.Response(200, json=movie_payload)

    transport = httpx.MockTransport(handler)

    monkeypatch.setenv("TMDB_API_KEY", "test-key")
    monkeypatch.setenv("TMDB_BASE_URL", "https://example.test")

    client = TMDBClient(
        httpx.Client(transport=transport, base_url="https://example.test")
    )

    engine = create_engine("sqlite://")
    TestingSessionLocal = sessionmaker(bind=engine)

    Base.metadata.create_all(engine)

    ingestor = TMDBIngestor(client=client, session_factory=TestingSessionLocal)
    result = ingestor.ingest_movie(550)

    assert result["tmdb_id"] == 550
    assert result["cast_count"] == 2
    assert result["artwork_count"] == 2

    with TestingSessionLocal() as session:
        movie = session.query(Movie).filter_by(tmdb_id=550).one()
        assert movie.title == "Fight Club"
        assert movie.release_year == 1999

        cast_members = session.query(CastMember).all()
        assert {member.tmdb_id for member in cast_members} == {1, 2}

        mappings = session.query(MovieCast).filter_by(movie_id=movie.id).all()
        assert len(mappings) == 2
        assert any(mapping.character == "Narrator" for mapping in mappings)

        artwork = session.query(Artwork).filter_by(movie_id=movie.id).all()
        assert len(artwork) == 2
