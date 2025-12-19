from __future__ import annotations

from typing import Any, Iterable
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import and_, func
from sqlalchemy.orm import Session, joinedload

from app.core.auth import require_role
from app.core.celery import celery_app
from app.db import get_db
from app.models import (
    ActorDetection,
    Frame,
    FrameTag,
    Movie,
    SceneAttribute,
    Tag,
)
from app.services.storage import resolve_frame_signed_url
from app.tasks.frames import ingest_and_tag_frame

router = APIRouter(prefix="/frames", tags=["frames"])


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
        "file_path": frame.file_path,
        "storage_uri": frame.storage_uri,
        "signed_url": signed_url,
        "status": frame.status,
        "embedding_model": frame.embedding_model,
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
                "confidence": detection.confidence,
                "bbox": detection.bbox,
                "face_index": detection.face_index,
            }
            for detection in frame.actor_detections
        ],
    }


def _apply_filters(query, filters: FrameFilters):
    if filters.movie_id:
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
            joinedload(Frame.actor_detections),
        )
        .join(Movie)
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
            joinedload(Frame.actor_detections),
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


class IngestRequest(BaseModel):
    movie_id: int
    storage_uri: str | None = None
    file_path: str
    signed_url: str | None = None
    captured_at: str | None = None


@router.post("/ingest")
def enqueue_ingest(
    payload: IngestRequest, _: object = Depends(require_role("moderator", "admin"))
) -> dict[str, str | int]:
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
    movie_id: int = Form(..., description="Database movie id"),
    file: UploadFile = File(...),
    _: object = Depends(require_role("moderator", "admin")),
) -> dict[str, str | int]:
    destination = Path("/tmp/uploads")
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / file.filename
    content = await file.read()
    target.write_bytes(content)

    async_result = ingest_and_tag_frame.delay(
        file_path=str(target),
        movie_id=movie_id,
        storage_uri=None,
    )
    return {"task_id": async_result.id, "status": "queued", "file_path": str(target)}


@router.get("/tasks/{task_id}")
def get_task_status(task_id: str) -> dict[str, Any]:
    result = celery_app.AsyncResult(task_id)
    response: dict[str, Any] = {"task_id": task_id, "state": result.state}
    if result.successful():
        response["result"] = result.result
    elif result.failed():
        response["error"] = str(result.result)
    return response
