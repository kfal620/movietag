"""Frame ingestion and tagging tasks."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
import time
from typing import Any, Iterable

import numpy as np
from PIL import Image
from celery import shared_task
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.db import SessionLocal
from app.models import ActorDetection, Frame, FrameTag, Movie, SceneAttribute, Tag
from app.services.film_matcher import FilmMatcher
from app.services.storage import download_to_path
from app.services.vision import detect_faces, encode_image_with_clip
from datetime import datetime

logger = logging.getLogger(__name__)

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


def _hash_embedding(seed: bytes, dimensions: int = 8) -> list[float]:
    # Legacy deterministic hash fallback for environments without image libraries.
    digest = sum(seed) or 1
    np.random.seed(digest)
    vector = np.random.default_rng(digest).random(dimensions)
    return [round(float(value), 6) for value in vector.tolist()]


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


def _load_image(path: Path) -> Image.Image:
    with Image.open(path) as image:
        return image.convert("RGB")


def _compute_embedding(image: Image.Image, dimensions: int = 128) -> list[float]:
    """Derive a lightweight embedding from image pixels."""

    rgb_array = np.asarray(image)

    # Resize down to keep computation fast and deterministic
    height, width = rgb_array.shape[:2]
    downsample_factor = max(1, min(height, width) // 64)
    reduced = rgb_array[::downsample_factor, ::downsample_factor, :]

    # Channel-wise statistics + flattened sample
    mean_channels = reduced.mean(axis=(0, 1))
    std_channels = reduced.std(axis=(0, 1))
    flattened = reduced.flatten().astype(float)

    if flattened.size > dimensions:
        indices = np.linspace(0, flattened.size - 1, dimensions - 6).astype(int)
        sample = flattened[indices]
    else:
        sample = np.pad(flattened, (0, max(0, dimensions - flattened.size)), mode="wrap")

    vector = np.concatenate([mean_channels, std_channels, sample])
    # Normalize to unit length to mirror typical embeddings
    norm = np.linalg.norm(vector) or 1.0
    normalized = vector / norm
    return [round(float(value), 6) for value in normalized.tolist()[:dimensions]]


def _match_frame_with_known_movies(
    session: Session, frame: Frame
) -> dict[str, Any] | None:
    matcher = FilmMatcher(session)
    embedding = json.loads(frame.embedding) if frame.embedding else []

    # Reset predictions before attempting a new match
    frame.predicted_movie_id = None
    frame.match_confidence = None
    frame.predicted_timestamp = None
    frame.predicted_shot_id = None

    match = matcher.match_movie(embedding)
    if match:
        frame.predicted_movie_id = match["movie_id"]
        frame.match_confidence = match["confidence"]
        frame.predicted_timestamp = match.get("timestamp")
        frame.predicted_shot_id = match.get("shot_id")
        frame.status = "matched"
        frame.failure_reason = None
        session.add(frame)
        return match

    frame.status = "unmatched"
    frame.failure_reason = None
    session.add(frame)
    return None


def _persist_scene_attributes(
    session: Session, frame: Frame, embedding: list[float], *, min_confidence: float = 0.35
) -> list[dict[str, Any]]:
    time_of_day_score = embedding[0] if embedding else 0.5
    attribute_rows = [
        ("time_of_day", "night" if time_of_day_score < 0.45 else "day", 1 - abs(0.5 - time_of_day_score)),
        ("lighting", "low_key" if time_of_day_score < 0.4 else "high_key", 0.8),
    ]
    applied: list[dict[str, Any]] = []
    for attribute, value, confidence in attribute_rows:
        value_to_store = value if confidence >= min_confidence else "unknown"
        record = SceneAttribute(
            frame_id=frame.id,
            attribute=attribute,
            value=value_to_store,
            confidence=round(float(confidence), 3),
        )
        session.add(record)
        applied.append({"attribute": attribute, "value": value_to_store, "confidence": record.confidence})
    return applied


def _persist_actor_detections(session: Session, frame: Frame) -> list[dict[str, Any]]:
    from app.models import MovieCast, CastMember  # local import to avoid cycles

    movie_cast = (
        session.query(CastMember.id, CastMember.name)
        .join(MovieCast, MovieCast.cast_member_id == CastMember.id)
        .filter(MovieCast.movie_id == frame.movie_id)
        .order_by(MovieCast.cast_order)
        .limit(3)
        .all()
    )
    detections: list[dict[str, Any]] = []
    for index, (cast_member_id, name) in enumerate(movie_cast):
        confidence = round(0.7 - 0.05 * index, 3)
        record = ActorDetection(
            frame_id=frame.id,
            cast_member_id=cast_member_id,
            face_index=index,
            confidence=confidence,
            bbox=f"{0.1 * index},{0.1 * index},0.3,0.3",
        )
        session.add(record)
        detections.append(
            {"cast_member_id": cast_member_id, "name": name, "confidence": confidence}
        )
    return detections


def _ensure_local_copy(file_path: str, storage_uri: str | None) -> Path:
    path = Path(file_path)
    if path.exists():
        return path

    if storage_uri:
        path.parent.mkdir(parents=True, exist_ok=True)
        download_to_path(storage_uri, str(path))
        return path

    raise FileNotFoundError(f"Frame not found at {file_path}")


def _mark_failure(frame_id: int, reason: str, session_factory: SessionFactory | None = None) -> None:
    with _session_scope(session_factory) as session:
        frame = session.get(Frame, frame_id)
        if frame is None:
            return
        frame.failure_reason = reason
        frame.status = "failed"
        session.add(frame)


def _materialize_frame(frame: Frame) -> tuple[Path, bool]:
    """Return a path to the frame contents, downloading from storage if necessary."""

    try:
        return _ensure_local_copy(frame.file_path, frame.storage_uri), False
    except FileNotFoundError:
        pass

    if frame.storage_uri:
        temp = NamedTemporaryFile(delete=False, suffix=Path(frame.file_path).suffix or ".img")
        download_to_path(frame.storage_uri, temp.name)
        return Path(temp.name), True

    if frame.signed_url:
        import requests

        response = requests.get(frame.signed_url, timeout=30)
        response.raise_for_status()
        temp = NamedTemporaryFile(delete=False, suffix=Path(frame.file_path).suffix or ".img")
        temp.write(response.content)
        temp.flush()
        return Path(temp.name), True

    raise FileNotFoundError("Frame content is unavailable (no storage_uri or signed_url)")


@shared_task(name="frames.import")
def import_frame(
    file_path: str,
    movie_id: int | None = None,
    storage_uri: str | None = None,
    signed_url: str | None = None,
    captured_at: str | None = None,
    session_factory: SessionFactory | None = None,
) -> dict[str, Any]:
    """Import a still frame from disk or object storage.

    The task validates the frame location, asserts the movie exists (when provided), and
    persists a ``Frame`` row that downstream tasks can embed and tag.
    """

    temp_file: Path | None = None
    try:
        try:
            path = _ensure_local_copy(file_path, storage_uri)
        except FileNotFoundError:
            if storage_uri:
                temp = NamedTemporaryFile(delete=False)
                download_to_path(storage_uri, temp.name)
                path = Path(temp.name)
                temp_file = path
            elif signed_url:
                import requests

                response = requests.get(signed_url, timeout=30)
                response.raise_for_status()
                temp = NamedTemporaryFile(delete=False)
                temp.write(response.content)
                temp.flush()
                path = Path(temp.name)
                temp_file = path
            else:
                raise

        logger.info("Importing frame from %s for movie %s", path, movie_id or "unknown")

        with _session_scope(session_factory) as session:
            movie = session.get(Movie, movie_id) if movie_id is not None else None
            if movie_id is not None and movie is None:
                raise ValueError(f"Movie with id {movie_id} does not exist")

            parsed_captured_at = None
            if captured_at:
                try:
                    parsed_captured_at = datetime.fromisoformat(captured_at)
                except Exception:
                    parsed_captured_at = None

            frame = Frame(
                movie_id=movie_id,
                file_path=str(path),
                storage_uri=storage_uri,
                signed_url=signed_url,
                captured_at=parsed_captured_at,
                ingested_at=datetime.utcnow(),
                status="new",
                failure_reason=None,
            )
            session.add(frame)
            session.flush()
            session.refresh(frame)

            return {
                "status": "imported",
                "frame_id": frame.id,
                "file_path": frame.file_path,
                "movie_id": frame.movie_id,
                "storage_uri": frame.storage_uri,
            }
    finally:
        if temp_file and temp_file.exists():
            try:
                temp_file.unlink()
            except Exception:
                logger.warning("Failed to cleanup temp file %s", temp_file)


@shared_task(name="frames.embed")
def embed_frame(
    frame_id: int,
    embedding_model: str = "rgb-histogram-v1",
    session_factory: SessionFactory | None = None,
) -> dict[str, Any]:
    """Generate an image-derived embedding vector for a frame and persist it."""

    settings = get_settings()
    clip_model = f"{settings.clip_model_name}:{settings.clip_pretrained}"
    embed_model_name = embedding_model
    embed_model_version = settings.embedding_model_version or settings.clip_pretrained

    with _session_scope(session_factory) as session:
        frame = session.get(Frame, frame_id)
        if frame is None:
            raise ValueError(f"Frame with id {frame_id} does not exist")

        frame.status = "embedding"
        frame.failure_reason = None
        session.add(frame)
        session.flush()

        path, cleanup = _materialize_frame(frame)
        try:
            image = _load_image(path)
            try:
                if settings.embedding_service_url:
                    import requests

                    with open(path, "rb") as handle:
                        resp = requests.post(
                            settings.embedding_service_url,
                            files={"file": handle},
                            timeout=30,
                        )
                    resp.raise_for_status()
                    payload = resp.json()
                    embedding = payload.get("embedding")
                    embed_model_name = payload.get("model", embed_model_name)
                    embed_model_version = payload.get("version", embed_model_version)
                else:
                    embedding = encode_image_with_clip(
                        image=image,
                        model_name=settings.clip_model_name,
                        pretrained=settings.clip_pretrained,
                    )
                    embed_model_name = f"clip-{clip_model}"
            except Exception:
                logger.exception("Falling back to deterministic embedding for frame %s", frame.id)
                embedding = _compute_embedding(image)
                embed_model_name = embed_model_name or "rgb-histogram-v1"
        except FileNotFoundError as exc:
            _mark_failure(frame.id, str(exc))
            raise
        finally:
            if cleanup and path.exists():
                try:
                    path.unlink()
                except Exception:
                    logger.warning("Could not cleanup temporary file for frame %s", frame.id)

        frame.embedding = json.dumps(embedding)
        frame.embedding_model = embed_model_name
        frame.embedding_model_version = embed_model_version
        frame.status = "embedded"
        session.add(frame)

        logger.info("Embedded frame %s (dim=%s)", frame.id, len(embedding))

        return {
            "status": "embedded",
            "frame_id": frame.id,
            "embedding_dimensions": len(embedding),
            "embedding_model": embed_model_name,
            "embedding_model_version": embed_model_version,
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

        frame.failure_reason = None
        frame.status = "tagged"
        session.add(frame)

        logger.info("Tagged frame %s with %s labels", frame.id, len(applied_tags))

        return {"status": "tagged", "frame_id": frame.id, "tags": applied_tags}


@shared_task(name="frames.scene_attributes")
def detect_scene_attributes(
    frame_id: int, session_factory: SessionFactory | None = None
) -> dict[str, Any]:
    with _session_scope(session_factory) as session:
        frame = session.get(Frame, frame_id)
        if frame is None:
            raise ValueError(f"Frame with id {frame_id} does not exist")

        # Idempotency: clear prior predictions
        session.query(SceneAttribute).filter(SceneAttribute.frame_id == frame.id).delete()

        embedding = json.loads(frame.embedding) if frame.embedding else []
        applied = _persist_scene_attributes(session, frame, embedding)

        frame.failure_reason = None
        frame.status = "scene_annotated"
        session.add(frame)

        logger.info("Scene attributes stored for frame %s", frame.id)
        return {"status": "scene_attributes", "frame_id": frame.id, "attributes": applied}


@shared_task(name="frames.actor_detections")
def detect_actor_faces(frame_id: int, session_factory: SessionFactory | None = None) -> dict[str, Any]:
    settings = get_settings()
    cleanup = False
    path: Path | None = None
    try:
        with _session_scope(session_factory) as session:
            frame = session.get(Frame, frame_id)
            if frame is None:
                raise ValueError(f"Frame with id {frame_id} does not exist")

            # remove existing detections to keep task idempotent
            session.query(ActorDetection).filter(ActorDetection.frame_id == frame.id).delete()

            path, cleanup = _materialize_frame(frame)
            image = _load_image(path)

            try:
                detected_faces = detect_faces(image, min_confidence=settings.face_min_confidence)
            except Exception:
                logger.exception("Falling back to legacy actor detection for frame %s", frame.id)
                detected_faces = []

            from app.models import MovieCast, CastMember  # local import to avoid cycles

            cast_member_ids = [
                cast_member_id
                for (cast_member_id,) in (
                    session.query(CastMember.id)
                        .join(MovieCast, MovieCast.cast_member_id == CastMember.id)
                        .filter(MovieCast.movie_id == frame.movie_id)
                        .order_by(MovieCast.cast_order)
                        .all()
                )
            ]

            persisted: list[dict[str, Any]] = []
            for index, face in enumerate(detected_faces):
                cast_member_id = cast_member_ids[index] if index < len(cast_member_ids) else None
                bbox = ",".join(f"{value:.2f}" for value in face.bbox) if face.bbox else None
                if face.confidence < settings.face_min_confidence:
                    cast_member_id = None
                detection = ActorDetection(
                    frame_id=frame.id,
                    cast_member_id=cast_member_id,
                    face_index=index,
                    confidence=round(face.confidence, 3),
                    bbox=bbox,
                )
                session.add(detection)
                persisted.append(
                    {
                        "cast_member_id": cast_member_id,
                        "confidence": detection.confidence,
                        "bbox": face.bbox,
                    }
                )

            if not persisted and not detected_faces:
                persisted = _persist_actor_detections(session, frame)

            frame.failure_reason = None
            frame.status = "actors_detected"
            session.add(frame)
            return {
                "status": "actors_detected",
                "frame_id": frame.id,
                "detections": persisted,
            }
    finally:
        if cleanup and path and path.exists():
            try:
                path.unlink()
            except Exception:
                logger.warning("Could not cleanup face detection temp file for frame %s", frame_id)


def _match_frame(
    frame_id: int, session_factory: SessionFactory | None = None
) -> dict[str, Any]:
    with _session_scope(session_factory) as session:
        frame = session.get(Frame, frame_id)
        if frame is None:
            raise ValueError(f"Frame with id {frame_id} does not exist")
        match = _match_frame_with_known_movies(session, frame)
        return {
            "status": "matched" if match else "unmatched",
            "predicted_movie_id": frame.predicted_movie_id,
            "match_confidence": frame.match_confidence,
            "predicted_timestamp": frame.predicted_timestamp,
            "predicted_shot_id": frame.predicted_shot_id,
        }


@shared_task(
    name="frames.pipeline",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def ingest_and_tag_frame(
    self,
    file_path: str,
    movie_id: int | None = None,
    storage_uri: str | None = None,
    signed_url: str | None = None,
    captured_at: str | None = None,
) -> dict[str, Any]:
    """End-to-end pipeline to import, embed, and either tag or match a frame."""

    started = time.monotonic()
    import_result = import_frame(
        file_path=file_path,
        movie_id=movie_id,
        storage_uri=storage_uri,
        signed_url=signed_url,
        captured_at=captured_at,
    )
    frame_id = import_result["frame_id"]

    try:
        embed_result = embed_frame(frame_id)
        if movie_id is None:
            match_result = _match_frame(frame_id)
        else:
            tag_result = tag_frame(frame_id)
            scene_result = detect_scene_attributes(frame_id)
            actor_result = detect_actor_faces(frame_id)
    except Exception as exc:  # pragma: no cover - defensive path
        logger.exception("Pipeline failed for frame %s", frame_id)
        _mark_failure(frame_id, str(exc))
        raise

    with _session_scope() as session:
        frame = session.get(Frame, frame_id)
        if frame and movie_id is not None:
            frame.status = "tagged"
            frame.failure_reason = None
            session.add(frame)

    elapsed = round(time.monotonic() - started, 3)
    logger.info("Pipeline completed for frame %s in %ss", frame_id, elapsed)

    results: dict[str, Any] = {"import": import_result, "embed": embed_result}
    if movie_id is None:
        results["match"] = match_result
    else:
        results.update({"tag": tag_result, "scene": scene_result, "actors": actor_result})
    return {"frame_id": frame_id, "results": results}
