from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.movies import _serialize_movie
from app.db import get_db
from app.main import create_application
from app.models import Base, Movie


def setup_app():
    import os

    os.environ["CELERY_BROKER_URL"] = "memory://"
    os.environ["CELERY_RESULT_BACKEND"] = "cache+memory://"
    os.environ["MODERATOR_TOKEN"] = "moderator-token"
    os.environ["ADMIN_TOKEN"] = "admin-token"

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)

    app = create_application()

    def _get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    return app, SessionLocal


def test_list_movies_returns_items(monkeypatch):
    app, SessionLocal = setup_app()
    with SessionLocal() as session:
        movie = Movie(title="Example", tmdb_id=99)
        session.add(movie)
        session.commit()

    client = TestClient(app)
    response = client.get("/api/movies")
    assert response.status_code == 200
    assert response.json()["items"][0]["tmdb_id"] == 99


def test_ingest_tmdb_movie_enqueues_task(monkeypatch):
    app, _ = setup_app()

    class FakeResult:
        id = "tmdb-1"

    class FakeTask:
        def delay(self, tmdb_id):
            return FakeResult()

    from app.api import routes as routes_pkg
    monkeypatch.setattr(routes_pkg.movies, "ingest_movie_from_tmdb", FakeTask())
    client = TestClient(app)
    response = client.post(
        "/api/movies/ingest",
        json={"tmdb_id": 550},
        headers={"Authorization": "Bearer moderator-token"},
    )
    assert response.status_code == 200
    assert response.json()["task_id"] == "tmdb-1"
