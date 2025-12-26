from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.core.auth import require_role
from app.core.celery import celery_app
from app.db import get_db
from app.models import ActorDetection, Frame, FrameTag, SceneAttribute, Tag
from app.services.vision import get_vision_model_status, warmup_vision_models

router_models = APIRouter(prefix="/models/vision", tags=["vision-models"])
router_vision = APIRouter(prefix="/vision", tags=["vision"])


@router_models.get("/status")
def vision_model_status() -> dict[str, Any]:
    return {"models": get_vision_model_status()}


@router_models.post("/warmup")
def warmup_models(_: object = Depends(require_role("moderator", "admin"))) -> dict[str, bool]:
    warmup_vision_models()
    return {"ok": True}


class VisionRunFilters(BaseModel):
    movie_id: int | None = None
    tag: list[str] | None = None
    status: str | None = None
    cast_member_id: int | None = None
    time_of_day: str | None = None


class VisionRunRequest(BaseModel):
    frame_ids: list[int] | None = None
    filters: VisionRunFilters | None = None
    limit: int = Field(default=500, ge=1, le=5000)


def _apply_filters(query, filters: VisionRunFilters):
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


@router_vision.post("/run")
def run_vision_analysis(
    payload: VisionRunRequest,
    db: Session = Depends(get_db),
    _: object = Depends(require_role("moderator", "admin")),
) -> dict[str, Any]:
    frame_ids = payload.frame_ids or []
    if not frame_ids and payload.filters:
        query = db.query(Frame.id)
        query = _apply_filters(query, payload.filters)
        frame_ids = [row[0] for row in query.limit(payload.limit).all()]

    if not frame_ids:
        raise HTTPException(status_code=400, detail="No frames matched the request")

    async_result = celery_app.signature("vision.analyze_frames", args=(frame_ids,)).apply_async()
    return {"job_id": async_result.id, "count": len(frame_ids)}
