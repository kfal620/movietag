from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.frames import _serialize_frame
from app.db import get_db
from app.main import create_application
from app.models import (
    ActorDetection,
    Base,
    Frame,
    FrameTag,
    Movie,
    SceneAttribute,
    Tag,
)


def build_app_with_db():
    # Use an in-memory Celery transport to avoid external dependencies during tests.
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
    TestingSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)

    app = create_application()

    def _get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    return app, TestingSessionLocal


def seed_frame(session):
    movie = Movie(title="Test Movie", description="Desc", release_year=2020)
    session.add(movie)
    session.flush()
    frame = Frame(
        movie_id=movie.id,
        file_path="/tmp/test.jpg",
        status="tagged",
        ingested_at=datetime.utcnow(),
    )
    tag = Tag(name="night")
    session.add_all([frame, tag])
    session.flush()
    session.add(FrameTag(frame_id=frame.id, tag_id=tag.id, confidence=0.9))
    session.add(
        SceneAttribute(
            frame_id=frame.id, attribute="time_of_day", value="night", confidence=0.8
        )
    )
    session.add(ActorDetection(frame_id=frame.id, cast_member_id=None, confidence=0.5))
    session.commit()
    return frame.id


def test_list_frames_filters_and_serializes():
    app, SessionLocal = build_app_with_db()
    with SessionLocal() as session:
        frame_id = seed_frame(session)

    client = TestClient(app)
    response = client.get("/api/frames", params={"tag": "night"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == frame_id
    assert body["items"][0]["tags"][0]["name"] == "night"


def test_get_frame_by_id_returns_details():
    app, SessionLocal = build_app_with_db()
    with SessionLocal() as session:
        frame_id = seed_frame(session)

    client = TestClient(app)
    response = client.get(f"/api/frames/{frame_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == frame_id
    assert payload["scene_attributes"][0]["attribute"] == "time_of_day"


def test_replace_frame_tags_updates_status(monkeypatch):
    app, SessionLocal = build_app_with_db()
    with SessionLocal() as session:
        frame_id = seed_frame(session)

    client = TestClient(app)
    response = client.post(
        f"/api/frames/{frame_id}/tags",
        json={"tags": ["sunrise", "city"]},
        headers={"Authorization": "Bearer moderator-token"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "confirmed"
    assert {tag["name"] for tag in payload["tags"]} == {"sunrise", "city"}


def test_upload_ingest_enqueues_task(monkeypatch):
    app, SessionLocal = build_app_with_db()
    with SessionLocal() as session:
        seed_frame(session)

    class FakeResult:
        id = "task-123"

    class FakeTask:
        def delay(self, **kwargs):
            return FakeResult()

    from app.api import routes as routes_pkg

    monkeypatch.setattr(routes_pkg.frames, "ingest_and_tag_frame", FakeTask())
    client = TestClient(app)
    response = client.post(
        "/api/frames/ingest/upload",
        data={"movie_id": 1},
        files={"file": ("demo.jpg", b"binarydata", "image/jpeg")},
        headers={"Authorization": "Bearer moderator-token"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"] == "task-123"


def test_moderation_endpoints_require_valid_token():
    app, SessionLocal = build_app_with_db()
    with SessionLocal() as session:
        frame_id = seed_frame(session)

    client = TestClient(app)
    missing_header = client.post(
        f"/api/frames/{frame_id}/tags", json={"tags": ["city"]}
    )
    assert missing_header.status_code == 401

    bad_token = client.post(
        f"/api/frames/{frame_id}/tags",
        json={"tags": ["city"]},
        headers={"Authorization": "Bearer invalid"},
    )
    assert bad_token.status_code == 403


def test_serialize_frame_prefers_existing_signed_url(monkeypatch):
    app, SessionLocal = build_app_with_db()
    with SessionLocal() as session:
        frame_id = seed_frame(session)
        frame = session.get(Frame, frame_id)
        frame.signed_url = "https://example.com/prefetched"
        session.add(frame)
        session.commit()

    client = TestClient(app)
    response = client.get(f"/api/frames/{frame_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["signed_url"] == "https://example.com/prefetched"


def test_serialize_frame_generates_signed_url_from_storage(monkeypatch):
    app, SessionLocal = build_app_with_db()
    with SessionLocal() as session:
        frame_id = seed_frame(session)
        frame = session.get(Frame, frame_id)
        frame.storage_uri = "s3://frames/demo.jpg"
        frame.signed_url = None
        session.add(frame)
        session.commit()

    from app import services

    monkeypatch.setattr(
        services.storage,
        "generate_presigned_url",
        lambda storage_uri, expires_in=600: f"https://signed.example.com/{storage_uri}",
    )

    client = TestClient(app)
    response = client.get(f"/api/frames/{frame_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["signed_url"] == "https://signed.example.com/s3://frames/demo.jpg"
