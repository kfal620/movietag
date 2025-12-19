from pathlib import Path

import numpy as np
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, Frame, Movie
from app.tasks import frames as frame_tasks


def create_image(tmp_path: Path) -> Path:
    array = np.zeros((10, 10, 3), dtype=np.uint8)
    array[:, :, 0] = 255
    path = tmp_path / "test.jpg"
    Image.fromarray(array, "RGB").save(path)
    return path


def test_embed_and_tag_pipeline(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        movie = Movie(title="Test Movie")
        session.add(movie)
        session.commit()
        image_path = create_image(tmp_path)
        frame = Frame(movie_id=movie.id, file_path=str(image_path))
        session.add(frame)
        session.commit()
        session.refresh(frame)
        frame_id = frame.id

    monkeypatch.setattr(frame_tasks, "SessionLocal", SessionLocal)

    embed_result = frame_tasks.embed_frame(frame_id)
    assert embed_result["embedding_dimensions"] >= 128

    tag_result = frame_tasks.tag_frame(frame_id)
    assert tag_result["status"] == "tagged"

    scene_result = frame_tasks.detect_scene_attributes(frame_id)
    assert scene_result["attributes"]

    actor_result = frame_tasks.detect_actor_faces(frame_id)
    assert actor_result["status"] == "actors_detected"
