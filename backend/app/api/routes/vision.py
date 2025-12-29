from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.core.auth import require_role
from app.core.celery import celery_app
from app.db import get_db
from app.models import ActorDetection, Frame, FrameTag, SceneAttribute, Tag
from app.services.vision import get_vision_model_status
from app.tasks.vision import warmup_models_task

logger = logging.getLogger(__name__)

router_models = APIRouter(prefix="/models/vision", tags=["vision-models"])
router_vision = APIRouter(prefix="/vision", tags=["vision"])


@router_models.get("/status")
def vision_model_status() -> dict[str, Any]:
    return {"models": get_vision_model_status()}


@router_models.post("/warmup")
def warmup_models(_: object = Depends(require_role("moderator", "admin"))) -> dict[str, str]:
    task = warmup_models_task.delay()
    return {"task_id": task.id, "status": "queued"}


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


@router_vision.get("/pipelines")
def list_vision_pipelines() -> dict[str, list[dict[str, Any]]]:
    """List all available vision pipelines with their status.
    
    Returns:
        Dict with "pipelines" key containing list of pipeline metadata
    """
    try:
        from app.services.vision_pipelines import list_pipelines
        
        pipelines = list_pipelines()
        return {
            "pipelines": [
                {
                    "id": p.id,
                    "name": p.name,
                    "model_id": p.model_id,
                    "input_resolution": p.input_resolution,
                    "device": p.device,
                    "dtype": p.dtype,
                    "version": p.version,
                    "loaded": p.loaded,
                }
                for p in pipelines
            ]
        }
    except Exception as e:
        logger.exception("Failed to list vision pipelines")
        raise HTTPException(
            status_code=500, detail=f"Failed to list pipelines: {str(e)}"
        ) from e


class AnalyzeFrameRequest(BaseModel):
    """Request body for analyzing a single frame with a specific pipeline."""
    
    frame_id: int
    pipeline_id: str = Field(default="clip_vitb32", description="Pipeline ID to use")
    force: bool = Field(default=False, description="Force recompute even if cached")


@router_vision.post("/analyze")
def analyze_frame_endpoint(
    payload: AnalyzeFrameRequest,
    db: Session = Depends(get_db),
    _: object = Depends(require_role("moderator", "admin")),
) -> dict[str, Any]:
    """Analyze a single frame with a specified vision pipeline.
    
    This endpoint triggers embedding extraction and attribute classification
    using the specified pipeline. Results are cached and returned on subsequent
    calls unless force=True.
    
    Args:
        payload: Request with frame_id, pipeline_id, and force flag
        db: Database session
        
    Returns:
        Dict with status, pipeline_id, and results (embeddings + attributes)
        
    Raises:
        HTTPException: If frame not found or analysis fails
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Check if frame exists
    frame = db.query(Frame).filter(Frame.id == payload.frame_id).first()
    if not frame:
        raise HTTPException(status_code=404, detail=f"Frame {payload.frame_id} not found")
    
    try:
        # Import late to avoid circular dependencies
        from app.services import vision_service
        
        result = vision_service.analyze_frame(
            frame_id=payload.frame_id,
            pipeline_id=payload.pipeline_id,
            force=payload.force,
            session=db,
        )
        
        return {
            "status": "success",
            "frame_id": payload.frame_id,
            "pipeline_id": payload.pipeline_id,
            **result,
        }
    except KeyError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid pipeline_id: {str(e)}"
        ) from e
    except Exception as e:
        logger.exception("Frame analysis failed")
        raise HTTPException(
            status_code=500, detail=f"Analysis failed: {str(e)}"
        ) from e
