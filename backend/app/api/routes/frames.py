from __future__ import annotations

from typing import Any
import asyncio
import json
import logging
from datetime import datetime
from io import BytesIO

from celery import chain
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from tempfile import NamedTemporaryFile
from urllib.parse import urlparse
import uuid
from sqlalchemy import and_, func
from sqlalchemy.orm import Session, joinedload

from app.core.auth import AuthenticatedUser, require_role
from app.core.settings import get_settings
from app.db import SessionLocal
from app.core.celery import celery_app
from app.db import get_db
from app.integrations.tmdb import TMDBIngestor
from app.models import (
    ActorDetection,
    Frame,
    FrameTag,
    Movie,
    SceneAttribute,
    Tag,
)
from app.services.storage import (
    resolve_frame_signed_url,
    upload_fileobj,
    generate_presigned_url,
    _build_s3_client,
)
from app.tasks.frames import ingest_and_tag_frame

router = APIRouter(prefix="/frames", tags=["frames"])
logger = logging.getLogger(__name__)


class FrameFilters(BaseModel):
    movie_id: int | None = None
    tag: list[str] | None = None
    status: str | None = None
    cast_member_id: int | None = None
    time_of_day: str | None = None
    limit: int = 20
    offset: int = 0
    sort: str = "-created_at"


def _serialize_frame(frame: Frame) -> dict[str, Any]:
    signed_url = resolve_frame_signed_url(frame)
    return {
        "id": frame.id,
        "movie_id": frame.movie_id,
        "movie_title": frame.movie.title if frame.movie else None,
        "match_confidence": frame.match_confidence,
        "predicted_timestamp": frame.predicted_timestamp,
        "predicted_shot_id": frame.predicted_shot_id,
        "shot_timestamp": frame.shot_timestamp,
        "scene_summary": frame.scene_summary,
        "metadata_source": frame.metadata_source,
        "file_path": frame.file_path,
        "storage_uri": frame.storage_uri,
        "signed_url": signed_url,
        "status": frame.status,
        "embedding_model": frame.embedding_model,
        "embedding_model_version": frame.embedding_model_version,
        "failure_reason": frame.failure_reason,
        "ingested_at": frame.ingested_at,
        "captured_at": frame.captured_at,
        "created_at": frame.created_at,
        "updated_at": frame.updated_at,
        "tags": [
            {"id": ft.tag.id, "name": ft.tag.name, "confidence": ft.confidence}
            for ft in frame.tags
        ],
        "scene_attributes": [
            {
                "id": attr.id,
                "attribute": attr.attribute,
                "value": attr.value,
                "confidence": attr.confidence,
            }
            for attr in frame.scene_attributes
        ],
        "actor_detections": [
            {
                "id": detection.id,
                "cast_member_id": detection.cast_member_id,
                "cast_member_name": detection.cast_member.name
                if detection.cast_member
                else None,
                "confidence": detection.confidence,
                "bbox": [float(value) for value in detection.bbox.split(",")] if detection.bbox else None,
                "face_index": detection.face_index,
                "embedding": json.loads(detection.embedding) if detection.embedding else None,
                "cluster_label": detection.cluster_label,
                "track_status": detection.track_status,
                "emotion": detection.emotion,
                "pose": {
                    "yaw": detection.pose_yaw,
                    "pitch": detection.pose_pitch,
                    "roll": detection.pose_roll,
                },
            }
            for detection in frame.actor_detections
        ],
    }


def _apply_filters(query, filters: FrameFilters):
    if filters.movie_id is not None:
        query = query.filter(Frame.movie_id == filters.movie_id)
    if filters.status:
        query = query.filter(Frame.status == filters.status)
    if filters.tag:
        query = query.join(FrameTag).join(Tag).filter(Tag.name.in_(filters.tag))
    if filters.cast_member_id:
        query = query.join(ActorDetection).filter(
            ActorDetection.cast_member_id == filters.cast_member_id
        )
    if filters.time_of_day:
        query = query.join(SceneAttribute).filter(
            and_(
                SceneAttribute.attribute == "time_of_day",
                SceneAttribute.value == filters.time_of_day,
            )
        )
    return query


def _apply_sort(query, sort: str):
    ordering = Frame.created_at.desc() if sort.startswith("-") else Frame.created_at
    if sort.lstrip("-") == "updated_at":
        ordering = Frame.updated_at.desc() if sort.startswith("-") else Frame.updated_at
    return query.order_by(ordering)


@router.get("/storage")
def browse_storage(
    prefix: str | None = None,
    limit: int = 50,
    cursor: str | None = Query(default=None, description="Continuation token from previous page"),
    _: object = Depends(require_role("moderator", "admin")),
) -> dict[str, Any]:
    """List raw objects from the configured frames bucket.

    This is used by the frontend storage explorer to surface assets that may
    not yet be ingested into the database.
    """

    settings = get_settings()
    if not (
        settings.storage_frames_bucket
        and settings.storage_access_key
        and settings.storage_secret_key
    ):
        raise HTTPException(status_code=503, detail="Storage is not configured")

    client = _build_s3_client(settings.storage_endpoint_url)
    params: dict[str, Any] = {
        "Bucket": settings.storage_frames_bucket,
        "MaxKeys": min(limit, 1000),
    }
    if prefix:
        params["Prefix"] = prefix.lstrip("/")
    if cursor:
        params["ContinuationToken"] = cursor

    try:
        response = client.list_objects_v2(**params)
    except Exception as exc:
        logger.exception("Unable to list storage objects")
        raise HTTPException(status_code=502, detail=f"Storage browse failed: {exc}") from exc

    items = []
    for obj in response.get("Contents", []):
        storage_uri = f"s3://{settings.storage_frames_bucket}/{obj['Key']}"
        items.append(
            {
                "key": obj["Key"],
                "size": obj.get("Size"),
                "last_modified": obj.get("LastModified"),
                "storage_uri": storage_uri,
                "signed_url": generate_presigned_url(storage_uri),
            }
        )

    return {
        "bucket": settings.storage_frames_bucket,
        "items": items,
        "prefix": prefix,
        "truncated": response.get("IsTruncated", False),
        "next_cursor": response.get("NextContinuationToken"),
    }


@router.get("/lookup")
def lookup_frame(
    storage_uri: str | None = None,
    file_path: str | None = None,
    db: Session = Depends(get_db),
    _: object = Depends(require_role("moderator", "admin")),
) -> dict[str, Any]:
    if not storage_uri and not file_path:
        raise HTTPException(status_code=400, detail="storage_uri or file_path is required")

    query = (
        db.query(Frame)
        .options(
            joinedload(Frame.tags).joinedload(FrameTag.tag),
            joinedload(Frame.scene_attributes),
            joinedload(Frame.actor_detections).joinedload(ActorDetection.cast_member),
            joinedload(Frame.movie),
        )
    )

    if storage_uri:
        query = query.filter(Frame.storage_uri == storage_uri)
    if file_path:
        query = query.filter(Frame.file_path == file_path)

    frame = query.one_or_none()
    if frame is None:
        raise HTTPException(status_code=404, detail="Frame not found")
    return _serialize_frame(frame)


class StorageFrameCreate(BaseModel):
    storage_uri: str
    file_path: str
    movie_id: int | None = None
    captured_at: datetime | None = None


@router.post("/from-storage")
def create_frame_from_storage(
    payload: StorageFrameCreate,
    db: Session = Depends(get_db),
    _: object = Depends(require_role("moderator", "admin")),
) -> dict[str, Any]:
    frame = Frame(
        storage_uri=payload.storage_uri,
        file_path=payload.file_path,
        movie_id=payload.movie_id,
        captured_at=payload.captured_at,
        ingested_at=datetime.utcnow(),
        status="needs_analyzing",
    )
    db.add(frame)
    db.commit()
    db.refresh(frame)
    return _serialize_frame(frame)


class FrameUpdateRequest(BaseModel):
    movie_id: int | None = None
    predicted_timestamp: str | None = None
    predicted_shot_id: str | None = None
    shot_timestamp: str | None = None
    scene_summary: str | None = None
    metadata_source: str | None = None
    file_path: str | None = None
    storage_uri: str | None = None
    match_confidence: float | None = None
    status: str | None = None
    captured_at: datetime | None = None
    embedding_model: str | None = None
    embedding_model_version: str | None = None


@router.patch("/{frame_id}")
def update_frame(
    frame_id: int,
    payload: FrameUpdateRequest,
    db: Session = Depends(get_db),
    _: object = Depends(require_role("moderator", "admin")),
) -> dict[str, Any]:
    frame = db.get(Frame, frame_id)
    if frame is None:
        raise HTTPException(status_code=404, detail="Frame not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(frame, field, value)

    db.add(frame)
    db.commit()
    db.refresh(frame)
    return _serialize_frame(frame)


class TMDBAssignmentRequest(BaseModel):
    tmdb_id: int


@router.post("/{frame_id}/assign-tmdb")
async def assign_frame_tmdb(
    frame_id: int,
    payload: TMDBAssignmentRequest,
    user: AuthenticatedUser = Depends(require_role("moderator", "admin")),
) -> dict[str, Any]:
    result = await asyncio.to_thread(sync_assign_frame_tmdb, frame_id, payload)
    return result


def sync_assign_frame_tmdb(frame_id: int, payload: TMDBAssignmentRequest) -> dict[str, Any]:
    db = SessionLocal()
    try:
        frame = db.get(Frame, frame_id)
        if frame is None:
            raise HTTPException(status_code=404, detail="Frame not found")

        ingestor = TMDBIngestor(session_factory=SessionLocal.session_factory)
        try:
            ingest_result = ingestor.ingest_movie(payload.tmdb_id)
        except Exception as exc:
            logger.exception("TMDb ingest failed for frame %s", frame_id)
            raise HTTPException(status_code=502, detail=f"TMDb ingest failed: {exc}") from exc

        movie_id = ingest_result.get("movie_id")
        if movie_id is None:
            raise HTTPException(status_code=502, detail="TMDb ingest did not yield a movie id")

        movie = db.get(Movie, movie_id)
        if movie is None:
            raise HTTPException(status_code=404, detail="Movie not found after ingest")

        if frame.scene_summary is None and movie.description:
            frame.scene_summary = movie.description

        frame.movie_id = movie.id
        frame.match_confidence = 1.0
        frame.status = "tmdb_only"
        frame.metadata_source = ingest_result.get("provider") or "tmdb"

        db.add(frame)
        db.commit()
        db.refresh(frame)
        return _serialize_frame(frame)
    finally:
        db.close()


@router.get("")
def list_frames(
    movie_id: int | None = None,
    tag: list[str] | None = Query(default=None),
    status: str | None = None,
    cast_member_id: int | None = None,
    time_of_day: str | None = None,
    limit: int = 20,
    offset: int = 0,
    sort: str = "-created_at",
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    filters = FrameFilters(
        movie_id=movie_id,
        tag=list(tag) if tag else None,
        status=status,
        cast_member_id=cast_member_id,
        time_of_day=time_of_day,
        limit=limit,
        offset=offset,
        sort=sort,
    )
    base_query = (
        db.query(Frame)
        .options(
            joinedload(Frame.tags).joinedload(FrameTag.tag),
            joinedload(Frame.scene_attributes),
            joinedload(Frame.actor_detections).joinedload(ActorDetection.cast_member),
            joinedload(Frame.movie),
        )
        .outerjoin(Movie, Frame.movie_id == Movie.id)
    )
    filtered = _apply_filters(base_query, filters)
    total = filtered.distinct().count()
    items = (
        _apply_sort(filtered, filters.sort)
        .offset(filters.offset)
        .limit(min(filters.limit, 100))
        .all()
    )
    return {
        "items": [_serialize_frame(frame) for frame in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{frame_id}")
def get_frame(frame_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    frame = (
        db.query(Frame)
        .options(
        joinedload(Frame.tags).joinedload(FrameTag.tag),
        joinedload(Frame.scene_attributes),
        joinedload(Frame.actor_detections).joinedload(ActorDetection.cast_member),
        joinedload(Frame.movie),
    )
        .filter(Frame.id == frame_id)
        .one_or_none()
    )
    if frame is None:
        raise HTTPException(status_code=404, detail="Frame not found")
    return _serialize_frame(frame)


class TagUpdateRequest(BaseModel):
    tags: list[str]


@router.post("/{frame_id}/tags")
def replace_frame_tags(
    frame_id: int,
    payload: TagUpdateRequest,
    db: Session = Depends(get_db),
    _: object = Depends(require_role("moderator", "admin")),
) -> dict[str, Any]:
    frame = db.get(Frame, frame_id)
    if frame is None:
        raise HTTPException(status_code=404, detail="Frame not found")

    existing_tags = {ft.tag.name: ft for ft in frame.tags}
    for tag_name in payload.tags:
        tag = db.query(Tag).filter(Tag.name == tag_name).one_or_none()
        if tag is None:
            tag = Tag(name=tag_name)
            db.add(tag)
            db.flush()

        if tag_name not in existing_tags:
            db.add(FrameTag(frame_id=frame.id, tag_id=tag.id, confidence=1.0))

    # remove tags not requested
    for tag_name, frame_tag in existing_tags.items():
        if tag_name not in payload.tags:
            db.delete(frame_tag)

    frame.status = "confirmed"
    db.add(frame)
    db.commit()
    db.refresh(frame)
    return _serialize_frame(frame)


class SceneAttributePayload(BaseModel):
    attribute: str
    value: str
    confidence: float | None = None


class SceneAttributeUpdateRequest(BaseModel):
    attributes: list[SceneAttributePayload]


@router.post("/{frame_id}/scene-attributes")
def replace_scene_attributes(
    frame_id: int,
    payload: SceneAttributeUpdateRequest,
    db: Session = Depends(get_db),
    _: object = Depends(require_role("moderator", "admin")),
) -> dict[str, Any]:
    frame = db.get(Frame, frame_id)
    if frame is None:
        raise HTTPException(status_code=404, detail="Frame not found")

    for existing in list(frame.scene_attributes):
        db.delete(existing)

    for attr in payload.attributes:
        db.add(
            SceneAttribute(
                frame_id=frame.id,
                attribute=attr.attribute,
                value=attr.value,
                confidence=attr.confidence,
            )
        )

    frame.status = "analyzed"
    db.add(frame)
    db.commit()
    db.refresh(frame)
    return _serialize_frame(frame)


class ActorDetectionPayload(BaseModel):
    cast_member_id: int | None = None
    confidence: float | None = None
    face_index: int | None = None
    bbox: list[float] | None = None
    cluster_label: str | None = None
    track_status: str | None = None
    emotion: str | None = None
    pose_yaw: float | None = None
    pose_pitch: float | None = None
    pose_roll: float | None = None


class ActorDetectionsUpdateRequest(BaseModel):
    actors: list[ActorDetectionPayload]


@router.post("/{frame_id}/actors")
def replace_actor_detections(
    frame_id: int,
    payload: ActorDetectionsUpdateRequest,
    db: Session = Depends(get_db),
    _: object = Depends(require_role("moderator", "admin")),
) -> dict[str, Any]:
    frame = db.get(Frame, frame_id)
    if frame is None:
        raise HTTPException(status_code=404, detail="Frame not found")

    for detection in list(frame.actor_detections):
        db.delete(detection)

    for detection in payload.actors:
        bbox = ",".join(str(value) for value in detection.bbox) if detection.bbox else None
        db.add(
            ActorDetection(
                frame_id=frame.id,
                cast_member_id=detection.cast_member_id,
                confidence=detection.confidence,
                face_index=detection.face_index,
                bbox=bbox,
                cluster_label=detection.cluster_label,
                track_status=detection.track_status,
                emotion=detection.emotion,
                pose_yaw=detection.pose_yaw,
                pose_pitch=detection.pose_pitch,
                pose_roll=detection.pose_roll,
            )
        )

    frame.status = "analyzed"
    db.add(frame)
    db.commit()
    db.refresh(frame)
    return _serialize_frame(frame)


class FrameStatusUpdate(BaseModel):
    status: str


@router.post("/{frame_id}/status")
def update_frame_status(
    frame_id: int,
    payload: FrameStatusUpdate,
    db: Session = Depends(get_db),
    _: object = Depends(require_role("moderator", "admin")),
) -> dict[str, Any]:
    frame = db.get(Frame, frame_id)
    if frame is None:
        raise HTTPException(status_code=404, detail="Frame not found")
    frame.status = payload.status
    db.add(frame)
    db.commit()
    db.refresh(frame)
    return {"frame_id": frame.id, "status": frame.status}


@router.post("/{frame_id}/analyze")
def analyze_frame(
    frame_id: int,
    db: Session = Depends(get_db),
    _: object = Depends(require_role("moderator", "admin")),
) -> dict[str, Any]:
    frame = db.get(Frame, frame_id)
    if frame is None:
        raise HTTPException(status_code=404, detail="Frame not found")

    pipeline = chain(
        celery_app.signature("frames.embed", args=(frame.id,)),
        celery_app.signature("frames.tag", args=(frame.id,)),
        celery_app.signature("frames.scene_attributes", args=(frame.id,)),
        celery_app.signature("frames.actor_detections", args=(frame.id,)),
    )
    async_result = pipeline.apply_async()
    return {"task_id": async_result.id, "status": "queued", "frame_id": frame.id}


@router.post("/{frame_id}/vision/run")
def run_frame_vision_analysis(
    frame_id: int,
    db: Session = Depends(get_db),
    _: object = Depends(require_role("moderator", "admin")),
) -> dict[str, Any]:
    frame = db.get(Frame, frame_id)
    if frame is None:
        raise HTTPException(status_code=404, detail="Frame not found")

    async_result = celery_app.signature("vision.analyze_frames", args=([frame.id],)).apply_async()
    return {"job_id": async_result.id, "frame_id": frame.id}


class IngestRequest(BaseModel):
    movie_id: int | None = None
    storage_uri: str | None = None
    file_path: str
    signed_url: str | None = None
    captured_at: str | None = None


def _validate_location(file_path: str, signed_url: str | None) -> None:
    parsed_file = urlparse(file_path)
    parsed_signed = urlparse(signed_url) if signed_url else None

    allowed_schemes = {"s3", "http", "https", ""}
    if parsed_file.scheme and parsed_file.scheme not in allowed_schemes:
        raise HTTPException(status_code=400, detail="Unsupported file_path scheme")
    if parsed_signed and parsed_signed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=400, detail="signed_url must be http/https")

    if parsed_file.scheme in {"http", "https"} and not signed_url:
        # Require explicit signed URL if ingesting via remote HTTP
        raise HTTPException(status_code=400, detail="signed_url is required for remote http/https ingest")


@router.post("/ingest")
def enqueue_ingest(
    payload: IngestRequest, _: object = Depends(require_role("moderator", "admin"))
) -> dict[str, str | int]:
    _validate_location(payload.file_path, payload.signed_url)
    async_result = ingest_and_tag_frame.delay(
    file_path=payload.file_path,
    movie_id=payload.movie_id,
    storage_uri=payload.storage_uri,
    signed_url=payload.signed_url,
    captured_at=payload.captured_at,
    )
    return {"task_id": async_result.id, "status": "queued"}


@router.post("/ingest/upload")
async def upload_and_ingest(
    movie_id: int | None = Form(
        None, description="Database movie id if already known"
    ),
    file: UploadFile = File(...),
    _: object = Depends(require_role("moderator", "admin")),
) -> dict[str, str | int]:
    object_key = f"uploads/{uuid.uuid4().hex}-{file.filename}"
    storage_uri: str | None = None
    payload_path = file.filename
    file.file.seek(0)
    payload = file.file.read()
    try:
        storage_uri = upload_fileobj(
            BytesIO(payload),
            key=object_key,
            content_type=file.content_type,
        )
    except Exception as exc:
        logger.warning("Upload failed, storing frame locally instead: %s", exc)
        temp_file = NamedTemporaryFile(delete=False, suffix=file.filename)
        temp_file.write(payload)
        temp_file.flush()
        payload_path = temp_file.name
    finally:
        try:
            file.file.close()
        except Exception:
            pass

    storage_uri = storage_uri or payload_path
    async_result = ingest_and_tag_frame.delay(
        file_path=payload_path,
        movie_id=movie_id,
        storage_uri=storage_uri,
    )
    return {"task_id": async_result.id, "status": "queued", "storage_uri": storage_uri}


@router.get("/tasks/{task_id}")
def get_task_status(task_id: str) -> dict[str, Any]:
    result = celery_app.AsyncResult(task_id)
    response: dict[str, Any] = {"task_id": task_id, "state": result.state}
    if result.successful():
        response["result"] = result.result
    elif result.failed():
        response["error"] = str(result.result)
    return response


class FrameExportRequest(BaseModel):
    frame_ids: list[int]
    format: str = "csv"


@router.post("/export")
def export_frames(
    payload: FrameExportRequest,
    db: Session = Depends(get_db),
    _: object = Depends(require_role("moderator", "admin")),
) -> StreamingResponse:
    if not payload.frame_ids:
        raise HTTPException(status_code=400, detail="frame_ids is required")

    frames = (
        db.query(Frame)
        .options(
            joinedload(Frame.tags).joinedload(FrameTag.tag),
            joinedload(Frame.scene_attributes),
            joinedload(Frame.actor_detections).joinedload(ActorDetection.cast_member),
            joinedload(Frame.movie),
        )
        .filter(Frame.id.in_(payload.frame_ids))
        .all()
    )

    serialized = [_serialize_frame(frame) for frame in frames]

    if payload.format == "json":
        content = json.dumps(serialized, default=str).encode("utf-8")
        return StreamingResponse(
            iter([content]),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=frames.json"},
        )

    fieldnames = [
        "id",
        "movie_id",
        "movie_title",
        "match_confidence",
        "status",
        "file_path",
        "signed_url",
        "predicted_timestamp",
        "predicted_shot_id",
        "shot_timestamp",
        "scene_summary",
        "metadata_source",
        "captured_at",
        "tags",
        "scene_attributes",
        "actor_detections",
    ]
    rows: list[dict[str, Any]] = []
    for frame in serialized:
        rows.append(
            {
                "id": frame["id"],
                "movie_id": frame["movie_id"],
                "movie_title": frame["movie_title"],
                "match_confidence": frame.get("match_confidence"),
                "status": frame["status"],
                "file_path": frame["file_path"],
                "signed_url": frame.get("signed_url"),
                "predicted_timestamp": frame.get("predicted_timestamp"),
                "predicted_shot_id": frame.get("predicted_shot_id"),
                "shot_timestamp": frame.get("shot_timestamp"),
                "scene_summary": frame.get("scene_summary"),
                "metadata_source": frame.get("metadata_source"),
                "captured_at": frame.get("captured_at"),
                "tags": ";".join(tag["name"] for tag in frame["tags"]),
                "scene_attributes": json.dumps(frame["scene_attributes"]),
                "actor_detections": json.dumps(frame["actor_detections"]),
            }
        )

    import csv
    from io import StringIO

    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)

    content = buffer.getvalue().encode("utf-8")
    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=frames.csv"},
    )
