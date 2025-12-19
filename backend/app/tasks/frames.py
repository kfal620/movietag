"""Frame ingestion and tagging tasks."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any, Iterable

from celery import shared_task
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Frame, FrameTag, Movie, Tag

logger = logging.getLogger(__name__)

SessionFactory = Callable[[], Session]


def _cleanup_session(session_factory: SessionFactory, session: Session) -> None:
    if hasattr(session_factory, "remove"):
        session_factory.remove()  # type: ignore[call-arg]
    else:
        session.close()


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


def _hash_embedding(seed: bytes, dimensions: int = 8) -> list[float]:
    digest = hashlib.blake2b(seed, digest_size=dimensions * 4).digest()
    max_uint32 = 2**32 - 1
    return [
        round(int.from_bytes(digest[i : i + 4], "big") / max_uint32, 6)
        for i in range(0, len(digest), 4)
    ]


def _tokenize(text: str) -> list[str]:
    return [
        token.lower()
        for token in re.split(r"[\s_\-]+", text)
        if token.strip()
    ]


def _derive_candidate_tags(frame: Frame, movie: Movie) -> list[str]:
    file_tokens = _tokenize(Path(frame.file_path).stem)
    title_tokens = _tokenize(movie.title)

    combined: list[str] = []
    for token in [*file_tokens, *title_tokens]:
        if token and token not in combined:
            combined.append(token)

    if movie.release_year and str(movie.release_year) not in combined:
        combined.append(str(movie.release_year))

    return combined[:3] or ["untagged"]


def _confidence_scores(embedding: Iterable[float], count: int) -> list[float]:
    vector = list(embedding)
    scores: list[float] = []
    for index in range(count):
        base = vector[index % len(vector)] if vector else 0.5
        scores.append(round(0.4 + 0.6 * base, 4))
    return scores


@shared_task(name="frames.import")
def import_frame(
    file_path: str,
    movie_id: int | None = None,
    session_factory: SessionFactory | None = None,
) -> dict[str, Any]:
    """Import a still frame from disk or object storage.

    The task validates the frame location, asserts the movie exists, and persists a
    ``Frame`` row that downstream tasks can embed and tag.
    """

    if movie_id is None:
        raise ValueError("movie_id is required to import a frame")

    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Frame not found at {file_path}")

    logger.info("Importing frame from %s for movie %s", path, movie_id)

    with _session_scope(session_factory) as session:
        movie = session.get(Movie, movie_id)
        if movie is None:
            raise ValueError(f"Movie with id {movie_id} does not exist")

        frame = Frame(movie_id=movie_id, file_path=str(path))
        session.add(frame)
        session.flush()
        session.refresh(frame)

        return {
            "status": "imported",
            "frame_id": frame.id,
            "file_path": frame.file_path,
            "movie_id": frame.movie_id,
        }


@shared_task(name="frames.embed")
def embed_frame(
    frame_id: int,
    session_factory: SessionFactory | None = None,
) -> dict[str, Any]:
    """Generate a deterministic embedding vector for a frame and persist it."""

    with _session_scope(session_factory) as session:
        frame = session.get(Frame, frame_id)
        if frame is None:
            raise ValueError(f"Frame with id {frame_id} does not exist")

        data: bytes
        try:
            data = Path(frame.file_path).read_bytes()
        except FileNotFoundError:
            data = frame.file_path.encode()

        embedding = _hash_embedding(data)
        frame.embedding = json.dumps(embedding)
        session.add(frame)

        logger.info("Embedded frame %s (dim=%s)", frame.id, len(embedding))

        return {
            "status": "embedded",
            "frame_id": frame.id,
            "embedding_dimensions": len(embedding),
        }


@shared_task(name="frames.tag")
def tag_frame(
    frame_id: int,
    session_factory: SessionFactory | None = None,
) -> dict[str, Any]:
    """Assign predicted tags to a frame based on embeddings and metadata."""

    with _session_scope(session_factory) as session:
        frame = session.get(Frame, frame_id)
        if frame is None:
            raise ValueError(f"Frame with id {frame_id} does not exist")

        movie = session.get(Movie, frame.movie_id)
        if movie is None:
            raise ValueError(f"Movie with id {frame.movie_id} does not exist")

        embedding = json.loads(frame.embedding) if frame.embedding else []
        candidate_tags = _derive_candidate_tags(frame, movie)
        confidences = _confidence_scores(embedding, len(candidate_tags))

        applied_tags: list[dict[str, Any]] = []
        for tag_name, confidence in zip(candidate_tags, confidences):
            tag = session.query(Tag).filter_by(name=tag_name).one_or_none()
            if tag is None:
                tag = Tag(name=tag_name, description=f"Auto-generated tag {tag_name}")
                session.add(tag)
                session.flush()

            existing = (
                session.query(FrameTag)
                .filter_by(frame_id=frame.id, tag_id=tag.id)
                .one_or_none()
            )

            if existing is None:
                session.add(
                    FrameTag(
                        frame_id=frame.id,
                        tag_id=tag.id,
                        confidence=confidence,
                    )
                )

            applied_tags.append({"name": tag.name, "confidence": confidence})

        logger.info("Tagged frame %s with %s labels", frame.id, len(applied_tags))

        return {"status": "tagged", "frame_id": frame.id, "tags": applied_tags}
