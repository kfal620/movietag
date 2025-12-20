"""Frame ingestion and tagging tasks."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable, Generator
from contextlib import contextmanager
from io import BytesIO
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
from app.integrations.tmdb import TMDBIngestor
from app.models import ActorDetection, Frame, FrameTag, Movie, SceneAttribute, Tag
from app.services.film_matcher import FilmMatcher
from app.services.storage import download_to_path
from app.services.vision import (
    SceneAttributePrediction,
    cosine_similarity,
    detect_faces,
    encode_face_image,
    encode_image_with_clip,
    predict_scene_attributes,
)
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
    session: Session,
    frame: Frame,
    predictions: list[SceneAttributePrediction],
    *,
    min_confidence: float = 0.2,
) -> list[dict[str, Any]]:
    applied: list[dict[str, Any]] = []
    for prediction in predictions:
        if prediction.confidence is None:
            continue
        value_to_store = prediction.value if prediction.confidence >= min_confidence else "unknown"
        record = SceneAttribute(
            frame_id=frame.id,
            attribute=prediction.attribute,
            value=value_to_store,
            confidence=round(float(prediction.confidence), 3),
        )
        session.add(record)
        applied.append(
            {
                "attribute": prediction.attribute,
                "value": value_to_store,
                "confidence": record.confidence,
            }
        )
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
        embedding = _hash_embedding(f"{frame.id}-{index}".encode(), 64)
        record = ActorDetection(
            frame_id=frame.id,
            cast_member_id=cast_member_id,
            face_index=index,
            confidence=confidence,
            bbox=f"{0.1 * index},{0.1 * index},0.3,0.3",
            embedding=json.dumps(embedding),
            track_status="seeded",
        )
        session.add(record)
        detections.append(
            {"cast_member_id": cast_member_id, "name": name, "confidence": confidence}
        )
    return detections


def _load_headshot_image(profile_path: str) -> Image.Image | None:
    if not profile_path:
        return None
    path = Path(profile_path)
    try:
        if path.exists():
            return _load_image(path)
        if profile_path.startswith("http"):
            import requests

            response = requests.get(profile_path, timeout=20)
            response.raise_for_status()
            return Image.open(BytesIO(response.content)).convert("RGB")
    except Exception:
        logger.debug("Failed to load headshot %s", profile_path, exc_info=True)
    return None


def _reference_embeddings_for_cast(
    session: Session, frame: Frame, settings: Any
) -> dict[int, list[float]]:
    from app.models import MovieCast, CastMember  # local import to avoid cycles

    cast_records: list[CastMember] = (
        session.query(CastMember)
        .join(MovieCast, MovieCast.cast_member_id == CastMember.id)
        .filter(MovieCast.movie_id == frame.movie_id)
        .order_by(MovieCast.cast_order)
        .all()
    )
    embeddings: dict[int, list[float]] = {}
    for cast_member in cast_records:
        if cast_member.face_embedding:
            try:
                embeddings[cast_member.id] = json.loads(cast_member.face_embedding)
                continue
            except Exception:
                logger.debug("Invalid face embedding for cast member %s", cast_member.id)

        headshot = _load_headshot_image(cast_member.profile_path or "")
        if headshot is not None:
            try:
                embedding = encode_face_image(headshot)
                cast_member.face_embedding = json.dumps(embedding)
                cast_member.face_embedding_model = "facenet_vggface2"
                session.add(cast_member)
                embeddings[cast_member.id] = embedding
                continue
            except Exception:
                logger.debug("Failed to encode headshot for cast member %s", cast_member.id)

        embeddings[cast_member.id] = _hash_embedding(str(cast_member.id).encode(), 64)
    return embeddings


def _best_match_for_face(
    face_embedding: list[float],
    cast_embeddings: dict[int, list[float]],
    threshold: float,
) -> tuple[int | None, float]:
    best_id: int | None = None
    best_score = 0.0
    for cast_id, reference in cast_embeddings.items():
        try:
            score = cosine_similarity(face_embedding, reference)
        except Exception:
            score = 0.0
        if score > best_score:
            best_score = score
            best_id = cast_id
    if best_score < threshold:
        return None, best_score
    return best_id, best_score


def _cluster_unknown_faces(
    session: Session,
    frame: Frame,
    detections: list[ActorDetection],
    unknown_threshold: float,
) -> dict[int, tuple[str, str]]:
    movie_id = frame.movie_id or frame.predicted_movie_id
    if movie_id is None:
        return {}

    existing: list[ActorDetection] = (
        session.query(ActorDetection)
        .join(Frame, ActorDetection.frame_id == Frame.id)
        .filter(
            Frame.movie_id == movie_id,
            ActorDetection.cast_member_id.is_(None),
            ActorDetection.embedding.isnot(None),
            ActorDetection.cluster_label.isnot(None),
        )
        .all()
    )

    clusters: dict[str, list[list[float]]] = {}
    for record in existing:
        try:
            embedding = json.loads(record.embedding or "[]")
        except Exception:
            continue
        if not embedding:
            continue
        clusters.setdefault(record.cluster_label or "unknown", []).append(embedding)

    def _next_cluster_label() -> str:
        indices = [
            int(label.split("-")[-1])
            for label in clusters.keys()
            if label.startswith("unknown-") and label.split("-")[-1].isdigit()
        ]
        next_index = (max(indices) + 1) if indices else 1
        return f"unknown-{next_index}"

    results: dict[int, tuple[str, str]] = {}
    for idx, detection in enumerate(detections):
        if detection.cast_member_id is not None or not detection.embedding:
            results[idx] = ("identified", detection.cluster_label or "")
            continue

        best_label: str | None = None
        best_score = 0.0
        try:
            embedding = json.loads(detection.embedding)
        except Exception:
            embedding = []

        if not embedding:
            results[idx] = ("untracked", detection.cluster_label or "")
            continue

        for label, embeddings in clusters.items():
            centroid = np.mean(np.asarray(embeddings), axis=0)
            score = cosine_similarity(embedding, centroid.tolist())
            if score > best_score:
                best_score = score
                best_label = label

        if best_label and best_score >= unknown_threshold:
            results[idx] = ("tracked", best_label)
            clusters.setdefault(best_label, []).append(embedding)
        else:
            label = _next_cluster_label()
            clusters.setdefault(label, []).append(embedding)
            results[idx] = ("new_track", label)

    return results


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
    settings = get_settings()
    cleanup = False
    path: Path | None = None
    try:
        with _session_scope(session_factory) as session:
            frame = session.get(Frame, frame_id)
            if frame is None:
                raise ValueError(f"Frame with id {frame_id} does not exist")

            # Idempotency: clear prior predictions
            session.query(SceneAttribute).filter(SceneAttribute.frame_id == frame.id).delete()

            try:
                path, cleanup = _materialize_frame(frame)
            except FileNotFoundError as exc:
                _mark_failure(frame.id, str(exc), session_factory=session_factory)
                raise

            image = _load_image(path)

            try:
                predictions = predict_scene_attributes(image, service_url=settings.vision_service_url)
            except Exception:
                logger.exception("Scene attribute prediction failed for frame %s", frame.id)
                predictions = []

            if not predictions:
                embedding = json.loads(frame.embedding) if frame.embedding else []
                predictions = [
                    SceneAttributePrediction(
                        attribute="time_of_day",
                        value="night" if (embedding[0] if embedding else 0.5) < 0.45 else "day",
                        confidence=0.5,
                    )
                ]

            applied = _persist_scene_attributes(session, frame, predictions)

            frame.failure_reason = None
            frame.status = "scene_annotated"
            session.add(frame)

            logger.info("Scene attributes stored for frame %s", frame.id)
            return {"status": "scene_attributes", "frame_id": frame.id, "attributes": applied}
    finally:
        if cleanup and path and path.exists():
            try:
                path.unlink()
            except Exception:
                logger.warning("Could not cleanup scene attribute temp file for frame %s", frame_id)


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
                detected_faces = detect_faces(
                    image,
                    min_confidence=settings.face_min_confidence,
                    service_url=settings.face_analytics_service_url,
                )
            except Exception:
                logger.exception("Falling back to legacy actor detection for frame %s", frame.id)
                detected_faces = []

            cast_embeddings = _reference_embeddings_for_cast(session, frame, settings)

            persisted: list[dict[str, Any]] = []
            new_records: list[ActorDetection] = []
            similarities: list[float] = []
            for index, face in enumerate(detected_faces):
                bbox = ",".join(f"{value:.4f}" for value in face.bbox) if face.bbox else None
                matched_cast_id, similarity = _best_match_for_face(
                    face.embedding, cast_embeddings, settings.face_recognition_match_threshold
                )
                if face.confidence < settings.face_min_confidence:
                    matched_cast_id = None
                    similarity = 0.0
                combined_confidence = round(min(1.0, face.confidence * max(similarity, 0.5)), 3)
                detection = ActorDetection(
                    frame_id=frame.id,
                    cast_member_id=matched_cast_id,
                    face_index=index,
                    confidence=combined_confidence,
                    bbox=bbox,
                    embedding=json.dumps(face.embedding),
                    emotion=face.emotion,
                    pose_yaw=face.pose_yaw,
                    pose_pitch=face.pose_pitch,
                    pose_roll=face.pose_roll,
                )
                session.add(detection)
                new_records.append(detection)
                similarities.append(similarity)

            clustering = _cluster_unknown_faces(
                session, frame, new_records, settings.face_unknown_match_threshold
            )

            for idx, detection in enumerate(new_records):
                if detection.cast_member_id is not None:
                    detection.track_status = "identified"
                    detection.cluster_label = detection.cluster_label
                elif idx in clustering:
                    status, label = clustering[idx]
                    detection.track_status = status
                    detection.cluster_label = label

                similarity = similarities[idx] if idx < len(similarities) else None
                persisted.append(
                    {
                        "cast_member_id": detection.cast_member_id,
                        "confidence": detection.confidence,
                        "bbox": [float(v) for v in detection.bbox.split(",")] if detection.bbox else None,
                        "similarity": similarity,
                        "cluster_label": detection.cluster_label,
                        "emotion": detection.emotion,
                        "pose": {
                            "yaw": detection.pose_yaw,
                            "pitch": detection.pose_pitch,
                            "roll": detection.pose_roll,
                        },
                        "track_status": detection.track_status,
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


def _maybe_enqueue_enrichment(
    frame_id: int,
    predicted_movie_id: int | None,
    predicted_timestamp: str | None = None,
    session_factory: SessionFactory | None = None,
) -> None:
    if predicted_movie_id is None:
        return

    with _session_scope(session_factory) as session:
        movie = session.get(Movie, predicted_movie_id)
        if movie is None or movie.tmdb_id is None:
            return
        enrich_frame_metadata.delay(
            frame_id,
            movie.tmdb_id,
            shot_timestamp=predicted_timestamp,
        )


@shared_task(name="frames.enrich_metadata")
def enrich_frame_metadata(
    frame_id: int,
    tmdb_id: int,
    provider_hint: str | None = None,
    shot_timestamp: str | None = None,
    scene_summary: str | None = None,
    session_factory: SessionFactory | None = None,
) -> dict[str, Any]:
    """Enrich a frame with upstream metadata and persist the provider used."""

    ingestor = TMDBIngestor(provider_hint=provider_hint)
    ingest_result = ingestor.ingest_movie(tmdb_id)

    with _session_scope(session_factory) as session:
        frame = session.get(Frame, frame_id)
        if frame is None:
            raise ValueError(f"Frame with id {frame_id} does not exist")

        movie = (
            session.get(Movie, ingest_result.get("movie_id"))
            if ingest_result.get("movie_id") is not None
            else None
        )
        if movie is not None:
            if frame.movie_id is None:
                frame.movie_id = movie.id
            if frame.predicted_movie_id is None:
                frame.predicted_movie_id = movie.id
            if scene_summary is None and movie.description:
                scene_summary = movie.description

        frame.shot_timestamp = shot_timestamp or frame.shot_timestamp or frame.predicted_timestamp
        if scene_summary is not None:
            frame.scene_summary = scene_summary
        frame.metadata_source = ingest_result.get("provider") or provider_hint or frame.metadata_source
        frame.failure_reason = None
        frame.status = "enriched"
        session.add(frame)

        logger.info(
            "Frame %s enriched via %s (movie_id=%s)",
            frame.id,
            frame.metadata_source,
            frame.movie_id,
        )

        return {
            "status": "enriched",
            "frame_id": frame.id,
            "movie_id": frame.movie_id,
            "metadata_source": frame.metadata_source,
            "shot_timestamp": frame.shot_timestamp,
            "scene_summary": frame.scene_summary,
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
            _maybe_enqueue_enrichment(
                frame_id,
                match_result.get("predicted_movie_id"),
                match_result.get("predicted_timestamp"),
            )
        else:
            tag_result = tag_frame(frame_id)
            scene_result = detect_scene_attributes(frame_id)
            actor_result = detect_actor_faces(frame_id)
            _maybe_enqueue_enrichment(frame_id, movie_id)
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
